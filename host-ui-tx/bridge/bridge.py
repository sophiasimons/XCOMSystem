#!/usr/bin/env python3
"""XCOM Bridge: WebSocket server that handles file transfers to STM32 via Ethernet.

Usage:
  python bridge.py --stm32-ip 192.168.1.100 --stm32-port 5000 --ws-port 8765

If --stm32-ip is omitted the bridge will run in simulated mode and echo messages.
"""

import base64
import argparse
import asyncio
import json
import logging
import socket
from pathlib import Path
from aiohttp import web
from websockets import serve

LOG = logging.getLogger("bridge")


class EthernetRelay:
    def __init__(self, stm32_ip=None, stm32_port=5000):
        self.stm32_ip = stm32_ip
        self.stm32_port = stm32_port
        self._is_connected = False

    async def test_connection(self):
        """Test if we can connect to the STM32 via Ethernet."""
        if not self.stm32_ip:
            return {"connected": False, "reason": "No STM32 IP address configured"}
        
        try:
            # Try to connect with a short timeout
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.stm32_ip, self.stm32_port),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            
            return {
                "connected": True,
                "ip": self.stm32_ip,
                "port": self.stm32_port
            }
            
        except asyncio.TimeoutError:
            LOG.debug("Connection timeout to %s:%s", self.stm32_ip, self.stm32_port)
            return {
                "connected": False,
                "reason": f"Connection timeout to {self.stm32_ip}:{self.stm32_port}"
            }
        except Exception as e:
            LOG.debug("Failed to connect to STM32: %s", e)
            return {
                "connected": False,
                "reason": f"Cannot connect: {str(e)}"
            }

    async def connect(self):
        if not self.stm32_ip:
            LOG.info("Running in simulated mode (no STM32 IP configured)")
            return
            
        try:
            connection_status = await self.test_connection()
            self._is_connected = connection_status.get("connected", False)
            if self._is_connected:
                LOG.info("STM32 reachable at %s:%s", self.stm32_ip, self.stm32_port)
            else:
                LOG.warning("STM32 not reachable at %s:%s", self.stm32_ip, self.stm32_port)
        except Exception as e:
            self._is_connected = False
            LOG.error("Failed to connect to STM32: %s", e)

    async def send_file(self, file_data: bytes, filename: str):
        """Send file to STM32 over Ethernet TCP socket"""
        if not self.stm32_ip:
            LOG.info(f"Simulated send: {filename} ({len(file_data)} bytes)")
            return
            
        try:
            LOG.info(f"Sending {filename} ({len(file_data)} bytes) to {self.stm32_ip}:{self.stm32_port}...")
            
            # Open TCP connection to STM32
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.stm32_ip, self.stm32_port),
                timeout=5.0
            )
            
            # Send file size first (4 bytes, little-endian)
            file_size = len(file_data)
            writer.write(file_size.to_bytes(4, byteorder='little'))
            await writer.drain()
            
            # Send entire file
            writer.write(file_data)
            await writer.drain()
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            LOG.info(f"File transfer complete: {filename}")
                
        except asyncio.TimeoutError:
            LOG.error(f"Timeout sending file to {self.stm32_ip}:{self.stm32_port}")
            raise RuntimeError(f"Connection timeout")
        except Exception as e:
            LOG.error(f"Failed to send file: {e}")
            raise


async def ws_handler(websocket, path, relay: EthernetRelay):
    LOG.info("Client connected: %s", websocket.remote_address)
    try:
        async for msg in websocket:
            LOG.debug("WS received: %s", msg)
            try:
                obj = json.loads(msg)
                msg_type = obj.get("type", "")
                
                if msg_type == "check_connection":
                    # Check if we can connect to the STM32 via Ethernet
                    connection_status = await relay.test_connection()
                    response = {
                        "type": "connection_status",
                        **connection_status  # This unpacks all the status information
                    }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == "file_upload":
                    # Handle file upload
                    if not relay._is_connected and relay.stm32_ip:
                        connection_status = await relay.test_connection()
                        if not connection_status.get("connected"):
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "STM32 device not reachable via Ethernet"
                            }))
                            continue

                    filename = obj.get("filename", "file.bin")
                    size = obj.get("size", 0)
                    data = obj.get("data", "")
                    
                    try:
                        # Convert base64 data to bytes
                        if isinstance(data, str):
                            # Remove data URL prefix if present
                            if ',' in data:
                                data = data.split(',')[1]
                            file_bytes = base64.b64decode(data)
                        else:
                            file_bytes = data
                        
                        # Send file directly via Ethernet
                        await relay.send_file(file_bytes, filename)
                        
                        await websocket.send(json.dumps({
                            "type": "upload_success",
                            "filename": filename,
                            "size": len(file_bytes)
                        }))
                    except Exception as e:
                        LOG.error(f"File upload failed: {e}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Failed to send file: {str(e)}"
                        }))
                
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
    parser.add_argument("--stm32-ip", help="STM32 IP address (e.g. 192.168.1.100)")
    parser.add_argument("--stm32-port", type=int, default=5000, help="STM32 TCP port (default: 5000)")
    parser.add_argument("--ws-port", type=int, default=8765)
    parser.add_argument("--web-port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    relay = EthernetRelay(stm32_ip=args.stm32_ip, stm32_port=args.stm32_port)
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
