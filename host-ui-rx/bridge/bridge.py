#!/usr/bin/env python3
"""XCOM RX Bridge: Receives files from RX STM32 via Ethernet and displays in web UI.

Supports two incoming formats:
- Framed: START_FLAG (4 bytes) + header_len (4 bytes LE) + header_json (header_len bytes utf-8) + payload
  header_json should include at least: { "size": <payload_size>, "filename": "...", "mimetype": "..." }
- Legacy: 4-byte little-endian payload size followed by raw payload bytes

The receiver preserves filename and mimetype when metadata is present.
"""

import argparse
import asyncio
import base64
import concurrent.futures
import json
import logging
import mimetypes
import os
import time
import tempfile
from aiohttp import web
from datetime import datetime
from pathlib import Path
from websockets import serve

LOG = logging.getLogger("rx-bridge")

START_FLAG = b"\xAA\xBB\xCC\xDD"


class EthernetReceiver:
    def __init__(self, listen_port=5000):
        self.listen_port = listen_port
        self.last_file = None
        self.last_filename = None
        self.last_mimetype = None
        self.websocket_clients = set()
        self.stm32_connected = False
        self.fpga_connected = False
        self.adafruit_connected = False
        self.last_connection_time = None
        self.data_received = False
        # optional recorded port
        self.adafruit_port = None
        self.fpga_port = None

    async def handle_stm32_connection(self, reader, writer):
        addr = writer.get_extra_info('peername')
        LOG.info(f"RX STM32 connected from {addr}")
        self.stm32_connected = True
        self.last_connection_time = datetime.now()

        try:
            # Read first 4 bytes; detect framed START_FLAG or legacy size prefix
            first4 = await reader.readexactly(4)
            metadata = {}
            file_data = b''

            if first4 == START_FLAG:
                # Framed format
                header_len_bytes = await reader.readexactly(4)
                header_len = int.from_bytes(header_len_bytes, byteorder='little')
                header_json_bytes = await reader.readexactly(header_len)
                try:
                    metadata = json.loads(header_json_bytes.decode('utf-8'))
                except Exception:
                    metadata = {}
                payload_size = int(metadata.get('size', 0))
                LOG.info(f"Receiving framed file: {payload_size} bytes, metadata={metadata}")
                # read payload
                while len(file_data) < payload_size:
                    chunk = await reader.read(min(4096, payload_size - len(file_data)))
                    if not chunk:
                        break
                    file_data += chunk
                    if len(file_data) % 10240 == 0:
                        progress = (len(file_data) * 100) // payload_size
                        LOG.info(f"Progress: {progress}%")
                expected = payload_size
            else:
                # Legacy size-prefixed format
                file_size = int.from_bytes(first4, byteorder='little')
                LOG.info(f"Receiving legacy file: {file_size} bytes")
                while len(file_data) < file_size:
                    chunk = await reader.read(min(4096, file_size - len(file_data)))
                    if not chunk:
                        break
                    file_data += chunk
                    if len(file_data) % 10240 == 0:
                        progress = (len(file_data) * 100) // file_size
                        LOG.info(f"Progress: {progress}%")
                expected = file_size

            if len(file_data) == expected:
                LOG.info(f"✓ File received successfully: {len(file_data)} bytes")
                self.data_received = True

                raw_filename = metadata.get('filename') if isinstance(metadata.get('filename'), str) else None
                if raw_filename:
                    filename = Path(raw_filename).name
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"received_{timestamp}.bin"

                self.last_file = file_data
                self.last_filename = filename

                # Save local copy
                local_save = Path('received_files')
                local_save.mkdir(parents=True, exist_ok=True)
                local_path = local_save / filename
                local_path.write_bytes(file_data)
                LOG.info(f"File saved to: {local_path}")

                # Save copy in web static folder when available
                try:
                    web_files_dir = Path('/usr/src/app/web/app/received_files')
                    web_files_dir.mkdir(parents=True, exist_ok=True)
                    web_path = web_files_dir / filename
                    web_path.write_bytes(file_data)
                    LOG.info(f"File saved to web path: {web_path}")
                except Exception:
                    LOG.debug('Could not write to web static received_files path; continuing')

                # Determine mimetype
                mimetype = metadata.get('mimetype') if isinstance(metadata.get('mimetype'), str) else None
                if not mimetype:
                    guessed, _ = mimetypes.guess_type(filename)
                    mimetype = guessed
                self.last_mimetype = mimetype
                await self.notify_clients(file_data, filename, mimetype)
            else:
                LOG.error(f"File reception incomplete: {len(file_data)}/{expected} bytes")

        except Exception as e:
            LOG.error(f"Error receiving file: {e}")
        finally:
            self.stm32_connected = False
            self.data_received = False
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            LOG.info("RX STM32 disconnected")

    async def notify_clients(self, file_data, filename, mimetype=None):
        """Notify all WebSocket clients about new file"""
        if not self.websocket_clients:
            return
            
        # Encode file as base64 for WebSocket
        file_b64 = base64.b64encode(file_data).decode('ascii')
        
        message = json.dumps({
            "type": "file_received",
            "filename": filename,
            "size": len(file_data),
            "mimetype": mimetype,
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

    async def notify_ber_result(self, filename, result: dict):
        """Notify all connected websocket clients about BER results for a filename
        result is a dict containing bytes_compared, differing_bytes, bits_compared,
        differing_bits, bit_error_rate, etc.
        """
        if not self.websocket_clients:
            return

        message = json.dumps({
            "type": "ber_result",
            "filename": filename,
            **result
        })

        dead_clients = set()
        for ws in self.websocket_clients:
            try:
                await ws.send(message)
                LOG.info(f"Sent BER result to client for {filename}")
            except Exception as e:
                LOG.error(f"Failed to send BER result: {e}")
                dead_clients.add(ws)

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


def ftd_blocking_reader(loop, receiver, device_index=2):
    """
    Blocking FTDI reader that parses framed files from an FT232H.
    Frame format expected:
      [START_FLAG (4 bytes)] [header_len (4 bytes little-endian)] [header_json (header_len bytes utf-8)] [payload]
    When a full frame is received the function will write the file to disk
    and schedule `receiver.notify_clients(payload, filename, mimetype)` on the
    provided asyncio loop via `asyncio.run_coroutine_threadsafe`.
    """
    START_FLAG = b"\xAA\xBB\xCC\xDD"
    try:
        import ftd2xx as ftd
    except Exception as e:
        print(f"[ftd] ftd2xx import failed: {e}")
        return

    try:
        dev = ftd.open(device_index)
    except Exception as e:
        print(f"[ftd] Failed to open FTDI device index {device_index}: {e}")
        return

    try:
        dev.resetDevice()
        dev.setUSBParameters(65536, 65536)
        dev.setTimeouts(1000, 1000)
        dev.setBitMode(0x00, 0x00)
        dev.purge(ftd.defines.PURGE_RX | ftd.defines.PURGE_TX)
    except Exception as e:
        print(f"[ftd] Device configuration failed: {e}")
        try:
            dev.close()
        except Exception:
            pass
        return

    buf = bytearray()
    try:
        while True:
            rxq = dev.getQueueStatus()
            if rxq > 0:
                chunk = dev.read(rxq)
                if chunk:
                    buf.extend(chunk)

            # Attempt to parse frames
            while True:
                idx = buf.find(START_FLAG)
                if idx == -1:
                    # keep buffer from growing without bound
                    if len(buf) > 10_000_000:
                        buf[:] = buf[-1_000_000:]
                    break

                # Drop leading bytes
                if idx > 0:
                    del buf[:idx]

                header_offset = len(START_FLAG)
                if len(buf) < header_offset + 4:
                    break

                header_len = int.from_bytes(buf[header_offset:header_offset+4], byteorder='little')
                total_header_end = header_offset + 4 + header_len
                if len(buf) < total_header_end:
                    break

                header_json_bytes = bytes(buf[header_offset+4:total_header_end])
                try:
                    metadata = json.loads(header_json_bytes.decode('utf-8'))
                except Exception:
                    metadata = {}

                payload_size = int(metadata.get('size', 0))
                total_frame_len = total_header_end + payload_size
                if len(buf) < total_frame_len:
                    break

                payload = bytes(buf[total_header_end:total_frame_len])
                del buf[:total_frame_len]

                raw_filename = metadata.get('filename') if isinstance(metadata.get('filename'), str) else None
                if raw_filename:
                    filename = Path(raw_filename).name
                else:
                    filename = f"received_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
                mimetype = metadata.get('mimetype') if isinstance(metadata.get('mimetype'), str) else None

                # Save to local received_files
                try:
                    local_save = Path('received_files')
                    local_save.mkdir(parents=True, exist_ok=True)
                    local_path = local_save / filename
                    local_path.write_bytes(payload)
                except Exception as e:
                    print(f"[ftd] Failed to write local copy: {e}")

                # Save to web static folder when available
                try:
                    web_files_dir = Path('/usr/src/app/web/app/received_files')
                    web_files_dir.mkdir(parents=True, exist_ok=True)
                    web_path = web_files_dir / filename
                    web_path.write_bytes(payload)
                except Exception:
                    pass

                # Schedule notify_clients on the asyncio loop
                try:
                    # Record last mimetype on the receiver (thread-safe-ish)
                    try:
                        receiver.last_mimetype = mimetype
                    except Exception:
                        pass
                    coro = receiver.notify_clients(payload, filename, mimetype)
                    asyncio.run_coroutine_threadsafe(coro, loop)
                except Exception as e:
                    print(f"[ftd] Failed to schedule notify_clients: {e}")

            time.sleep(0.001)
    except Exception as e:
        print(f"[ftd] Reader loop exception: {e}")
    finally:
        try:
            dev.close()
        except Exception:
            pass


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
                "mimetype": getattr(receiver, 'last_mimetype', None),
                "data": file_b64
            }))
        
        async for msg in websocket:
            LOG.info("WS received: %s", msg[:100])
            try:
                obj = json.loads(msg)
                msg_type = obj.get("type", "")
                
                if msg_type == "check_connection":
                    # Report connection status: prioritize Adafruit device presence, then STM32
                    if getattr(receiver, 'adafruit_connected', False) or getattr(receiver, 'fpga_connected', False):
                        # prefer the new adafruit fields if present
                        port = getattr(receiver, 'adafruit_port', None) or getattr(receiver, 'fpga_port', None)
                        response = {
                            "type": "connection_status",
                            "connected": True,
                            "device": "adafruit",
                            "port": port
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


async def start_web_server(host, port, receiver=None):
    """Start HTTP server for web UI"""
    # Allow configuring max upload size via env var MAX_UPLOAD_MB (default 200 MB)
    try:
        max_upload_mb = int(os.environ.get('MAX_UPLOAD_MB', '200'))
    except Exception:
        max_upload_mb = 200
    client_max_size = max_upload_mb * 1024 * 1024
    app = web.Application(client_max_size=client_max_size)
    # expose receiver to request handlers so external notifiers can call notify_clients
    if receiver is not None:
        app['receiver'] = receiver
    
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
                    guessed, _ = mimetypes.guess_type(p.name)
                    entries.append({
                        'name': p.name,
                        'size': p.stat().st_size,
                        'mtime': p.stat().st_mtime,
                        'mimetype': guessed
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
        
        async def api_notify_new_file(request):
            """Endpoint for external processes to notify the bridge of a new file.
            Expects JSON: { "filename": "name.bin", "mimetype": "type" }
            The file is read from the container's files_dir and then notify_clients
            is called so connected web UI clients receive the update.
            """
            try:
                data = await request.json()
            except Exception:
                raise web.HTTPBadRequest(text='expected json body')

            filename = data.get('filename')
            mimetype = data.get('mimetype')
            if not filename:
                raise web.HTTPBadRequest(text='missing filename')

            # Prevent path traversal
            if '..' in filename or filename.startswith('/'):
                raise web.HTTPForbidden()

            filepath = files_dir / filename
            if not filepath.exists() or not filepath.is_file():
                raise web.HTTPNotFound()

            # Read file bytes
            file_bytes = filepath.read_bytes()

            # Notify connected websocket clients
            await request.app['receiver'].notify_clients(file_bytes, filename, mimetype)

            return web.json_response({'status': 'ok'})

        app.router.add_post('/api/notify_new_file', api_notify_new_file)
        
        async def api_compute_ber(request):
            """Compute bit-error-rate between a received file and an uploaded reference file.
            Streams the uploaded reference to a temporary file and performs a chunked
            comparison against the stored received file to avoid loading whole files
            into memory. Comparison is offloaded to a threadpool to avoid blocking
            the asyncio event loop.

            Expects multipart/form-data with field 'reference' containing the original file.
            Query parameter or form field 'filename' specifies the received file to compare.
            Returns JSON: { filename, reference_filename, bytes_compared, differing_bytes, bits_compared, differing_bits, bit_error_rate }
            """
            # Try to get filename from query first
            q_filename = request.query.get('filename')
            post = await request.post()
            filename = q_filename or post.get('filename')
            if not filename:
                raise web.HTTPBadRequest(text='missing filename parameter (query or form)')

            # Prevent path traversal
            if '..' in filename or filename.startswith('/'):
                raise web.HTTPForbidden()

            filepath = files_dir / filename
            if not filepath.exists() or not filepath.is_file():
                raise web.HTTPNotFound()

            # Use multipart reader to stream the uploaded reference to a tempfile
            try:
                mp = await request.multipart()
            except Exception:
                # Fallback if not a multipart request
                raise web.HTTPBadRequest(text='expected multipart/form-data')

            ref_part = None
            async for part in mp:
                # look for the 'reference' file field
                if part.name == 'reference' and part.filename:
                    ref_part = part
                    break

            if ref_part is None:
                # Try to find any file part
                # Rewind the multipart reader by re-parsing form (less efficient)
                # but supports clients that didn't name the field 'reference'
                for k, v in post.items():
                    if hasattr(v, 'filename'):
                        # aiohttp FileField: has .file and .filename
                        # Write its content to temp
                        ref_field = v
                        break
                else:
                    raise web.HTTPBadRequest(text='missing reference file upload (field name: reference)')

                # write reference bytes from ref_field
                tmp = tempfile.NamedTemporaryFile(delete=False)
                try:
                    # ref_field.file is a file-like object
                    while True:
                        chunk = ref_field.file.read(64 * 1024)
                        if not chunk:
                            break
                        tmp.write(chunk)
                    tmp.flush()
                    tmp_path = tmp.name
                finally:
                    tmp.close()
            else:
                # Stream the part to a temp file
                tmp = tempfile.NamedTemporaryFile(delete=False)
                try:
                    while True:
                        chunk = await ref_part.read_chunk(size=64 * 1024)
                        if not chunk:
                            break
                        tmp.write(chunk)
                    tmp.flush()
                    tmp_path = tmp.name
                finally:
                    tmp.close()

            # Define the synchronous comparison function to run in executor
            def compare_files(received_path, reference_path, chunk_size=64 * 1024):
                differing_bytes = 0
                differing_bits = 0
                bytes_compared = 0

                with open(received_path, 'rb') as fa, open(reference_path, 'rb') as fb:
                    while True:
                        a = fa.read(chunk_size)
                        b = fb.read(chunk_size)
                        if not a and not b:
                            break
                        # If lengths differ, pad shorter with zeros conceptually
                        la = len(a)
                        lb = len(b)
                        max_len = max(la, lb)
                        # iterate over positions
                        for i in range(max_len):
                            av = a[i] if i < la else 0
                            bv = b[i] if i < lb else 0
                            x = av ^ bv
                            if x:
                                differing_bytes += 1
                                try:
                                    differing_bits += x.bit_count()
                                except AttributeError:
                                    differing_bits += bin(x).count('1')
                        bytes_compared += max_len

                bits_compared = bytes_compared * 8
                bit_error_rate = (differing_bits / bits_compared) if bits_compared > 0 else 0.0
                return {
                    'bytes_compared': bytes_compared,
                    'differing_bytes': differing_bytes,
                    'bits_compared': bits_compared,
                    'differing_bits': differing_bits,
                    'bit_error_rate': bit_error_rate
                }

            # Run comparison in threadpool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            try:
                stats = await loop.run_in_executor(None, compare_files, str(filepath), tmp_path)
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            result = {
                'filename': filename,
                'reference_filename': os.path.basename(tmp_path),
            }
            result.update(stats)

            # Notify connected websocket clients about the BER result so UI can show it
            try:
                # receiver registered in app under 'receiver'
                recv = request.app.get('receiver')
                if recv is not None:
                    # Fire-and-forget notify (but await to ensure delivery before HTTP response)
                    await recv.notify_ber_result(filename, result)
            except Exception:
                LOG.exception('Failed to notify websocket clients about BER result')

            return web.json_response(result)

        app.router.add_post('/api/compute_ber', api_compute_ber)
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
    parser.add_argument("--adafruit-port", type=int, default=0,
                       help="Optional TCP port to listen for Adafruit connections (default: disabled)")
    parser.add_argument("--adafruit-bitpacked", action="store_true",
                       help="If set, interpret Adafruit payload as ASCII '0'/'1' bits packed into a stream and reconstruct bytes")
    parser.add_argument("--adafruit-bitorder", choices=["msb","lsb"], default="msb",
                       help="Bit order when reconstructing bits from Adafruit (msb or lsb). Default: msb")
    parser.add_argument("--ws-port", type=int, default=8766,
                       help="WebSocket port for web UI (default: 8766)")
    parser.add_argument("--web-port", type=int, default=8001,
                       help="HTTP port for web UI (default: 8001)")
    parser.add_argument("--host", default="0.0.0.0",
                       help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--enable-ftdi", action="store_true",
                       help="Enable integrated FTDI (FT232H) capture")
    parser.add_argument("--ftdi-index", type=int, default=2,
                       help="FTDI device index to open (default: 2)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    receiver = EthernetReceiver(listen_port=args.listen_port)
    # Record configured Adafruit port on receiver so ws_handler can report it
    receiver.adafruit_port = args.adafruit_port
    # For backward compatibility also set fpga_port if present
    receiver.fpga_port = getattr(args, 'fpga_port', args.adafruit_port)

    # Start web server for UI
    web_runner = await start_web_server(args.host, args.web_port, receiver)

    # Optionally start FTDI worker in a background thread (if requested)
    if args.enable_ftdi:
        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        # Start the blocking FTDI reader in the executor
        loop.run_in_executor(executor, ftd_blocking_reader, loop, receiver, args.ftdi_index)

    # Optional: start a separate server for FPGA raw-bit/byte input
    # This allows the FPGA to send raw data directly to the bridge, which can then be forwarded to the web UI.
    adafruit_server = None
    if args.adafruit_port and args.adafruit_port > 0:
        async def adafruit_handler(reader, writer):
            addr = writer.get_extra_info('peername')
            LOG.info(f"Adafruit device connected from {addr}")
            receiver.adafruit_connected = True
            try:
                # Read first 4 bytes to detect framed START_FLAG or legacy size prefix
                first4 = await reader.readexactly(4)
                metadata = {}
                payload = b''

                if first4 == START_FLAG:
                    # Framed format
                    header_len_bytes = await reader.readexactly(4)
                    header_len = int.from_bytes(header_len_bytes, byteorder='little')
                    header_json_bytes = await reader.readexactly(header_len)
                    try:
                        metadata = json.loads(header_json_bytes.decode('utf-8'))
                    except Exception:
                        metadata = {}
                    payload_size = int(metadata.get('size', 0))
                    LOG.info(f"Adafruit framed payload size: {payload_size}")
                    while len(payload) < payload_size:
                        chunk = await reader.read(min(4096, payload_size - len(payload)))
                        if not chunk:
                            break
                        payload += chunk
                else:
                    # Legacy format: first4 is the size
                    payload_size = int.from_bytes(first4, byteorder='little')
                    LOG.info(f"Adafruit reports payload size: {payload_size}")
                    while len(payload) < payload_size:
                        chunk = await reader.read(min(4096, payload_size - len(payload)))
                        if not chunk:
                            break
                        payload += chunk

                if len(payload) != int(payload_size):
                    LOG.error("Adafruit payload incomplete: %d/%d bytes", len(payload), payload_size)
                else:
                    LOG.info("Adafruit payload received (%d bytes)", len(payload))

                    # If bitpacked, payload is ASCII '0'/'1' stream; reconstruct bytes
                    if args.adafruit_bitpacked:
                        bits = [c for c in payload.decode('ascii', errors='ignore') if c in '01']
                        if len(bits) % 8 != 0:
                            bits += ['0'] * (8 - (len(bits) % 8))
                        data = bytearray()
                        msb_first = (args.adafruit_bitorder == 'msb')
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
                        out_data = bytes(data)
                    else:
                        out_data = payload

                    # Determine filename: prefer metadata filename if present
                    raw_filename = metadata.get('filename') if isinstance(metadata.get('filename'), str) else None
                    if raw_filename:
                        filename = Path(raw_filename).name
                    else:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"adafruit_{timestamp}.bin"

                    receiver.last_file = out_data
                    receiver.last_filename = filename

                    web_files_dir = Path('/usr/src/app/web/app/received_files')
                    web_files_dir.mkdir(parents=True, exist_ok=True)
                    save_path = web_files_dir / filename
                    save_path.write_bytes(out_data)
                    LOG.info(f"File saved to web path: {save_path}")

                    # Determine mimetype and notify
                    mimetype = metadata.get('mimetype') if isinstance(metadata.get('mimetype'), str) else None
                    if not mimetype:
                        guessed, _ = mimetypes.guess_type(filename)
                        mimetype = guessed
                    await receiver.notify_clients(out_data, filename, mimetype)

            except Exception as e:
                LOG.error("Error in Adafruit handler: %s", e)
            finally:
                receiver.fpga_connected = False
                receiver.adafruit_connected = False
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        adafruit_server = await asyncio.start_server(adafruit_handler, '0.0.0.0', args.adafruit_port)
        LOG.info(f"✓ Listening for Adafruit on 0.0.0.0:{args.adafruit_port}")

    # Start WebSocket server
    async def handler(ws, path):
        await ws_handler(ws, path, receiver)

    # Set max_size to 20MB to handle larger file uploads
    # Use WS_MAX_MB env or fall back to MAX_UPLOAD_MB to keep consistent limits
    try:
        ws_max_mb = int(os.environ.get('WS_MAX_MB', os.environ.get('MAX_UPLOAD_MB', '50')))
    except Exception:
        ws_max_mb = 50
    ws_max_size = ws_max_mb * 1024 * 1024
    ws_server = await serve(handler, args.host, args.ws_port, max_size=ws_max_size)
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
