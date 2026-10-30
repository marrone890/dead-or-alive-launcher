"""Authenticated launcher companion. The game resource remains authoritative for lobbies."""
import hashlib, json, os, re, secrets, threading, time
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path
import pymysql
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

CONFIG_PATH = Path(os.environ.get('DOA_SOCIAL_CONFIG', 'C:/RedM-Setup/launcher-private/service.json'))
config = json.loads(CONFIG_PATH.read_text())
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
lock = threading.Lock()
limits = defaultdict(deque)
def now(): return int(time.time())
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def fail(message, code=400): raise HTTPException(code, message)
@contextmanager
def db():
    con = pymysql.connect(**config['database'], charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=5, read_timeout=8, write_timeout=8, autocommit=False)
    try:
        with con.cursor() as cur: yield cur
        con.commit()
    except BaseException:
        con.rollback(); raise
    finally: con.close()
def one(c, q, args=()): c.execute(q,args); return c.fetchone()
def rows(c, q, args=()): c.execute(q,args); return c.fetchall()
def rate(key, maximum, period):
    with lock:
        stamp=time.monotonic()
        if len(limits)>10000:
            for k in list(limits):
                if not limits[k] or stamp-limits[k][-1]>3600: del limits[k]
        queue=limits[key]
        while queue and stamp-queue[0]>period: queue.popleft()
        if len(queue)>=maximum: fail('Please wait before trying again.',429)
        queue.append(stamp)
def identity(request,c):
    auth=request.headers.get('authorization','')
    if not re.fullmatch(r'Bearer [a-f0-9]{64}',auth): fail('Link your launcher in-game first.',401)
    row=one(c,'SELECT a.* FROM doa_social_sessions s JOIN doa_social_accounts a ON a.id=s.account_id WHERE s.token_hash=%s AND s.expires>%s',(digest(auth[7:]),now()))
    if not row: fail('Your session expired. Link again in-game.',401)
    return row
def pair(a,b): return tuple(sorted((a,b)))
def friendship(c,a,b): return one(c,'SELECT * FROM doa_social_friends WHERE a=%s AND b=%s',pair(a,b))
def clean(value, size):
    if not isinstance(value,str): fail('Text is required.')
    value=''.join(x for x in value.strip() if ord(x)>=32 and ord(x)!=127)
    if not value or len(value)>size: fail(f'Use between 1 and {size} characters.')
    return value
@app.middleware('http')
async def guard(request:Request,call_next):
    try:
        if request.method=='POST' and 'content-length' not in request.headers: return JSONResponse({'detail':'Content length required.'},411)
        if int(request.headers.get('content-length','0'))>4096: return JSONResponse({'detail':'Request too large.'},413)
        rate('ip:'+request.client.host,180,60)
        if request.method=='POST':
            data=b''
            async for chunk in request.stream():
                data+=chunk
                if len(data)>4096: return JSONResponse({'detail':'Request too large.'},413)
            request._body=data
    except HTTPException as e: return JSONResponse({'detail':e.detail},e.status_code)
    except ValueError: return JSONResponse({'detail':'Invalid request.'},400)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response
@app.exception_handler(pymysql.MySQLError)
async def database_error(request,exc): return JSONResponse({'detail':'Service temporarily unavailable.'},503)
class Link(BaseModel): code:str=Field(min_length=12,max_length=32)
class Action(BaseModel):
    action:str=Field(max_length=24)
    target:str=Field(default='',max_length=80)
    text:str=Field(default='',max_length=400)
    channel:str=Field(default='global',max_length=12)
@app.get('/api/status')
def status():
    with db() as c:
        state=one(c,'SELECT * FROM doa_social_state WHERE id=1')
        active=state and now()-state['updated']<15
        lobbies=json.loads(state['payload']) if active else []
        public=[{k:v for k,v in lobby.items() if k not in ('code','private')} for lobby in lobbies if not lobby.get('private')]
        return {'online':bool(active),'server':'Dead or Alive','address':'45.14.187.72:30120','lobbies':public}
@app.post('/api/link')
def link(body:Link,request:Request):
    rate('link:'+request.client.host,8,300)
    code=body.code.replace('-','').upper()
    if not re.fullmatch('[A-F0-9]{12}',code): fail('Enter the code shown in-game.')
    with db() as c:
        row=one(c,'SELECT * FROM doa_social_links WHERE code_hash=%s AND expires>%s FOR UPDATE',(digest(code),now()))
        if not row: fail('Code expired or already used.')
        c.execute('DELETE FROM doa_social_links WHERE code_hash=%s',(digest(code),))
        # Limit active devices to five; never log or persist raw bearer tokens on the VPS.
        sessions=rows(c,'SELECT token_hash FROM doa_social_sessions WHERE account_id=%s ORDER BY expires DESC',(row['account_id'],))
        for old in sessions[4:]: c.execute('DELETE FROM doa_social_sessions WHERE token_hash=%s',(old['token_hash'],))
        token=secrets.token_hex(32)
        c.execute('INSERT INTO doa_social_sessions VALUES(%s,%s,%s)',(digest(token),row['account_id'],now()+30*86400))
        return {'token':token}
