const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isDesktop: true,
  platform: process.platform,
  closeApp: () => ipcRenderer.send('app-close'),
  minimizeApp: () => ipcRenderer.send('app-minimize'),
  maximizeApp: () => ipcRenderer.send('app-maximize'),
});
