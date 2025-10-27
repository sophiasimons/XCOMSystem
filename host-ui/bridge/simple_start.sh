#!/bin/sh
# Start both the bridge and a simple HTTP server for the web UI
python -m http.server 8000 --directory /app/web &
python bridge.py --ws-port 8765