@app.get('/api/state')
def state(request:Request):
    with db() as c:
        me=identity(request,c)
        friends=rows(c,'SELECT f.*,p.id,p.name,p.online_at FROM doa_social_friends f JOIN doa_social_accounts p ON p.id=IF(f.a=%s,f.b,f.a) WHERE f.a=%s OR f.b=%s',(me['id'],me['id'],me['id']))
        guild=one(c,'SELECT * FROM doa_social_guilds WHERE id=%s',(me['guild_id'],)) if me['guild_id'] else None
        if guild: guild['members']=rows(c,'SELECT id,name,online_at FROM doa_social_accounts WHERE guild_id=%s',(guild['id'],))
        return {'me':{k:me[k] for k in ('id','name','guild_id')},'friends':friends,'guild':guild,
            'invites':rows(c,'SELECT g.* FROM doa_social_guild_invites i JOIN doa_social_guilds g ON g.id=i.guild_id WHERE i.account_id=%s',(me['id'],)),
            'players':rows(c,'SELECT id,name,online_at FROM doa_social_accounts WHERE id<>%s ORDER BY online_at DESC,name LIMIT 200',(me['id'],)),
            'commands':rows(c,'SELECT id,status FROM doa_social_commands WHERE account_id=%s ORDER BY id DESC LIMIT 3',(me['id'],)), 'time':now()}
@app.get('/api/messages')
def messages(request:Request,channel:str='global',target:str='',after:int=0):
    with db() as c:
        me=identity(request,c)
        if channel=='guild':
            if not me['guild_id']: fail('Join a guild first.',403)
            target=me['guild_id']
        elif channel=='dm':
            friend=friendship(c,me['id'],target)
            if not friend or friend['status']!='accepted': fail('Private chat requires an accepted friend.',403)
            target=':'.join(pair(me['id'],target))
        elif channel!='global': fail('Unknown channel.')
        else: target=''
        result=rows(c,'SELECT id,sender,name,body,created FROM doa_social_messages WHERE channel=%s AND target=%s AND id>%s ORDER BY id DESC LIMIT 80',(channel,target,max(0,after)))
        return list(reversed(result))
