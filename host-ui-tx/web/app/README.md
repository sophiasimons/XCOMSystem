# XCOM Web App (static)

This is a small, self-contained static web app you can open in a browser to prototype the UI.

Features:
- Simulation mode (generates telemetry) for development without hardware.
- Bridge mode: connects to a local bridge WebSocket at ws://127.0.0.1:8765 and sends JSON messages.
- Simple telemetry chart (Chart.js CDN) and command buttons.

Run locally:

1) Quick (file): open `index.html` directly in a modern browser. Some browsers restrict local WebSocket permissions; using a local server is more reliable.

2) Recommended: serve with a simple static server (Python):

```bash
cd host-ui/web/app
python3 -m http.server 8000
# open http://127.0.0.1:8000 in your browser
```

3) Use with the bridge (run bridge on host or container):

 - Start the bridge (host):
   ```bash
   cd host-ui/bridge
   source .venv/bin/activate
   pip install -r requirements.txt
   python bridge.py --ws-port 8765
   ```

 - Or run the container:
   ```bash
   docker run --rm -p 8765:8765 xcom-bridge:latest
   ```

Then select "Connect to Bridge" and click Connect in the UI.
