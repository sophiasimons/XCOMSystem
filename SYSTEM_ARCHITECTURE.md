# XCOM System Architecture - X-Ray Communication Prototype

## Complete System Overview

```
┌──────────────┐        ┌───────────┐        ┌──────────┐        ┌───────────┐        ┌──────────────┐
│  TX Laptop   │──ETH──>│ STM32 TX  │───X───>│  X-RAY   │───X───>│ STM32 RX  │──ETH──>│  RX Laptop   │
│  (bridge.py) │        │(tx_main.c)│  RAY   │ CIRCUIT  │  RAY   │(rx_main.c)│        │ (bridge.py)  │
│              │        │           │        │ (separate│        │           │        │              │
│   Web UI     │        │  Receives │        │   code)  │        │  Sends to │        │   Web UI     │
└──────────────┘        └───────────┘        └──────────┘        └───────────┘        └──────────────┘
```

## Data Flow

### Phase 1: TX Laptop → STM32 TX (Ethernet)
- **File**: `host-ui-tx/bridge/bridge.py`
- **Protocol**: TCP/IP (Ethernet)
- **Direction**: Laptop sends file to STM32
- **Connection**: 
  - STM32 TX IP: `192.168.1.100:5000` (example)
  - Bridge connects as TCP client
- **No chunking needed** - TCP handles flow control

### Phase 2: STM32 TX → X-ray Circuit (Your Custom Protocol)
- **What it does**:
  - Receives file from bridge.py via Ethernet
  - Stores in global buffer `g_file_buffer`
  - Sets `g_file_ready = 1` flag
- **Interface for X-ray circuit**:
  ```c
  extern uint8_t* g_file_buffer;      // Pointer to file data
  extern uint32_t g_file_size;        // File size in bytes
  extern volatile uint8_t g_file_ready;  // 1 when file ready
  ```
- **X-ray circuit responsibility**: Read bytes and modulate into X-ray signal

### Phase 3: X-ray Circuit → STM32 RX (Your Custom Protocol)
- **What it expects**:
  - X-ray circuit writes received bytes to global buffer
  - X-ray circuit sets completion flag
- **Interface for X-ray circuit**:
  ```c
  extern uint8_t* g_rx_buffer;        // X-ray circuit allocates and fills this
  extern uint32_t g_rx_size;          // X-ray circuit sets this
  extern volatile uint8_t g_rx_complete;  // X-ray circuit sets to 1 when done
  ```
- **X-ray circuit responsibility**: Demodulate X-ray signal and write bytes

### Phase 4: STM32 RX → RX Laptop (Ethernet)
- **File**: `host-ui-rx/bridge/bridge.py`
- **Protocol**: TCP/IP (Ethernet)
- **Direction**: STM32 RX connects to laptop (STM32 is TCP client)
- **Connection**:
  - RX Laptop listens on port `5000` (TCP server)
  - STM32 RX connects to RX Laptop IP address
- **No chunking needed** - TCP handles flow control

## File Responsibilities

### TX Side

**`host-ui-tx/bridge/bridge.py`** (TX Laptop):
- ✅ Receives file from web UI via WebSocket
- ✅ Connects to STM32 TX via Ethernet TCP (acts as TCP client)
- ✅ Sends file size (4 bytes) + file data
- ✅ Serves web UI on port 8000, WebSocket on port 8765

**`src/tx/tx_main.c`** (STM32 TX - Reference Implementation):
- ✅ Runs TCP server on port 5000
- ✅ Receives file size (4 bytes) + file data from TX laptop
- ✅ Stores in `g_file_buffer` for X-ray circuit
- ✅ Provides API for X-ray circuit to access data
- 📝 **Note**: Copy this code into your STM32CubeIDE project (e.g., `XCOM_Transmitter/`)

### X-Ray Circuit (Your Separate Code)

**TX Side** - Must read from STM32 TX:
```c
#include <stdint.h>

extern uint8_t* g_file_buffer;
extern uint32_t g_file_size;
extern volatile uint8_t g_file_ready;

void xray_transmit_file(void) {
    // Wait for file to be ready
    while (!g_file_ready);
    
    // Transmit all bytes via X-ray
    for (uint32_t i = 0; i < g_file_size; i++) {
        uint8_t byte = g_file_buffer[i];
        xray_modulate_and_send(byte);  // Your X-ray TX function
    }
    
    g_file_ready = 0;  // Mark as processed
}
```

**RX Side** - Must write to STM32 RX:
```c
#include <stdint.h>
#include <stdlib.h>

extern uint8_t* g_rx_buffer;
extern uint32_t g_rx_size;
extern volatile uint8_t g_rx_complete;

void xray_receive_file(void) {
    // Get file size from X-ray header/protocol
    uint32_t expected_size = xray_read_file_size();
    
    // Allocate buffer
    g_rx_buffer = (uint8_t*)malloc(expected_size);
    g_rx_size = 0;
    g_rx_complete = 0;
    
    // Receive all bytes
    while (g_rx_size < expected_size) {
        uint8_t byte = xray_demodulate_and_receive();  // Your X-ray RX function
        g_rx_buffer[g_rx_size++] = byte;
    }
    
    // Signal completion
    g_rx_complete = 1;
}
```

### RX Side

**`src/rx/rx_main.c`** (STM32 RX - Reference Implementation):
- ✅ Waits for `g_rx_complete` flag from X-ray circuit
- ✅ Connects to RX laptop via Ethernet TCP (acts as TCP client)
- ✅ Sends file size (4 bytes) + file data to RX laptop
- ✅ Provides API for X-ray circuit to provide data
- 📝 **Note**: Copy this code into your STM32CubeIDE project (e.g., `XCOM Receiver/`)

