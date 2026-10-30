const {app,BrowserWindow,ipcMain,shell,safeStorage,session}=require('electron');
const fs=require('node:fs'),path=require('node:path'),https=require('node:https'),tls=require('node:tls'),crypto=require('node:crypto');
const config=require('./connection.json');
app.setName('Dead or Alive');
let win,token='';
const agent=new https.Agent({keepAlive:true,maxSockets:4});
agent.createConnection=(options,callback)=>{
 const socket=tls.connect({...options,rejectUnauthorized:false});
 const error=e=>callback(e);
 socket.once('error',error);
 socket.once('secureConnect',()=>{
  const cert=socket.getPeerCertificate();
  const actual=cert.raw&&crypto.createHash('sha256').update(cert.raw).digest();
  const expected=Buffer.from(config.certificateSha256,'hex');
  if(!actual||actual.length!==expected.length||!crypto.timingSafeEqual(actual,expected)||Date.parse(cert.valid_to)<Date.now()){
   socket.destroy();callback(new Error('Server certificate verification failed.'));return;
  }
  socket.removeListener('error',error);callback(null,socket);
 });
};
function request(route,method='GET',body){
 return new Promise((resolve,reject)=>{
  const data=body?JSON.stringify(body):'';
  const req=https.request({host:config.host,port:config.port,path:route,method,agent,
   headers:{...(token?{Authorization:'Bearer '+token}:{}),...(data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{})}},res=>{
    let text='';res.on('data',chunk=>{text+=chunk;if(text.length>1024*1024)req.destroy(new Error('Response too large.'));});
    res.on('end',()=>{try{const value=JSON.parse(text);res.statusCode>=400?reject(new Error(typeof value.detail==='string'?value.detail:'Request failed.')):resolve(value);}catch{reject(new Error('Invalid server response.'));}});
   });
  req.setTimeout(10000,()=>req.destroy(new Error('Server did not respond.')));
  req.on('error',()=>reject(new Error('Cannot establish a verified connection to the community server.')));
  req.end(data);
 });
}
function saveToken(value){
 const file=path.join(app.getPath('userData'),'session.bin');
 if(value){if(!safeStorage.isEncryptionAvailable())throw new Error('Windows credential encryption is unavailable.');fs.writeFileSync(file,safeStorage.encryptString(value));}
 else if(fs.existsSync(file))fs.unlinkSync(file);
 token=value;
}
const actions=new Set(['message','friend','accept','remove','block','guildCreate','guildInvite','guildAccept','guildLeave','guildKick','join','logout']);
if(!app.requestSingleInstanceLock())app.quit();
else {
app.on('second-instance',()=>{if(win){if(win.isMinimized())win.restore();win.focus();}});
app.whenReady().then(()=>{
 try{const file=path.join(app.getPath('userData'),'session.bin');if(fs.existsSync(file)&&safeStorage.isEncryptionAvailable())token=safeStorage.decryptString(fs.readFileSync(file));}catch{token='';}
 session.defaultSession.setPermissionRequestHandler((_wc,_permission,cb)=>cb(false));
 ipcMain.handle('companion',async(event,op,payload={})=>{
  if(event.sender!==win.webContents||event.senderFrame!==win.webContents.mainFrame)throw new Error('Unauthorized frame.');
  if(JSON.stringify(payload).length>4096)throw new Error('Request too large.');
  try {
   if(op==='session')return {linked:!!token};
   if(op==='status')return await request('/api/status');
   if(op==='state')return await request('/api/state');
   if(op==='link') {const result=await request('/api/link','POST',{code:String(payload.code||'')});saveToken(result.token);return {linked:true};}
   if(op==='logout'){try{await request('/api/action','POST',{action:'logout'});}finally{saveToken('');}return {ok:true};}
   if(op==='messages')return await request('/api/messages?'+new URLSearchParams({channel:payload.channel||'global',target:payload.target||''}));
   if(op==='action'&&actions.has(payload.action))return await request('/api/action','POST',payload);
   if(op==='connect'){await shell.openExternal(config.game);return {ok:true};}
   if(op==='discord'){await shell.openExternal('https://discord.com/invite/caVCQcvJMG');return {ok:true};}
   if(op==='website'){await shell.openExternal('https://www.doapvp.it/');return {ok:true};}
   throw new Error('Unsupported action.');
  }catch(error){return {error:error.message};}
 });
 win=new BrowserWindow({width:1140,height:780,minWidth:940,minHeight:670,backgroundColor:'#0b110e',autoHideMenuBar:true,title:'Dead or Alive',icon:path.join(__dirname,'assets/launcher.ico'),
  webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});
 win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 win.webContents.on('will-navigate',event=>event.preventDefault());
 win.loadFile(path.join(__dirname,'index.html'));
 if(process.env.DOA_LAUNCHER_SMOKE){win.webContents.once('did-finish-load',()=>setTimeout(async()=>{fs.writeFileSync(process.env.DOA_LAUNCHER_SMOKE,await win.webContents.capturePage().then(i=>i.toPNG()));app.quit();},4000));}
});
app.on('window-all-closed',()=>app.quit());
}
