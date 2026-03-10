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
import os
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
        self.stm32_connected = False
        self.fpga_connected = False
        self.last_connection_time = None
        self.data_received = False  # Track if we've received any data
        
    async def handle_stm32_connection(self, reader, writer):
        """Handle incoming connection from RX STM32"""
        addr = writer.get_extra_info('peername')
        LOG.info(f"RX STM32 connected from {addr}")
        self.stm32_connected = True
        self.last_connection_time = datetime.now()
        
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
                
                # Mark that we've received data
                self.data_received = True
                
                # Store file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"received_{timestamp}.bin"
                self.last_file = file_data
                self.last_filename = filename

                # Save to disk in two places:
                # 1) a local received_files/ for dev environments
                # 2) the web app's received_files dir so the HTTP server (/api/files and /files/) can serve it
                # Save local copy
                local_save = Path('received_files')
                local_save.mkdir(parents=True, exist_ok=True)
                local_path = local_save / filename
                local_path.write_bytes(file_data)
                LOG.info(f"File saved to: {local_path}")

                # Also save into web static folder if available (container runtime path)
                try:
                    web_files_dir = Path('/usr/src/app/web/app/received_files')
                    web_files_dir.mkdir(parents=True, exist_ok=True)
                    web_path = web_files_dir / filename
                    web_path.write_bytes(file_data)
                    LOG.info(f"File saved to web path: {web_path}")
                except Exception:
                    # Non-fatal: continue if web path not writable in this environment
                    LOG.debug('Could not write to web static received_files path; continuing')
                
                # Notify all connected websocket clients
                await self.notify_clients(file_data, filename)
            else:
                LOG.error(f"File reception incomplete: {len(file_data)}/{file_size} bytes")
                
        except Exception as e:
            LOG.error(f"Error receiving file: {e}")
        finally:
            self.stm32_connected = False
            self.data_received = False  # Reset when disconnected
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
            LOG.info("WS received: %s", msg[:100])
            try:
                obj = json.loads(msg)
                msg_type = obj.get("type", "")
                
                if msg_type == "check_connection":
                    # Report connection status: prioritize FPGA presence, then STM32
                    if getattr(receiver, 'fpga_connected', False):
                        response = {
                            "type": "connection_status",
                            "connected": True,
                            "device": "fpga",
                            "port": getattr(receiver, 'fpga_port', None)
                        }
                    elif receiver.stm32_connected:
                        response = {
                            "type": "connection_status",
                            "connected": True,
                            "device": "stm32",
                            "port": receiver.listen_port
                        }
                    else:
                        response = {
                            "type": "connection_status",
                            "connected": False,
                            "reason": "No devices connected"
                        }
                    LOG.info("Sending connection status: %s", response)
                    await websocket.send(json.dumps(response))
                
                elif msg_type == "get_last_file":
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
        # Expose received files and a simple directory listing so the UI can open/download them
        # Directory under the web static root where received files are saved
        files_dir = Path('/usr/src/app/web/app/received_files')
        if not files_dir.exists():
            files_dir.mkdir(parents=True, exist_ok=True)

        async def files_index(request):
            # Build a simple HTML index of received files
            files = []
            for p in sorted(files_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_file():
                    files.append((p.name, p.stat().st_size, p.stat().st_mtime))

            html = ['<html><head><meta charset="utf-8"><title>Received files</title></head><body>']
            html.append('<h2>Received files</h2>')
            html.append('<ul>')
            for name, size, mtime in files:
                html.append(f'<li><a href="/files/{name}">{name}</a> ({size} bytes)</li>')
            html.append('</ul>')
            html.append('</body></html>')
            return web.Response(text='\n'.join(html), content_type='text/html')

        async def api_files(request):
            # Return JSON list of files for UI consumption
            entries = []
            for p in sorted(files_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_file():
                    entries.append({
                        'name': p.name,
                        'size': p.stat().st_size,
                        'mtime': p.stat().st_mtime
                    })
            return web.json_response(entries)

        async def serve_file(request):
            name = request.match_info.get('filename')
            # Prevent path traversal
            if '..' in name or name.startswith('/'):
                raise web.HTTPForbidden()
            filepath = files_dir / name
            if not filepath.exists() or not filepath.is_file():
                raise web.HTTPNotFound()
            # Return file with Content-Disposition so browsers download with a sensible filename
            resp = web.FileResponse(filepath)
            try:
                resp.headers['Content-Disposition'] = f'attachment; filename="{name}"'
            except Exception:
                # If headers cannot be set for any reason, just return the FileResponse
                pass
            return resp
        app.router.add_get('/files/', files_index)
        app.router.add_get('/files/{filename}', serve_file)
        app.router.add_get('/api/files', api_files)
        # Expose host-side received_files path if provided via environment (HOST_RECEIVED_DIR)
        async def api_host_received_path(request):
            host_path = os.environ.get('HOST_RECEIVED_DIR', '')
            return web.json_response({'host_path': host_path})
        app.router.add_get('/api/host_received_path', api_host_received_path)
        # Serve static web files after registering dynamic /files routes so they don't get shadowed
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
    parser.add_argument("--fpga-port", type=int, default=0,
                       help="Optional TCP port to listen for FPGA connections (default: disabled)")
    parser.add_argument("--fpga-bitpacked", action="store_true",
                       help="If set, interpret FPGA payload as ASCII '0'/'1' bits packed into a stream and reconstruct bytes")
    parser.add_argument("--fpga-bitorder", choices=["msb","lsb"], default="msb",
                       help="Bit order when reconstructing bits from FPGA (msb or lsb). Default: msb")
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
    # Record configured FPGA port on receiver so ws_handler can report it
    receiver.fpga_port = args.fpga_port

    # Start web server for UI
    web_runner = await start_web_server(args.host, args.web_port)

    # Optional: start a separate server for FPGA raw-bit/byte input
    # This allows the FPGA to send raw data directly to the bridge, which can then be forwarded to the web UI.
    fpga_server = None
    if args.fpga_port and args.fpga_port > 0:
        async def fpga_handler(reader, writer):
            addr = writer.get_extra_info('peername')
            LOG.info(f"FPGA connected from {addr}")
            receiver.fpga_connected = True
            try:
                # Read 4-byte little-endian size header (same framing as STM32)
                size_bytes = await reader.readexactly(4)
                payload_size = int.from_bytes(size_bytes, byteorder='little')
                LOG.info(f"FPGA reports payload size: %d", payload_size)

                # Read payload
                payload = b''
                while len(payload) < payload_size:
                    chunk = await reader.read(min(4096, payload_size - len(payload)))
                    if not chunk:
                        break
                    payload += chunk

                if len(payload) != payload_size:
                    LOG.error("FPGA payload incomplete: %d/%d bytes", len(payload), payload_size)
                else:
                    LOG.info("FPGA payload received (%d bytes)", len(payload))
                    # If bitpacked, payload is ASCII '0'/'1' stream; reconstruct bytes
                    if args.fpga_bitpacked:
                        bits = [c for c in payload.decode('ascii', errors='ignore') if c in '01']
                        # pad to multiple of 8
                        if len(bits) % 8 != 0:
                            bits += ['0'] * (8 - (len(bits) % 8))
                        data = bytearray()
                        msb_first = (args.fpga_bitorder == 'msb')
                        for i in range(0, len(bits), 8):
                            byte_bits = bits[i:i+8]
                            if msb_first:
                                val = 0
                                for b in byte_bits:
                                    val = (val << 1) | int(b)
                            else:
                                val = 0
                                for j, b in enumerate(byte_bits):
                                    val |= (int(b) << j)
                            data.append(val)
                        reconstructed = bytes(data)
                        LOG.info("FPGA bitpacked -> reconstructed %d bytes", len(reconstructed))
                        out_data = reconstructed
                    else:
                        # Treat payload as raw bytes and deliver directly
                        out_data = payload


                    # Persist the file and remember it so newly connected web clients can fetch it
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"fpga_{timestamp}.bin"
                    receiver.last_file = out_data
                    receiver.last_filename = filename

                    # Prefer to save files under the web app directory so static server can serve them
                    # Use the runtime web-app directory that the server serves from inside container
                    web_files_dir = Path('/usr/src/app/web/app/received_files')
                    web_files_dir.mkdir(parents=True, exist_ok=True)
                    save_path = web_files_dir / filename
                    save_path.write_bytes(out_data)
                    LOG.info(f"File saved to web path: {save_path}")

                    # Notify connected clients
                    await receiver.notify_clients(out_data, filename)

            except Exception as e:
                LOG.error("Error in FPGA handler: %s", e)
            finally:
                receiver.fpga_connected = False
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        fpga_server = await asyncio.start_server(fpga_handler, '0.0.0.0', args.fpga_port)
        LOG.info(f"✓ Listening for FPGA on 0.0.0.0:{args.fpga_port}")

    # Start WebSocket server
    async def handler(ws, path):
        await ws_handler(ws, path, receiver)

    # Set max_size to 20MB to handle larger file uploads
    ws_server = await serve(handler, args.host, args.ws_port, max_size=20 * 1024 * 1024)
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
