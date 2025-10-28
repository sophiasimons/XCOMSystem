#!/usr/bin/env python3
"""XCOM Bridge: WebSocket server that handles file transfers to STM32.

Usage:
  python bridge.py --port /dev/tty.usbserial-XXXX --baud 115200 --ws-port 8765

If --port is omitted the bridge will run in simulated mode and echo messages.
"""

import base64
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from aiohttp import web
from websockets import serve
from file_transfer import FileTransfer, create_chunk_validator

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
        self._is_connected = False
        self.file_transfer = FileTransfer()

    async def test_connection(self):
        """Test if we can connect to the STM32 device and verify it's an STM32."""
        if not self.serial_port:
            return {"connected": False, "reason": "No USB device detected"}
        
        try:
            if serial_asyncio is None:
                return {"connected": False, "reason": "Serial communication not available"}
                
            # Try to open the port
            loop = asyncio.get_running_loop()
            transport, protocol = await serial_asyncio.open_serial_connection(
                url=self.serial_port, 
                baudrate=self.baud
            )
            
            # TODO: Add specific STM32 detection here if needed
            # For now, we assume if we can open the port, it's our device
            
            # If we got here, connection successful
            transport.close()
            return {
                "connected": True,
                "port": self.serial_port,
                "baud": self.baud
            }
            
        except Exception as e:
            LOG.error("Failed to connect to STM32: %s", e)
            return {
                "connected": False,
                "reason": f"Connection failed: {str(e)}"
            }

    async def connect(self):
        if not self.serial_port:
            LOG.info("Running in simulated mode (no serial port)")
            return
        
        if serial_asyncio is None:
            raise RuntimeError("serial_asyncio (pyserial-asyncio) not available")
            
        loop = asyncio.get_running_loop()
        try:
            self.transport, self.protocol = await serial_asyncio.open_serial_connection(
                url=self.serial_port, 
                baudrate=self.baud
            )
            self._is_connected = True
            LOG.info("Connected to STM32 at %s @ %s", self.serial_port, self.baud)
        except Exception as e:
            self._is_connected = False
            LOG.error("Failed to connect to STM32: %s", e)
            raise

    async def write(self, data: bytes):
        if self.transport:
            # Add validation bytes
            validated_data = data + create_chunk_validator(data)
            self.transport.write(validated_data)
        else:
            LOG.debug("Simulated write: %r", data)

    async def send_file(self, file_data: bytes, filename: str):
        """Send a file to the STM32 in chunks"""
        # Prepare the file for transfer
        self.file_transfer.prepare_file(file_data, filename)
        
        # Send header first
        header = self.file_transfer.get_header()
        await self.write(header)
        await asyncio.sleep(0.1)  # Give STM32 time to process

        # Send chunks
        while True:
            chunk_data = self.file_transfer.get_next_chunk()
            if chunk_data is None:
                break
                
            chunk, chunk_num = chunk_data
            await self.write(chunk)
            LOG.info(f"Sent chunk {chunk_num}")
            await asyncio.sleep(0.05)  # Rate limiting
            
        LOG.info(f"File transfer complete: {filename}")


async def ws_handler(websocket, path, relay: SerialRelay):
    LOG.info("Client connected: %s", websocket.remote_address)
    try:
        async for msg in websocket:
            LOG.debug("WS received: %s", msg)
            try:
                obj = json.loads(msg)
                msg_type = obj.get("type", "")
                
                if msg_type == "check_connection":
                    # Check if we can connect to the STM32
                    connection_status = await relay.test_connection()
                    response = {
                        "type": "connection_status",
                        **connection_status  # This unpacks all the status information
                    }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == "file_upload":
                    # Handle file upload
                    if not relay._is_connected and not await relay.test_connection():
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "STM32 device not connected"
                        }))
                        continue

                    filename = obj.get("filename", "")
                    size = obj.get("size", 0)
                    data = obj.get("data", "")
                    
                    try:
                        # Convert base64 data to bytes and send to STM32
                        if isinstance(data, str):
                            import base64
                            data = base64.b64decode(data.split(',')[1])
                        await relay.write(data)
                        await websocket.send(json.dumps({
                            "type": "upload_success",
                            "filename": filename,
                            "size": len(data)
                        }))
                    except Exception as e:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Failed to send file: {str(e)}"
                        }))
                
                elif msg_type == "raw":
                    data = obj.get("data", "")
                    if isinstance(data, str):
                        data = data.encode()
                    await relay.write(data)
                    await websocket.send(json.dumps({"type":"ack","len":len(data)}))
                
                else:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "unknown message type"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "invalid json"
                }))
    except Exception as e:
        LOG.info("WS client disconnected: %s", e)


async def start_web_server(host, port):
    app = web.Application()
    # Serve files from the mounted web directory
    web_dir = Path('/usr/src/app/web/app')
    LOG.info("Looking for web files in: %s", web_dir)
    if not web_dir.exists():
        LOG.error("Web directory not found at %s", web_dir)
        return
        
    async def index_handler(request):
        return web.FileResponse(web_dir / 'index.html')
        
    # Serve static files
    app.router.add_get('/', index_handler)
    app.router.add_static('/', web_dir)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    LOG.info("Web UI server running at http://%s:%s", host, port)
    return runner

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="Serial port device path (e.g. /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--ws-port", type=int, default=8765)
    parser.add_argument("--web-port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    relay = SerialRelay(serial_port=args.port, baud=args.baud)
    await relay.connect()

    # Start web server for UI
    web_runner = await start_web_server(args.host, args.web_port)

    async def handler(ws, path):
        await ws_handler(ws, path, relay)

    async with serve(handler, args.host, args.ws_port):
        LOG.info("WebSocket bridge listening on ws://%s:%s", args.host, args.ws_port)
        try:
            await asyncio.Future()  # run forever
        finally:
            await web_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting")
