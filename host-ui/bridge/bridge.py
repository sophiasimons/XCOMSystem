#!/usr/bin/env python3
"""Simple host bridge that exposes a WebSocket server and relays messages to a serial port.

Usage:
  python bridge.py --port /dev/tty.usbserial-XXXX --baud 115200 --ws-port 8765

If --port is omitted the bridge will run in simulated mode and echo messages.
"""
import argparse
import asyncio
import json
import logging
from websockets import serve

try:
    import serial_asyncio
except Exception:
    serial_asyncio = None

LOG = logging.getLogger("bridge")


class SerialRelay:
    def __init__(self, serial_port=None, baud=115200):
        self.serial_port = serial_port
        self.baud = baud
        self.transport = None
        self.protocol = None

    async def connect(self):
        if not self.serial_port:
            LOG.info("Running in simulated mode (no serial port)")
            return
        if serial_asyncio is None:
            raise RuntimeError("serial_asyncio (pyserial-asyncio) not available")
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await serial_asyncio.open_serial_connection(url=self.serial_port, baudrate=self.baud)
        LOG.info("Connected to serial %s @ %s", self.serial_port, self.baud)

    async def write(self, data: bytes):
        if self.transport:
            self.transport.write(data)
        else:
            LOG.debug("Simulated write: %r", data)


async def ws_handler(websocket, path, relay: SerialRelay):
    LOG.info("Client connected: %s", websocket.remote_address)
    try:
        async for msg in websocket:
            LOG.debug("WS received: %s", msg)
            # Expect JSON messages with {"type":"raw","data":"..."}
            try:
                obj = json.loads(msg)
                if obj.get("type") == "raw":
                    data = obj.get("data", "")
                    if isinstance(data, str):
                        data = data.encode()
                    await relay.write(data)
                    # echo back
                    await websocket.send(json.dumps({"type":"ack","len":len(data)}))
                else:
                    await websocket.send(json.dumps({"type":"error","message":"unknown type"}))
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type":"error","message":"invalid json"}))
    except Exception as e:
        LOG.info("WS client disconnected: %s", e)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="Serial port device path (e.g. /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--ws-port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    relay = SerialRelay(serial_port=args.port, baud=args.baud)
    await relay.connect()

    async def handler(ws, path):
        await ws_handler(ws, path, relay)

    async with serve(handler, "127.0.0.1", args.ws_port):
        LOG.info("WebSocket bridge listening on ws://127.0.0.1:%s", args.ws_port)
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting")