**`host-ui-rx/bridge/bridge.py`** (RX Laptop):
- ✅ Runs TCP server on port 5000 (listens for STM32 RX)
- ✅ Receives file size (4 bytes) + file data from STM32 RX
- ✅ Saves to disk: `received_files/received_YYYYMMDD_HHMMSS.bin`
- ✅ Notifies web UI via WebSocket
- ✅ Serves web UI on port 8001, WebSocket on port 8766

## Network Configuration

### TX Side Network
```
TX Laptop: 192.168.1.1
  |
  | Ethernet cable
  |
STM32 TX:  192.168.1.100 (listening on port 5000)
```

### RX Side Network
```
RX Laptop: 192.168.1.200 (listening on port 5000)
  |
  | Ethernet cable
  |
STM32 RX:  192.168.1.201
```

## Unused Files (Legacy/Optional)

### `file_transfer.py` (Both TX and RX bridges)
- ❌ **NOT NEEDED** - Was for chunking in USB/UART system
- Ethernet uses simple file size + data protocol
- TCP handles flow control automatically
- Can be safely deleted

### `byte_converter.c` 
- ❌ **NOT NEEDED for Ethernet** - TCP handles everything
- ⚠️ **MAYBE for X-ray circuit** - If your X-ray protocol needs chunking
- Your decision based on X-ray circuit capabilities

### `bridge_usb.py` (RX side)
- ❌ **NOT NEEDED** - Old USB/UART implementation
- Replaced by Ethernet in `bridge.py`
- Can be safely deleted

## Starting the System

### 1. TX Side
```bash
cd host-ui-tx/bridge
python bridge.py --stm32-ip 192.168.1.100 --stm32-port 5000
# Opens web UI at http://127.0.0.1:8000
```

### 2. STM32 TX
- Flash with `src/tx/tx_main.c`
- Ensure Ethernet configured with IP `192.168.1.100`
- Will listen on port 5000

### 3. X-Ray Circuit
- Runs your separate code
- TX side: Reads from `g_file_buffer` on STM32 TX
- RX side: Writes to `g_rx_buffer` on STM32 RX

### 4. STM32 RX
- Flash with `src/rx/rx_main.c`
- Ensure Ethernet configured with IP `192.168.1.201`
- Configure RX laptop IP in code: `#define RX_LAPTOP_IP "192.168.1.200"`

### 5. RX Side
```bash
cd host-ui-rx/bridge
python bridge.py --listen-port 5000 --ws-port 8766 --web-port 8001
# Opens web UI at http://127.0.0.1:8001
# Listens for STM32 RX connections on port 5000
```

## File Summary

### ✅ Core Files You Need
**TX Laptop:**
- `host-ui-tx/bridge/bridge.py` - Sends files to STM32 TX via Ethernet
- `host-ui-tx/web/app/` - Web UI for file uploads

**RX Laptop:**
- `host-ui-rx/bridge/bridge.py` - Receives files from STM32 RX via Ethernet  
- `host-ui-rx/web/app/` - Web UI for viewing received files

**STM32 Reference Code:**
- `src/tx/tx_main.c` - Reference implementation for STM32 TX (copy to your STM32CubeIDE project)
- `src/rx/rx_main.c` - Reference implementation for STM32 RX (copy to your STM32CubeIDE project)

**Testing:**
- `test/test_connection.c` - Tests TX STM32 Ethernet connection
- `test/test_receive.c` - Tests RX STM32 Ethernet connection
- `test/txtFile.txt` - Sample test file

### ⚠️ Files for X-Ray Circuit (Your Responsibility)
- X-ray transmitter code (reads from `g_file_buffer` on STM32 TX)
- X-ray receiver code (writes to `g_rx_buffer` on STM32 RX)
- May optionally use `byte_converter.c` for chunking

### ❌ Files You Don't Need (Can Delete)
- `host-ui-tx/bridge/file_transfer.py` - Old chunking code for USB/UART
- `host-ui-rx/bridge/file_transfer.py` - Old chunking code for USB/UART
- `host-ui-rx/bridge/bridge_usb.py` - Old USB/UART implementation
- Any `byte_converter` files (unless needed for X-ray circuit)

## Testing the System

### Unit Tests (Before X-ray circuit integration)

**Test TX STM32 Connection:**
```bash
cd test
gcc test_connection.c -o test_connection
./test_connection 192.168.1.100 5000
```
This verifies:
- ✓ STM32 TX is reachable via Ethernet
- ✓ TCP server is running on port 5000
- ✓ STM32 can receive files

**Test RX STM32 Connection:**
```bash
cd test
gcc test_receive.c -o test_receive
./test_receive 192.168.1.101 5000
```
This verifies:
- ✓ STM32 RX is reachable via Ethernet
- ✓ STM32 can connect and send files
- ✓ Files are received and saved correctly

### End-to-End Test (With X-ray circuit)

1. **Upload file** on TX laptop web UI (http://127.0.0.1:8000)
2. **TX bridge.py** sends to STM32 TX via Ethernet ✓
3. **STM32 TX** stores in `g_file_buffer` ✓
4. **X-ray TX circuit** reads buffer and transmits via X-ray
5. **X-ray RX circuit** receives and writes to `g_rx_buffer`
6. **STM32 RX** sends `g_rx_buffer` to RX laptop ✓
7. **RX bridge.py** receives and saves to `received_files/` ✓
8. **View file** on RX laptop web UI (http://127.0.0.1:8001)

## Next Steps

1. Configure Ethernet IP addresses in your `.ioc` file
2. Enable LwIP in STM32CubeIDE
3. Uncomment `#define HAL_ETH_MODULE_ENABLED` in both tx_main.c and rx_main.c
4. Flash STM32s with updated code
5. Develop X-ray circuit communication layer
6. Test end-to-end
