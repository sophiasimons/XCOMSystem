# XCOM Desktop Popup (Electron)

Minimal Electron app that opens a popup window and connects to the local bridge via WebSocket.

Install & run (macOS, zsh):

```bash
cd host-ui/desktop-electron
# install electron locally (npm or yarn)
npm install
npm start
```

Note: you need Node.js and npm installed. This app connects to the bridge at ws://127.0.0.1:8765 by default.
