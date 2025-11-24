PLANNED SRC FILE STRUCTURE: 

```bash
XCOMSTM32/
├── src/
│   ├── conversion/          # Shared code for both TX and RX
│   │   ├── byte_converter.h
│   │   └── byte_converter.c
│   ├── tx/                  # Transmitter-specific code
│   │   ├── tx_main.c
│   └── rx/                  # Receiver-specific code
│       ├── rx_main.c

```