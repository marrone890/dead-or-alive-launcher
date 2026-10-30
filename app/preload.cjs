const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('companion',{call:(op,payload)=>ipcRenderer.invoke('companion',op,payload)});
