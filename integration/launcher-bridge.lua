-- Server-only launcher bridge. No network event can call these exports directly.
local launcherEpoch=tostring(os.time())..'-'..tostring(math.random(100000,999999))
exports('LauncherLobbies',function()
 local list={}
 for _,p in pairs(parties) do
  if not p.battle and p.phase=='lobby' then
   list[#list+1]={id=launcherEpoch..':'..p.id,name=p.name,mode=p.mode,map=p.map,count=DOA.count(p.members),max=Config.MaxParty,private=p.private,code=p.code}
  end
 end
 return list
end)
exports('LauncherJoin',function(src,target)
 if GetInvokingResource()~='doa_social' then return 'denied' end
 if not valid(src) then return nil end
 local raw=tostring(target)
 local public,code=raw:match('^(.-):code:(%x+)$')
 local epoch,id=(public or raw):match('^(.-):(%d+)$')
 local p=epoch==launcherEpoch and parties[tonumber(id)] or nil
 if not p or (p.private and p.code~=code) or p.battle or p.phase~='lobby' or DOA.count(p.members)>=Config.MaxParty then return 'Lobby unavailable' end
 if memberships[src]==p.id then return 'Joined lobby' end
 local current=partyOf(src)
 if creators[src] or training[src] or (current and current.phase~='lobby') then return 'Return to your lobby first' end
 leave(src,true);join(src,p);ensurePersonal(src)
 return memberships[src]==p.id and 'Joined lobby' or 'Unable to join lobby'
end)