@app.post('/api/action')
def action(body:Action,request:Request):
    with db() as c:
        me=identity(request,c); uid=me['id']; op=body.action; target=body.target
        rate('action:'+uid,40,60)
        if op=='logout':
            c.execute('DELETE FROM doa_social_sessions WHERE token_hash=%s',(digest(request.headers['authorization'][7:]),)); return {'ok':True}
        if op=='message':
            rate('message:'+uid,1,2); text=clean(body.text,400); channel=body.channel
            if channel=='guild':
                if not me['guild_id']: fail('Join a guild first.',403)
                target=me['guild_id']
            elif channel=='dm':
                f=friendship(c,uid,target)
                if not f or f['status']!='accepted': fail('Only accepted friends can send private messages.',403)
                target=':'.join(pair(uid,target))
            elif channel=='global': target=''
            else: fail('Unknown channel.')
            c.execute('INSERT INTO doa_social_messages(sender,name,channel,target,body,created) VALUES(%s,%s,%s,%s,%s,%s)',(uid,me['name'],channel,target,text,now()))
        elif op in ('friend','accept','remove','block'):
            if target==uid or not one(c,'SELECT id FROM doa_social_accounts WHERE id=%s',(target,)): fail('Choose another player.')
            a,b=pair(uid,target); f=friendship(c,uid,target)
            if op=='friend':
                if f: fail('A friendship, request, or block already exists.')
                c.execute('INSERT INTO doa_social_friends(a,b,requester) VALUES(%s,%s,%s)',(a,b,uid))
            elif op=='accept':
                if not f or f['status']!='pending' or f['requester']==uid: fail('No incoming request.')
                c.execute("UPDATE doa_social_friends SET status='accepted' WHERE a=%s AND b=%s",(a,b))
            elif op=='block': c.execute("INSERT INTO doa_social_friends VALUES(%s,%s,%s,'blocked') ON DUPLICATE KEY UPDATE requester=VALUES(requester),status='blocked'",(a,b,uid))
            else:
                if f and f['status']=='blocked' and f['requester']!=uid: fail('This player is unavailable.',403)
                c.execute('DELETE FROM doa_social_friends WHERE a=%s AND b=%s',(a,b))
        elif op=='guildCreate':
            rate('guild:'+uid,3,3600)
            if me['guild_id']: fail('Leave your current guild first.')
            name=clean(body.text,40); gid=secrets.token_hex(8)
            c.execute('SELECT id FROM doa_social_accounts WHERE id=%s FOR UPDATE',(uid,))
            if one(c,'SELECT guild_id FROM doa_social_accounts WHERE id=%s',(uid,))['guild_id']: fail('Already in a guild.')
            if one(c,'SELECT id FROM doa_social_guilds WHERE name=%s',(name,)): fail('Guild name already taken.')
            c.execute('INSERT INTO doa_social_guilds VALUES(%s,%s,%s)',(gid,name,uid)); c.execute('UPDATE doa_social_accounts SET guild_id=%s WHERE id=%s',(gid,uid))
        elif op=='guildInvite':
            guild=one(c,'SELECT * FROM doa_social_guilds WHERE id=%s AND owner_id=%s',(me['guild_id'],uid))
            f=friendship(c,uid,target)
            if not guild or not f or f['status']!='accepted': fail('Only the owner can invite accepted friends.',403)
            c.execute('INSERT IGNORE INTO doa_social_guild_invites VALUES(%s,%s)',(guild['id'],target))
        elif op=='guildAccept':
            account=one(c,'SELECT * FROM doa_social_accounts WHERE id=%s FOR UPDATE',(uid,))
            if account['guild_id'] or not one(c,'SELECT * FROM doa_social_guild_invites WHERE guild_id=%s AND account_id=%s',(target,uid)): fail('Invitation unavailable.')
            c.execute('UPDATE doa_social_accounts SET guild_id=%s WHERE id=%s',(target,uid)); c.execute('DELETE FROM doa_social_guild_invites WHERE account_id=%s',(uid,))
        elif op in ('guildLeave','guildKick'):
            guild=one(c,'SELECT * FROM doa_social_guilds WHERE id=%s',(me['guild_id'],))
            if not guild: fail('No guild.')
            if op=='guildKick':
                if guild['owner_id']!=uid or target==uid: fail('Only the owner can remove another member.',403)
                c.execute('UPDATE doa_social_accounts SET guild_id=NULL WHERE id=%s AND guild_id=%s',(target,guild['id']))
            elif guild['owner_id']==uid:
                c.execute('UPDATE doa_social_accounts SET guild_id=NULL WHERE guild_id=%s',(guild['id'],)); c.execute('DELETE FROM doa_social_guild_invites WHERE guild_id=%s',(guild['id'],)); c.execute('DELETE FROM doa_social_guilds WHERE id=%s',(guild['id'],))
            else: c.execute('UPDATE doa_social_accounts SET guild_id=NULL WHERE id=%s',(uid,))
        elif op=='join':
            rate('join:'+uid,1,5)
            rate('join-hour:'+uid,40,3600)
            snapshot=one(c,'SELECT * FROM doa_social_state WHERE id=1')
            if not snapshot or now()-snapshot['updated']>15: fail('Server is offline.')
            lobbies=json.loads(snapshot['payload'])
            if target.startswith('code:'):
                code=target[5:].upper()
                if not re.fullmatch('[A-F0-9]{6}',code): fail('Use the six-character code shown in your friend’s in-game lobby.')
                lobby=next((x for x in lobbies if secrets.compare_digest(str(x.get('code','')),code)),None)
                if not lobby: fail('Lobby code unavailable or expired.')
                target=str(lobby['id'])+':code:'+code
            elif not any(str(x['id'])==target and not x.get('private') for x in lobbies): fail('Lobby no longer available.')
            c.execute("UPDATE doa_social_commands SET status='replaced' WHERE account_id=%s AND status='pending'",(uid,))
            c.execute("INSERT INTO doa_social_commands(account_id,action,target,created) VALUES(%s,'join',%s,%s)",(uid,target,now()))
        else: fail('Unknown action.')
    return {'ok':True}
if __name__=='__main__':
    import uvicorn
    log_config={'version':1,'disable_existing_loggers':False,'handlers':{'file':{'class':'logging.handlers.RotatingFileHandler','filename':'C:/RedM-Setup/launcher-private/service.log','maxBytes':2000000,'backupCount':3}},'loggers':{'uvicorn':{'handlers':['file'],'level':'INFO','propagate':False},'uvicorn.error':{'handlers':['file'],'level':'INFO','propagate':False}}}
    uvicorn.run(app,host='0.0.0.0',port=config['port'],ssl_certfile=config['certificate'],ssl_keyfile=config['key'],limit_concurrency=100,timeout_keep_alive=5,access_log=False,log_config=log_config)
