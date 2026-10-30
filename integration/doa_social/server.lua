local ready=false
local lastMessage,lastLink={},{}
local cursor=0
local chatHooked=false
local function notice(src,text)
 TriggerClientEvent('chat:addMessage',src,{color={210,229,150},args={'Dead or Alive',text}})
end
local function identifier(src) return GetPlayerIdentifierByType(src,'license') end
local function account(src)
 local key=identifier(src);if not key then return nil end
 local name=(GetPlayerName(src) or 'Soldier'):gsub('[%c]',''):sub(1,80)
 MySQL.insert.await('INSERT INTO doa_social_accounts(id,identifier,name,online_at,source_id) VALUES(LOWER(HEX(RANDOM_BYTES(8))),?,?,?,?) ON DUPLICATE KEY UPDATE name=VALUES(name),online_at=VALUES(online_at),source_id=VALUES(source_id)',{key,name,os.time(),src})
 return MySQL.single.await('SELECT * FROM doa_social_accounts WHERE identifier=?',{key})
end
local function send(src,channel,text,target)
 if not ready or type(text)~='string' then return end
 text=text:gsub('[%c]',''):match('^%s*(.-)%s*$')
 if text=='' or #text>1600 or utf8.len(text)==nil or utf8.len(text)>400 then return notice(src,'Messages must contain 1–400 characters.') end
 if GetGameTimer()-(lastMessage[src] or -10000)<2000 then return notice(src,'Please wait before sending another message.') end
 lastMessage[src]=GetGameTimer()
 local a=account(src);if not a then return end
 local destination=''
 if channel=='guild' then
  if not a.guild_id then return notice(src,'Join a guild in the launcher first.') end
  destination=a.guild_id
 elseif channel=='dm' then
  if not target or not GetPlayerName(target) then return notice(src,'That player is not online.') end
  local b=account(target);if not b or b.id==a.id then return end
  local x,y=a.id,b.id;if x>y then x,y=y,x end
  local f=MySQL.single.await('SELECT status FROM doa_social_friends WHERE a=? AND b=?',{x,y})
  if not f or f.status~='accepted' then return notice(src,'Private messages require an accepted launcher friend.') end
  destination=x..':'..y
 end
 MySQL.insert.await('INSERT INTO doa_social_messages(sender,name,channel,target,body,created) VALUES(?,?,?,?,?,?)',{a.id,a.name,channel,destination,text,os.time()})
end
local function installChatHook()
 if not ready or chatHooked or GetResourceState('chat')~='started' then return end
 exports.chat:registerMessageHook(function(src,out,hook)
  if src>0 and (not out.mode or out.mode=='all' or out.mode=='_global') then
   hook.cancel();CreateThread(function() send(src,'global',out.args[#out.args]) end)
  end
 end)
 chatHooked=true
end
AddEventHandler('onResourceStop',function(resource) if resource=='chat' then chatHooked=false end end)
AddEventHandler('onResourceStart',function(resource) if resource=='chat' then CreateThread(function() Wait(0);installChatHook() end) end end)
RegisterCommand('launcher',function(src,args)
 if src==0 or not ready then return end
 if GetGameTimer()-(lastLink[src] or -60000)<10000 then return notice(src,'Please wait before requesting another code.') end
 lastLink[src]=GetGameTimer()
 local a=account(src);if not a then return end
 MySQL.update.await('DELETE FROM doa_social_links WHERE account_id=?',{a.id})
 if args[1]=='revoke' then
  MySQL.update.await('DELETE FROM doa_social_sessions WHERE account_id=?',{a.id})
  return notice(src,'Every launcher session has been signed out.')
 end
 local code=MySQL.scalar.await('SELECT HEX(RANDOM_BYTES(6))')
 MySQL.insert.await('INSERT INTO doa_social_links VALUES(SHA2(?,256),?,?)',{code,a.id,os.time()+300})
 notice(src,'Your launcher link code: '..code:sub(1,4)..'-'..code:sub(5,8)..'-'..code:sub(9)..' (valid 5 minutes). Enter it only in the official launcher. Do not share it.')
end,false)
RegisterCommand('g',function(src,args) if src>0 then send(src,'guild',table.concat(args,' ')) end end,false)
RegisterCommand('w',function(src,args)
 if src>0 then local target=tonumber(table.remove(args,1));send(src,'dm',table.concat(args,' '),target) end
end,false)
AddEventHandler('playerDropped',function()
 lastMessage[source]=nil;lastLink[source]=nil
 if ready then MySQL.update('UPDATE doa_social_accounts SET online_at=0,source_id=NULL WHERE identifier=?',{identifier(source) or ''}) end
end)
MySQL.ready(function()
 CreateThread(function()
  if not MySQL.scalar.await("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='doa_social_accounts'") then return end
  cursor=tonumber(MySQL.scalar.await('SELECT COALESCE(MAX(id),0) FROM doa_social_messages')) or 0
  ready=true
  installChatHook()
  while ready do
   local ok,err=pcall(function()
    local online={}
    for _,sid in ipairs(GetPlayers()) do local src=tonumber(sid);local a=account(src);if a then online[a.id]={src=src,guild=a.guild_id} end end
    local lobbies=exports.doa_pvp:LauncherLobbies()
    MySQL.insert.await('INSERT INTO doa_social_state VALUES(1,?,?) ON DUPLICATE KEY UPDATE payload=VALUES(payload),updated=VALUES(updated)',{#lobbies==0 and '[]' or json.encode(lobbies),os.time()})
    local messages=MySQL.query.await('SELECT * FROM doa_social_messages WHERE id>? ORDER BY id LIMIT 200',{cursor})
    for _,m in ipairs(messages) do
     cursor=m.id
     for id,player in pairs(online) do
      local allowed=m.channel=='global' or (m.channel=='guild' and player.guild==m.target)
      if m.channel=='dm' and (m.target:sub(1,16)==id or m.target:sub(18)==id) then
       local f=MySQL.single.await("SELECT status FROM doa_social_friends WHERE a=? AND b=?",{m.target:sub(1,16),m.target:sub(18)})
       allowed=f and f.status=='accepted'
      end
      if allowed then TriggerClientEvent('chat:addMessage',player.src,{color=m.channel=='global' and {210,229,150} or {170,185,245},args={'['..m.channel:upper()..'] '..m.name,m.body}}) end
     end
    end
    local commands=MySQL.query.await("SELECT * FROM doa_social_commands WHERE status='pending' ORDER BY id LIMIT 100")
    for _,cmd in ipairs(commands) do
     local result
     if os.time()-cmd.created>300 then result='expired'
     elseif online[cmd.account_id] then result=exports.doa_pvp:LauncherJoin(online[cmd.account_id].src,cmd.target) end
     if result then MySQL.update.await('UPDATE doa_social_commands SET status=? WHERE id=?',{result,cmd.id}) end
    end
   end)
   if not ok then print('Companion synchronization failed; retrying. '..tostring(err):sub(1,120)) end
   Wait(2000)
  end
 end)
end)
