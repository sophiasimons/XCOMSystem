# host-ui

This folder contains a minimal host bridge (Python) and a simple static web popup UI that connects to it via WebSocket.

Structure:
- bridge/: Python bridge that exposes a WebSocket server and relays to serial. Includes a Dockerfile and helper to build a container image.
- web/public/: Static web UI (index + popup) that talks to the bridge.
- desktop-electron/: Electron-based desktop popup app (standalone, no webserver required).
- scripts/: helper scripts to package the Electron app and build images.

Packaging/build scripts location
 - Put scripts that build container images or package native apps in `host-ui/scripts/`.
 - Dockerfile(s) for containerized components live next to each component (e.g. `host-ui/bridge/Dockerfile`).

See `bridge/README.md` and `desktop-electron/README.md` for run and packaging instructions.
