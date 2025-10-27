/**
 * @file byte_converter.h
 * @brief Header file for byte conversion utilities for XCOM system
 */

#ifndef BYTE_CONVERTER_H
#define BYTE_CONVERTER_H

#include <stdint.h>
#include <stddef.h>

/**
 * @brief Structure to hold file transfer metadata
 */
typedef struct {
    char filename[256];
    uint32_t filesize;
    uint32_t chunks_received;
    uint8_t transfer_complete;
} FileTransferMetadata;

/**
 * @brief Initialize the byte converter system
 * @return 0 on success, negative value on error
 */
int byte_converter_init(void);

/**
 * @brief Process incoming file data from the host
 * @param data Pointer to the received data buffer
 * @param size Size of the received data
 * @param metadata Pointer to file transfer metadata structure
 * @return Number of bytes processed, or negative value on error
 */
int process_file_data(const uint8_t* data, size_t size, FileTransferMetadata* metadata);

/**
 * @brief Check if the entire file has been received and processed
 * @param metadata Pointer to file transfer metadata structure
 * @return 1 if complete, 0 if not complete, negative value on error
 */
int check_transfer_complete(FileTransferMetadata* metadata);

/**
 * @brief Reset the file transfer state
 * @param metadata Pointer to file transfer metadata structure
 */
void reset_transfer(FileTransferMetadata* metadata);

#endif /* BYTE_CONVERTER_H */