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
- **File**: `src/tx/tx_main.c`
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
- **File**: `src/rx/rx_main.c`
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
- **File**: `host-ui-rx/bridge/bridge_new.py`
- **Protocol**: TCP/IP (Ethernet)
- **Direction**: STM32 initiates connection to laptop
- **Connection**:
  - RX Laptop listens on port `5000`
  - STM32 RX connects to `192.168.1.200:5000` (example)
- **No chunking needed** - TCP handles flow control

## File Responsibilities

### TX Side

**`host-ui-tx/bridge/bridge.py`** (TX Laptop):
- ✅ Receives file from web UI via WebSocket
- ✅ Sends file to STM32 TX via Ethernet TCP
- ✅ No modifications needed from Ethernet update

**`src/tx/tx_main.c`** (STM32 TX):
- ✅ Runs TCP server on port 5000
- ✅ Receives file from TX laptop
- ✅ Stores in `g_file_buffer` for X-ray circuit
- ✅ Provides API for X-ray circuit to access data

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

**`src/rx/rx_main.c`** (STM32 RX):
- ✅ Waits for `g_rx_complete` flag from X-ray circuit
- ✅ Connects to RX laptop via Ethernet TCP
- ✅ Sends complete file to RX laptop
- ✅ Provides API for X-ray circuit to provide data

**`host-ui-rx/bridge/bridge_new.py`** (RX Laptop):
- ✅ Runs TCP server on port 5000
- ✅ Receives file from STM32 RX
- ✅ Saves to disk: `received_files/received_TIMESTAMP.bin`
- ✅ Sends to web UI via WebSocket

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

## Do You Need byte_converter.c?

### For Ethernet Parts: **NO**
- TCP handles all chunking/reassembly automatically
- No manual buffer management needed

### For X-Ray Circuit: **MAYBE**
- If X-ray protocol needs chunking: Use `byte_converter.c`
- If X-ray can handle arbitrary file sizes: Don't need it
- **Your decision** based on X-ray circuit capabilities

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
python bridge_new.py --listen-port 5000
# Opens web UI at http://127.0.0.1:8001
```

## File Summary

### ✅ Files You Need (Updated for X-ray System)
- `host-ui-tx/bridge/bridge.py` - TX laptop sender
- `src/tx/tx_main.c` - STM32 TX receiver (from Ethernet) + X-ray interface
- `src/rx/rx_main.c` - STM32 RX sender (to Ethernet) + X-ray interface
- `host-ui-rx/bridge/bridge_new.py` - RX laptop receiver

### ⚠️ Files for X-Ray Circuit (Your Responsibility)
- X-ray transmitter code (reads from STM32 TX)
- X-ray receiver code (writes to STM32 RX)
- May optionally use `byte_converter.c` for chunking

### ❌ Files You Don't Need
- `src/tx/tx_main.c` (old version that sent via Ethernet - deleted)
- `test/test_connection.c` (USB/serial test - not using USB anymore)
- `src/rx/rx_ethernet.c` (old version - replaced by rx_main.c)

## Testing End-to-End

1. **Upload file** on TX laptop web UI
2. **TX bridge.py** sends to STM32 TX via Ethernet ✓
3. **STM32 TX** stores in `g_file_buffer` ✓
4. **X-ray TX circuit** reads buffer and transmits
5. **X-ray RX circuit** receives and writes to `g_rx_buffer`
6. **STM32 RX** sends `g_rx_buffer` to RX laptop ✓
7. **RX bridge.py** receives and displays in web UI ✓

## Next Steps

1. Configure Ethernet IP addresses in your `.ioc` file
2. Enable LwIP in STM32CubeIDE
3. Uncomment `#define HAL_ETH_MODULE_ENABLED` in both tx_main.c and rx_main.c
4. Flash STM32s with updated code
5. Develop X-ray circuit communication layer
6. Test end-to-end!

## Questions?

- **TX/RX bridges**: Handled by your code (Ethernet) ✓
- **X-ray communication**: Handled by separate circuit code (your responsibility)
- **Interface**: Global variables provide clean handoff between Ethernet and X-ray parts

Good luck with your X-ray communication prototype! 🚀
