#!/usr/bin/env python3
"""XCOM RX Bridge: Receives files from RX STM32 via Ethernet and displays in web UI.

Usage:
  python bridge.py --listen-port 5000 --ws-port 8765

The RX STM32 will connect to this bridge on listen-port and send files.
"""

import base64
import argparse
import asyncio
import json
import logging
from pathlib import Path
from aiohttp import web
from websockets import serve
from datetime import datetime

LOG = logging.getLogger("rx-bridge")


class EthernetReceiver:
    def __init__(self, listen_port=5000):
        self.listen_port = listen_port
        self.last_file = None
        self.last_filename = None
        self.websocket_clients = set()
        
    async def handle_stm32_connection(self, reader, writer):
        """Handle incoming connection from RX STM32"""
        addr = writer.get_extra_info('peername')
        LOG.info(f"RX STM32 connected from {addr}")
        
        try:
            # Receive file size first (4 bytes, little-endian)
            size_bytes = await reader.readexactly(4)
            file_size = int.from_bytes(size_bytes, byteorder='little')
            
            LOG.info(f"Receiving file: {file_size} bytes")
            
            # Receive file data
            file_data = b''
            while len(file_data) < file_size:
                chunk = await reader.read(min(4096, file_size - len(file_data)))
                if not chunk:
                    break
                file_data += chunk
                
                # Show progress
                if len(file_data) % 10240 == 0:
                    progress = (len(file_data) * 100) // file_size
                    LOG.info(f"Progress: {progress}%")
            
            if len(file_data) == file_size:
                LOG.info(f"✓ File received successfully: {len(file_data)} bytes")
                
                # Store file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"received_{timestamp}.bin"
                self.last_file = file_data
                self.last_filename = filename
                
                # Save to disk
                save_path = Path(f"received_files/{filename}")
                save_path.parent.mkdir(exist_ok=True)
                save_path.write_bytes(file_data)
                LOG.info(f"File saved to: {save_path}")
                
                # Notify all connected websocket clients
                await self.notify_clients(file_data, filename)
            else:
                LOG.error(f"File reception incomplete: {len(file_data)}/{file_size} bytes")
                
        except Exception as e:
            LOG.error(f"Error receiving file: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            LOG.info("RX STM32 disconnected")
    
    async def notify_clients(self, file_data, filename):
        """Notify all WebSocket clients about new file"""
        if not self.websocket_clients:
            return
            
        # Encode file as base64 for WebSocket
        file_b64 = base64.b64encode(file_data).decode('ascii')
        
        message = json.dumps({
            "type": "file_received",
            "filename": filename,
            "size": len(file_data),
            "data": file_b64
        })
        
        # Send to all connected clients
        dead_clients = set()
        for ws in self.websocket_clients:
            try:
                await ws.send(message)
                LOG.info(f"Notified client about {filename}")
            except Exception as e:
                LOG.error(f"Failed to notify client: {e}")
                dead_clients.add(ws)
        
        # Remove dead clients
        self.websocket_clients -= dead_clients
    
    async def start_server(self):
        """Start TCP server to listen for RX STM32 connections"""
        server = await asyncio.start_server(
            self.handle_stm32_connection,
            '0.0.0.0',
            self.listen_port
        )
        
        addr = server.sockets[0].getsockname()
        LOG.info(f'✓ Listening for RX STM32 on {addr[0]}:{addr[1]}')
        
        async with server:
            await server.serve_forever()


async def ws_handler(websocket, path, receiver: EthernetReceiver):
    """Handle WebSocket connections from web UI"""
    LOG.info("Web UI client connected: %s", websocket.remote_address)
    receiver.websocket_clients.add(websocket)
    
    try:
        # Send last received file if available
        if receiver.last_file:
            file_b64 = base64.b64encode(receiver.last_file).decode('ascii')
            await websocket.send(json.dumps({
                "type": "file_received",
                "filename": receiver.last_filename,
                "size": len(receiver.last_file),
                "data": file_b64
            }))
        
        async for msg in websocket:
            LOG.debug("WS received: %s", msg[:100])
            try:
                obj = json.loads(msg)
                msg_type = obj.get("type", "")
                
                if msg_type == "get_last_file":
                    # Client requesting last file
                    if receiver.last_file:
                        file_b64 = base64.b64encode(receiver.last_file).decode('ascii')
                        await websocket.send(json.dumps({
                            "type": "file_received",
                            "filename": receiver.last_filename,
                            "size": len(receiver.last_file),
                            "data": file_b64
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "info",
                            "message": "No files received yet"
                        }))
                        
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "invalid json"
                }))
    except Exception as e:
        LOG.info("WS client disconnected: %s", e)
    finally:
        receiver.websocket_clients.discard(websocket)


async def start_web_server(host, port):
    """Start HTTP server for web UI"""
    app = web.Application()
    
    # Look for web directory
    web_dir = Path(__file__).parent.parent / 'web' / 'app'
    if not web_dir.exists():
        web_dir = Path('/usr/src/app/web/app')  # Docker path
    
    LOG.info(f"Looking for web files in: {web_dir}")
    
    if web_dir.exists():
        async def index_handler(request):
            return web.FileResponse(web_dir / 'index.html')
        
        app.router.add_get('/', index_handler)
        app.router.add_static('/', web_dir)
    else:
        LOG.warning(f"Web directory not found at {web_dir}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    LOG.info(f"✓ Web UI server running at http://{host}:{port}")
    return runner


async def main():
    parser = argparse.ArgumentParser(description="XCOM RX Bridge - Receives files from RX STM32")
    parser.add_argument("--listen-port", type=int, default=5000, 
                       help="TCP port to listen for RX STM32 (default: 5000)")
    parser.add_argument("--ws-port", type=int, default=8766,
                       help="WebSocket port for web UI (default: 8766)")
    parser.add_argument("--web-port", type=int, default=8001,
                       help="HTTP port for web UI (default: 8001)")
    parser.add_argument("--host", default="0.0.0.0",
                       help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    receiver = EthernetReceiver(listen_port=args.listen_port)

    # Start web server for UI
    web_runner = await start_web_server(args.host, args.web_port)

    # Start WebSocket server
    async def handler(ws, path):
        await ws_handler(ws, path, receiver)

    ws_server = await serve(handler, args.host, args.ws_port)
    LOG.info(f"✓ WebSocket server listening on ws://{args.host}:{args.ws_port}")

    # Start TCP server for RX STM32
    try:
        await receiver.start_server()
    finally:
        await web_runner.cleanup()
        ws_server.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting")
