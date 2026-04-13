#!/usr/bin/env python3
"""XCOM RX Bridge: Receives files from an FT232H device and displays them in a web UI.

Frame format expected from FTDI:
  START_FLAG (4 bytes) + header_len (4 bytes LE) + header_json (header_len bytes utf-8) + payload
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

class BridgeState:
    """Holds the global state for the UI bridge."""
    def __init__(self):
        self.last_file = None
        self.last_filename = None
        self.last_mimetype = None
        self.websocket_clients = set()
        self.ftdi_connected = False

    async def notify_clients(self, file_data, filename, mimetype=None):
        """Notify all WebSocket clients about new file"""
        if not self.websocket_clients:
            return
            
        file_b64 = base64.b64encode(file_data).decode('ascii')
        
        message = json.dumps({
            "type": "file_received",
            "filename": filename,
            "size": len(file_data),
            "mimetype": mimetype,
            "data": file_b64
        })
        
        dead_clients = set()
        for ws in self.websocket_clients:
            try:
                await ws.send(message)
                LOG.info(f"Notified client about {filename}")
            except Exception as e:
                LOG.error(f"Failed to notify client: {e}")
                dead_clients.add(ws)
        
        self.websocket_clients -= dead_clients

    async def notify_ber_result(self, filename, result: dict):
        """Notify all connected websocket clients about BER results"""
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


def get_ftdi_device(target_serial=None, target_desc=None, fallback_index=2):
    """Scans for FTDI devices and returns an open device handle."""
    try:
        import ftd2xx as ftd
    except ImportError:
        print("[ftd_scanner] ftd2xx library not found. Cannot open FTDI device.")
        return None

    try:
        num_devices = ftd.createDeviceInfoList()
    except Exception as e:
        print(f"[ftd_scanner] Error listing FTDI devices: {e}")
        return None

    if num_devices == 0:
        print("[ftd_scanner] No FTDI devices detected.")
        return None

    print(f"[ftd_scanner] Found {num_devices} FTDI device(s).")

    for i in range(num_devices):
        try:
            detail = ftd.getDeviceInfoDetail(i)
            raw_serial = detail.get('serial', b'')
            raw_desc = detail.get('description', b'')
            
            serial = raw_serial.decode('utf-8', errors='ignore') if isinstance(raw_serial, bytes) else str(raw_serial)
            desc = raw_desc.decode('utf-8', errors='ignore') if isinstance(raw_desc, bytes) else str(raw_desc)
            
            print(f"  -> Index {i}: Serial='{serial}', Description='{desc}'")

            if target_serial and target_serial == serial:
                print(f"[ftd_scanner] Match found by Serial Number '{serial}' at index {i}.")
                return ftd.open(i)
            
            if target_desc and target_desc in desc:
                print(f"[ftd_scanner] Match found by Description '{desc}' at index {i}.")
                return ftd.open(i)
        except Exception as e:
            print(f"[ftd_scanner] Error reading device info at index {i}: {e}")

    if not target_serial and not target_desc:
        print(f"[ftd_scanner] No specific target requested. Defaulting to index {fallback_index}.")
        try:
            return ftd.open(fallback_index)
        except Exception as e:
            print(f"[ftd_scanner] Failed to open fallback index {fallback_index}: {e}")
            return None

    print("[ftd_scanner] Target device not found among connected devices.")
    return None


def ftd_blocking_reader(loop, state: BridgeState, target_serial=None, target_desc=None, fallback_index=2):
    """Blocking FTDI reader that parses framed files from an FT232H."""
    START_FLAG = b"\xAA\xBB\xCC\xDD"
    try:
        import ftd2xx as ftd
    except Exception as e:
        print(f"[ftd] ftd2xx import failed: {e}")
        return

    dev = get_ftdi_device(target_serial, target_desc, fallback_index)
    
    if dev is None:
        print("[ftd] Failed to obtain a valid FTDI device. Exiting FTDI reader thread.")
        return

    try:
        dev.resetDevice()
        dev.setUSBParameters(65536, 65536)
        dev.setTimeouts(1000, 1000)
        dev.setBitMode(0x00, 0x00)
        dev.purge(ftd.defines.PURGE_RX | ftd.defines.PURGE_TX)
        
        state.ftdi_connected = True
        print("[ftd] Device successfully configured and connected.")
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

            while True:
                idx = buf.find(START_FLAG)
                if idx == -1:
                    if len(buf) > 10_000_000:
                        buf[:] = buf[-1_000_000:]
                    break

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

                try:
                    # FORCE it to create the folder relative to this Python script
                    base_dir = Path(__file__).parent
                    local_save = base_dir / 'received_files'
                    local_save.mkdir(parents=True, exist_ok=True)
                    
                    local_path = local_save / filename
                    local_path.write_bytes(payload)
                    print(f"[ftd] SUCCESS! Wrote {len(payload)} bytes to {local_path}")
                except Exception as e:
                    print(f"[ftd] Failed to write local copy: {e}")

                try:
                    web_files_dir = Path('/usr/src/app/web/app/received_files')
                    web_files_dir.mkdir(parents=True, exist_ok=True)
                    web_path = web_files_dir / filename
                    web_path.write_bytes(payload)
                except Exception as e:
                    pass

                try:
                    state.last_file = payload
                    state.last_filename = filename
                    state.last_mimetype = mimetype
                    coro = state.notify_clients(payload, filename, mimetype)
                    asyncio.run_coroutine_threadsafe(coro, loop)
                except Exception as e:
                    print(f"[ftd] Failed to schedule notify_clients: {e}")

            time.sleep(0.001)
    except Exception as e:
        print(f"[ftd] Reader loop exception: {e}")
    finally:
        state.ftdi_connected = False
        try:
            dev.close()
        except Exception:
            pass


async def ws_handler(websocket, path, state: BridgeState):
    """Handle WebSocket connections from web UI"""
    LOG.info("Web UI client connected: %s", websocket.remote_address)
    state.websocket_clients.add(websocket)
    
    try:
        if state.last_file:
            file_b64 = base64.b64encode(state.last_file).decode('ascii')
            await websocket.send(json.dumps({
                "type": "file_received",
                "filename": state.last_filename,
                "size": len(state.last_file),
                "mimetype": state.last_mimetype,
                "data": file_b64
            }))
        
        async for msg in websocket:
            try:
                obj = json.loads(msg)
                msg_type = obj.get("type", "")
                
                if msg_type == "check_connection":
                    if state.ftdi_connected:
                        response = {
                            "type": "connection_status",
                            "connected": True,
                            "device": "ftdi",
                            "port": "USB"
                        }
                    else:
                        response = {
                            "type": "connection_status",
                            "connected": False,
                            "reason": "No FTDI device connected"
                        }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == "get_last_file":
                    if state.last_file:
                        file_b64 = base64.b64encode(state.last_file).decode('ascii')
                        await websocket.send(json.dumps({
                            "type": "file_received",
                            "filename": state.last_filename,
                            "size": len(state.last_file),
                            "data": file_b64
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "info",
                            "message": "No files received yet"
                        }))
                        
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "message": "invalid json"}))
    except Exception as e:
        LOG.info("WS client disconnected: %s", e)
    finally:
        state.websocket_clients.discard(websocket)


async def start_web_server(host, port, state: BridgeState):
    """Start HTTP server for web UI"""
    try:
        max_upload_mb = int(os.environ.get('MAX_UPLOAD_MB', '200'))
    except Exception:
        max_upload_mb = 200
    client_max_size = max_upload_mb * 1024 * 1024
    
    app = web.Application(client_max_size=client_max_size)
    app['state'] = state
    
    web_dir = Path(__file__).parent.parent / 'web' / 'app'
    if not web_dir.exists():
        web_dir = Path('/usr/src/app/web/app')
    
    LOG.info(f"Looking for web files in: {web_dir}")
    
    if web_dir.exists():
        async def index_handler(request):
            return web.FileResponse(web_dir / 'index.html')
        app.router.add_get('/', index_handler)

        # Force the web server to look in the exact same directory the FTDI reader is saving to
        base_dir = Path(__file__).parent
        files_dir = base_dir / 'received_files'
        files_dir.mkdir(parents=True, exist_ok=True)

        async def api_files(request):
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
            if '..' in name or name.startswith('/'):
                raise web.HTTPForbidden()
            filepath = files_dir / name
            if not filepath.exists() or not filepath.is_file():
                raise web.HTTPNotFound()
            resp = web.FileResponse(filepath)
            try:
                resp.headers['Content-Disposition'] = f'attachment; filename="{name}"'
            except Exception:
                pass
            return resp

        app.router.add_get('/api/files', api_files)
        app.router.add_get('/files/{filename}', serve_file)
        
        async def api_compute_ber(request):
            q_filename = request.query.get('filename')
            post = await request.post()
            filename = q_filename or post.get('filename')
            if not filename:
                raise web.HTTPBadRequest(text='missing filename parameter (query or form)')

            if '..' in filename or filename.startswith('/'):
                raise web.HTTPForbidden()

            filepath = files_dir / filename
            if not filepath.exists() or not filepath.is_file():
                raise web.HTTPNotFound()

            try:
                mp = await request.multipart()
            except Exception:
                raise web.HTTPBadRequest(text='expected multipart/form-data')

            ref_part = None
            async for part in mp:
                if part.name == 'reference' and part.filename:
                    ref_part = part
                    break

            if ref_part is None:
                for k, v in post.items():
                    if hasattr(v, 'filename'):
                        ref_field = v
                        break
                else:
                    raise web.HTTPBadRequest(text='missing reference file upload')

                tmp = tempfile.NamedTemporaryFile(delete=False)
                try:
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
                        la, lb = len(a), len(b)
                        max_len = max(la, lb)
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

            try:
                st = request.app.get('state')
                if st is not None:
                    await st.notify_ber_result(filename, result)
            except Exception:
                LOG.exception('Failed to notify websocket clients about BER result')

            return web.json_response(result)

        app.router.add_post('/api/compute_ber', api_compute_ber)
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
    parser = argparse.ArgumentParser(description="XCOM RX Bridge - Receives files from FTDI Device")
    parser.add_argument("--ws-port", type=int, default=8766, help="WebSocket port for web UI (default: 8766)")
    parser.add_argument("--web-port", type=int, default=8001, help="HTTP port for web UI (default: 8001)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--ftdi-index", type=int, default=2, help="FTDI device index to open if no target is specified (default: 2)")
    parser.add_argument("--ftdi-serial", type=str, default=None, help="Target FTDI serial number to connect to (e.g., FTX9A8B7)")
    parser.add_argument("--ftdi-desc", type=str, default=None, help="Target FTDI description to connect to")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    state = BridgeState()

    # Start web server
    web_runner = await start_web_server(args.host, args.web_port, state)

    # Start FTDI reader in background thread
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, ftd_blocking_reader, loop, state, args.ftdi_serial, args.ftdi_desc, args.ftdi_index)

    # Start WebSocket server (with library version compatibility fix)
    async def handler(ws, *ws_args):
        path = ws_args[0] if ws_args else getattr(getattr(ws, "request", None), "path", "/")
        await ws_handler(ws, path, state)

    try:
        ws_max_mb = int(os.environ.get('WS_MAX_MB', os.environ.get('MAX_UPLOAD_MB', '50')))
    except Exception:
        ws_max_mb = 50
        
    ws_max_size = ws_max_mb * 1024 * 1024
    ws_server = await serve(handler, args.host, args.ws_port, max_size=ws_max_size)
    LOG.info(f"✓ WebSocket server listening on ws://{args.host}:{args.ws_port}")

    # Keep the asyncio event loop running forever
    try:
        await asyncio.Event().wait()
    finally:
        await web_runner.cleanup()
        ws_server.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting")