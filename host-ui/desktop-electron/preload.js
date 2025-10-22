// Preload can expose safe APIs using contextBridge if needed.
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  // placeholder for future native APIs
})
