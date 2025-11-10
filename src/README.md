PLANNED SRC FILE STRUCTURE: 

XCOMSTM32/
├── src/
│   ├── conversion/              # Shared code for both TX and RX
│   │   ├── file_transfer.h
│   │   └── file_transfer.c
│   ├── tx/                  # Transmitter-specific code
│   │   ├── tx_main.c
│   │   └── file_reader.c    # Read file and chunk it
│   └── rx/                  # Receiver-specific code
│       ├── rx_main.c
│       └── file_writer.c    # Write chunks to file