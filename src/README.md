# XCOM System Source Code

This directory contains the source code for the XCOM system's microcontroller components.

## File Structure

- `byte_converter.h` - Header file defining the byte conversion interface
- `byte_converter.c` - Implementation of byte conversion utilities
- Additional files can be organized as follows:
  ```
  src/
  ├── byte_converter.h      # Byte conversion interface
  ├── byte_converter.c      # Byte conversion implementation
  ├── file_handler.h        # File operations interface (if needed)
  ├── file_handler.c        # File operations implementation
  └── main.c               # Main application entry point
  ```

## Byte Converter Usage

The byte converter module provides functionality for handling file transfers and byte conversions:

```c
#include "byte_converter.h"

// Initialize the converter
byte_converter_init();

// Set up file transfer metadata
FileTransferMetadata metadata = {0};
strcpy(metadata.filename, "example.dat");
metadata.filesize = expected_size;

// Process incoming data chunks
uint8_t buffer[1024];
size_t bytes_received;
// ... receive data into buffer ...
int processed = process_file_data(buffer, bytes_received, &metadata);

// Check if transfer is complete
if (check_transfer_complete(&metadata)) {
    // Handle completed transfer
}
```

## Development Notes

1. Keep chunk sizes reasonable for STM32 memory constraints
2. Consider implementing error detection/correction
3. Add file format validation if needed
4. Consider adding progress reporting functionality
5. Remember to handle endianness issues