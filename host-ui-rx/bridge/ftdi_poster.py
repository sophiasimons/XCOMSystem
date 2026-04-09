#!/usr/bin/env python3
"""
Simple FTDI reader that parses framed files from FT232H and notifies the
bridge running on localhost by POSTing to /api/notify_new_file.

Frame format expected (same as bridge):
  [START_FLAG (4 bytes)] [header_len (4 bytes little-endian)] [header_json (header_len bytes utf-8)] [payload]

This script writes files into the local ./received_files folder (which should
be mounted into the bridge container) and then notifies the bridge.

Note: requires `ftd2xx` Python binding on the host and `requests`.
"""

import json
import time
from pathlib import Path
import sys

START_FLAG = b"\xAA\xBB\xCC\xDD"

try:
    import ftd2xx as ftd
except Exception as e:
    print(f"[ftd_poster] ftd2xx import failed: {e}")
    sys.exit(1)

try:
    import requests
except Exception as e:
    print(f"[ftd_poster] requests import failed: {e}")
    sys.exit(1)

BRIDGE_NOTIFY_URL = "http://127.0.0.1:8001/api/notify_new_file"


def main(device_index=2):
    try:
        dev = ftd.open(device_index)
    except Exception as e:
        print(f"[ftd_poster] Failed to open FTDI device index {device_index}: {e}")
        sys.exit(1)

    try:
        dev.resetDevice()
        dev.setUSBParameters(65536, 65536)
        dev.setTimeouts(1000, 1000)
        dev.setBitMode(0x00, 0x00)
        dev.purge(ftd.defines.PURGE_RX | ftd.defines.PURGE_TX)
    except Exception as e:
        print(f"[ftd_poster] Device configuration failed: {e}")
        dev.close()
        sys.exit(1)

    buf = bytearray()
    received_dir = Path('received_files')
    received_dir.mkdir(parents=True, exist_ok=True)

    print("[ftd_poster] Listening for framed files from FTDI...")
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
                    filename = f"received_{time.strftime('%Y%m%d_%H%M%S')}.bin"

                mimetype = metadata.get('mimetype') if isinstance(metadata.get('mimetype'), str) else None

                # write file
                outpath = received_dir / filename
                try:
                    outpath.write_bytes(payload)
                    print(f"[ftd_poster] Saved {outpath} ({len(payload)} bytes)")
                except Exception as e:
                    print(f"[ftd_poster] Failed to write file: {e}")
                    continue

                # notify bridge
                try:
                    resp = requests.post(BRIDGE_NOTIFY_URL, json={"filename": filename, "mimetype": mimetype})
                    if resp.status_code == 200:
                        print(f"[ftd_poster] Notified bridge about {filename}")
                    else:
                        print(f"[ftd_poster] Bridge notify failed: {resp.status_code} {resp.text}")
                except Exception as e:
                    print(f"[ftd_poster] Failed to POST to bridge: {e}")

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("[ftd_poster] Stopped by user")
    finally:
        try:
            dev.close()
        except Exception:
            pass


if __name__ == '__main__':
    idx = 2
    if len(sys.argv) > 1:
        try:
            idx = int(sys.argv[1])
        except Exception:
            pass
    main(idx)
