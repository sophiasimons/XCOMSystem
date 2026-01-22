# Ethernet-Based File Transfer System

## Overview

The system has been simplified to use **Ethernet instead of USB/UART**. This eliminates the need for chunking and makes file transfers much faster and more reliable.

## Architecture

```
┌─────────────┐        WebSocket    ┌──────────┐      Ethernet TCP      ┌────────────┐
│   Browser   │         ─────────>  │ bridge.py│ ───────────────>       │ STM32 TX   │ ─────────────> Circuit
│     UI      │                     │ (laptop) │                        │            │
└─────────────┘                     └──────────┘                        └────────────┘
```

### Key Components:

1. **Browser UI** (`host-ui-tx/web/app/`)
   - Upload files via web interface
   - Monitor connection status

2. **Bridge.py** (`host-ui-tx/bridge/bridge.py`)
   - WebSocket server for UI communication
   - **NEW**: Uses TCP sockets to send files to STM32
   - No more serial port scanning

3. **STM32 Receiver** (`src/rx/rx_main.c`)
   - Listens on TCP port 5000
   - Receives entire file in one connection
   - No chunking needed - unlimited file size

## Setup Instructions (testing)

### 1. Configure STM32 Ethernet


In STM32CubeIDE:
1. Enable Ethernet in `.ioc` file:
   - Go to **Connectivity** → **ETH**
   - Enable Ethernet with default settings
   - Set your STM32 IP address (e.g., `192.168.1.100`)

2. Enable LwIP middleware:
   - Go to **Middleware** → **LWIP**
   - Enable LwIP
   - Configure IP address in LWIP settings


3. Generate code

### 2. Update STM32 Receiver Code

1. Copy `src/rx/rx_main.c` to your STM32 project
2. Uncomment the HAL defines at the top:
   ```c
   #define HAL_ETH_MODULE_ENABLED
   #include "stm32h7xx_hal.h"
   #include "lwip/tcp.h"
   #include "lwip/sockets.h"
   ```
3. Compile and flash to STM32

### 3. Run the Bridge

Start the bridge with your STM32's IP address:

```bash
cd host-ui-tx/bridge
python bridge.py --stm32-ip 192.168.1.100 --stm32-port 5000
```

The bridge will:
- Start WebSocket server on `ws://127.0.0.1:8765`
- Start web UI server on `http://127.0.0.1:8000`
- Connect to STM32 at `192.168.1.100:5000`

### 4. Use the Web UI

1. Open browser to `http://127.0.0.1:8000`
2. Check connection status (green dot = connected)
3. Upload files - they'll be sent directly to STM32 via Ethernet

## Network Configuration

### Option 1: Direct Connection (Simplest)
- Connect STM32 directly to your laptop via Ethernet cable
- Configure static IPs:
  - **Laptop**: `192.168.1.1`
  - **STM32**: `192.168.1.100`

### Option 2: Same Network
- Connect both laptop and STM32 to same router/switch
- Use DHCP or configure static IPs
- Make sure they can ping each other

### Testing Connection

Test if STM32 is reachable:
```bash
ping 192.168.1.100
```

## Benefits Over USB/Serial

1. **Simpler Code**: No chunking, no buffer management
2. **Faster**: Ethernet is much faster than 115200 baud UART
3. **Reliable**: TCP handles retransmission automatically
4. **Unlimited File Size**: Send files of any size
5. **No Cable Issues**: More robust than USB connections
6. **Multiple Connections**: Can handle multiple clients

## Troubleshooting

### Connection Failed
- Check STM32 IP address is correct
- Verify both devices are on same network
- Check firewall settings
- Try pinging STM32: `ping 192.168.1.100`

### File Transfer Failed
- Check STM32 server is running
- Verify port 5000 is not blocked
- Check STM32 has enough RAM for file

### UI Shows Disconnected
- Bridge might not be running
- Wrong STM32 IP address in bridge.py arguments
- STM32 server not started yet

## Example Usage

### Start Everything:

1. **Flash STM32** with `rx_ethernet.c`
2. **Start Bridge**:
   ```bash
   python bridge.py --stm32-ip 192.168.1.100
   ```
3. **Open Browser**: `http://127.0.0.1:8000`
4. **Upload Files**: Drag & drop or click to select

### Monitor in Terminal:

Bridge shows all activity:
```
INFO:bridge:STM32 reachable at 192.168.1.100:5000
INFO:bridge:WebSocket bridge listening on ws://127.0.0.1:8765
INFO:bridge:Web UI server running at http://127.0.0.1:8000
INFO:bridge:Client connected: ('127.0.0.1', 54321)
INFO:bridge:Sending myfile.txt (1024 bytes) to 192.168.1.100:5000...
INFO:bridge:File transfer complete: myfile.txt
```

## Old Files

These are kept for reference but not used with Ethernet, will be removed once Ethernet finalized as connection method:
- `src/conversion/byte_converter.c` - Chunking not needed anymore
- `test/test_connection.c` - USB connection test
- `test/test_byte_converter.c` - Chunking tests

