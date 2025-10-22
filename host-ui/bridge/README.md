# Host Bridge (Python)

This is a minimal host bridge that exposes a WebSocket server to local web UIs and relays messages to a serial port (or runs in simulated mode if no serial port is provided).

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run:

```bash
python bridge.py --port /dev/tty.usbserial-XXXX --baud 115200 --ws-port 8765
# or simulated mode:
python bridge.py --ws-port 8765
```
