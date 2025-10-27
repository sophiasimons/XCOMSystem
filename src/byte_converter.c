/**
 * @file byte_converter.c
 * @brief Implementation of byte conversion utilities for XCOM system
 */

#include "byte_converter.h"
#include <string.h>

// Maximum size for received data chunks
#define MAX_CHUNK_SIZE 1024

// Internal state tracking
static struct {
    uint8_t initialized;
    uint32_t bytes_processed;
    uint8_t buffer[MAX_CHUNK_SIZE];
} converter_state = {0};

int byte_converter_init(void) {
    // Initialize internal state
    memset(&converter_state, 0, sizeof(converter_state));
    converter_state.initialized = 1;
    return 0;
}

int process_file_data(const uint8_t* data, size_t size, FileTransferMetadata* metadata) {
    if (!data || !metadata || !converter_state.initialized) {
        return -1;
    }

    // Check if this is the start of a new transfer
    if (metadata->chunks_received == 0) {
        // Reset internal state for new transfer
        converter_state.bytes_processed = 0;
        metadata->transfer_complete = 0;
    }

    // Process the incoming data chunk
    size_t bytes_to_process = (size > MAX_CHUNK_SIZE) ? MAX_CHUNK_SIZE : size;
    memcpy(converter_state.buffer, data, bytes_to_process);

    // TODO: Add your specific byte conversion logic here
    // For example:
    // - Parse file headers
    // - Convert endianness if needed
    // - Handle specific file formats
    // - Implement error checking

    // Update progress
    converter_state.bytes_processed += bytes_to_process;
    metadata->chunks_received++;

    // Check if we've received the complete file
    if (converter_state.bytes_processed >= metadata->filesize) {
        metadata->transfer_complete = 1;
    }

    return bytes_to_process;
}

int check_transfer_complete(FileTransferMetadata* metadata) {
    if (!metadata || !converter_state.initialized) {
        return -1;
    }
    return metadata->transfer_complete;
}

void reset_transfer(FileTransferMetadata* metadata) {
    if (metadata) {
        memset(metadata, 0, sizeof(FileTransferMetadata));
    }
    converter_state.bytes_processed = 0;
}