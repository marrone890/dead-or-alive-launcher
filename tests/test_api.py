import configparser, hashlib, importlib.util, json, os, secrets, sys, time
from pathlib import Path
import pymysql, pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture(scope='session')
def api():
    parser=configparser.ConfigParser();parser.read('C:/RedM-Setup/private/admin.cnf');a=parser['client']
    name='doa_social_test_'+secrets.token_hex(6)
    connection={'host':a['host'],'user':a['user'],'password':a['password']}
    con=pymysql.connect(**connection,autocommit=True)
    with con.cursor() as c: c.execute('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4')
    con.select_db(name)
    with con.cursor() as c:
        for statement in (ROOT/'service/schema.sql').read_text().split(';'):
            if statement.strip(): c.execute(statement)
    private=Path('C:/RedM-Setup/launcher-private/test-config.json')
    private.write_text(json.dumps({'database':{**connection,'database':name}}))
    os.environ['DOA_SOCIAL_CONFIG']=str(private)
    spec=importlib.util.spec_from_file_location('companion_api',ROOT/'service/api.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    yield module
    with con.cursor() as c: c.execute('DROP DATABASE `'+name+'`')
    con.close();private.unlink()
@pytest.fixture
def setup(api):
    with api.db() as c:
        for t in ['accounts','links','sessions','friends','guilds','guild_invites','messages','state','commands']: c.execute('DELETE FROM doa_social_'+t)
        for x in ['a','b','c']:
            uid=x*16;token=x*64
            c.execute('INSERT INTO doa_social_accounts(id,identifier,name) VALUES(%s,%s,%s)',(uid,'license:'+x,'Player '+x))
            c.execute('INSERT INTO doa_social_sessions VALUES(%s,%s,%s)',(api.digest(token),uid,api.now()+3600))
    api.limits.clear()
    return TestClient(api.app)
def headers(x='a'): return {'Authorization':'Bearer '+x*64}
def action(client,op,x='a',**kw): return client.post('/api/action',json={'action':op,**kw},headers=headers(x))
def test_no_unauthenticated_access(setup):
    c=setup
    assert c.get('/api/status').status_code==200
    assert c.get('/api/state').status_code==401
    assert c.get('/api/messages').status_code==401
    assert c.post('/api/action',json={'action':'message','text':'forged'}).status_code==401
def test_link_code_is_expiring_and_single_use(setup,api):
    with api.db() as c:
        c.execute('INSERT INTO doa_social_links VALUES(%s,%s,%s)',(api.digest('123456ABCDEF'),'a'*16,api.now()+60))
        c.execute('INSERT INTO doa_social_links VALUES(%s,%s,%s)',(api.digest('000000ABCDEF'),'a'*16,api.now()-1))
    c=setup
    assert c.post('/api/link',json={'code':'0000-00AB-CDEF'}).status_code==400
    r=c.post('/api/link',json={'code':'1234-56AB-CDEF'});assert r.status_code==200
    token=r.json()['token'];assert len(token)==64
    assert c.post('/api/link',json={'code':'1234-56AB-CDEF'}).status_code==400
    assert c.get('/api/state',headers={'Authorization':'Bearer '+token}).status_code==200
    with api.db() as q: assert api.one(q,'SELECT * FROM doa_social_sessions WHERE token_hash=%s',(token,)) is None
def test_dm_requires_mutual_friendship_and_blocks_revoke_access(setup,api):
    c=setup
    assert action(c,'message',channel='dm',target='b'*16,text='private').status_code==403
    assert action(c,'friend',target='b'*16).status_code==200
    assert action(c,'accept',target='b'*16).status_code==400
    assert action(c,'accept','b',target='a'*16).status_code==200
    api.limits.clear()
    assert action(c,'message',channel='dm',target='b'*16,text='private 😀').status_code==200
    assert c.get('/api/messages?channel=dm&target='+'a'*16,headers=headers('b')).json()[0]['body']=='private 😀'
    assert c.get('/api/messages?channel=dm&target='+'a'*16,headers=headers('c')).status_code==403
    assert action(c,'block','b',target='a'*16).status_code==200
    assert c.get('/api/messages?channel=dm&target='+'b'*16,headers=headers()).status_code==403
    assert action(c,'remove',target='b'*16).status_code==403
def test_guild_permissions_and_private_history(setup,api):
    c=setup
    assert action(c,'guildCreate',text='Frontier Guild').status_code==200
    guild=c.get('/api/state',headers=headers()).json()['guild']['id']
    assert action(c,'guildAccept','b',target=guild).status_code==400
    assert action(c,'friend',target='b'*16).status_code==200
    assert action(c,'accept','b',target='a'*16).status_code==200
    assert action(c,'guildInvite',target='b'*16).status_code==200
    assert action(c,'guildAccept','b',target=guild).status_code==200
    assert action(c,'message',channel='guild',text='guild secret').status_code==200
    assert c.get('/api/messages?channel=guild',headers=headers('b')).json()[0]['body']=='guild secret'
    assert c.get('/api/messages?channel=guild',headers=headers('c')).status_code==403
    assert action(c,'guildKick','b',target='a'*16).status_code==403
    assert action(c,'guildKick',target='b'*16).status_code==200
    assert c.get('/api/messages?channel=guild',headers=headers('b')).status_code==403
def test_lobby_join_checks_current_public_snapshot(setup,api):
    c=setup
    assert action(c,'join',target='forged').status_code==400
    api.limits.clear()
    with api.db() as q:q.execute('INSERT INTO doa_social_state VALUES(1,%s,%s)',(json.dumps([{'id':'epoch:7','name':'Public'}]),api.now()))
    assert action(c,'join',target='epoch:7').status_code==200
    with api.db() as q:
        cmd=api.one(q,'SELECT * FROM doa_social_commands')
        assert cmd['account_id']=='a'*16 and cmd['target']=='epoch:7'
def test_rate_limits_lengths_and_unknown_actions(setup,api):
    c=setup
    assert action(c,'message',text='hello').status_code==200
    assert action(c,'message',text='spam').status_code==429
    api.limits.clear()
    assert action(c,'message',text='x'*401).status_code==422
    assert action(c,'message',text=' \n ').status_code==400
    assert action(c,'execute',text='os command').status_code==400
    assert c.post('/api/action',content='x'*5000).status_code==413
def test_private_lobbies_require_code_and_never_expose_it(setup,api):
    c=setup
    with api.db() as q:q.execute('INSERT INTO doa_social_state VALUES(1,%s,%s)',(json.dumps([{'id':'epoch:9','name':'Private name','private':True,'code':'A1B2C3'}]),api.now()))
    public=c.get('/api/status').json()
    assert public['lobbies']==[] and 'A1B2C3' not in json.dumps(public)
    assert action(c,'join',target='epoch:9').status_code==400
    api.limits.clear()
    assert action(c,'join',target='code:A1B2C3').status_code==200
    with api.db() as q:assert api.one(q,'SELECT target FROM doa_social_commands')['target']=='epoch:9:code:A1B2C3'
def test_state_never_exposes_identifiers_or_session_tokens(setup):
    result=setup.get('/api/state',headers=headers()).text
    assert 'license:' not in result and 'token_hash' not in result and 'identifier' not in result
def test_logout_revokes_session(setup):
    assert action(setup,'logout').status_code==200
    assert setup.get('/api/state',headers=headers()).status_code==401
