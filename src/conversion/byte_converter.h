/**
 * @file byte_converter.h
 * @brief Simple file handling for STM32
 */

#ifndef BYTE_CONVERTER_H
#define BYTE_CONVERTER_H

#include <stdint.h>
#include <stddef.h>

// Buffer and chunk sizes (in bytes)
#define CHUNK_SIZE      (16 * 1024)  // 16KB chunks
#define NUM_CHUNKS      4            // Number of chunk buffers
#define BUFFER_SIZE     (CHUNK_SIZE * NUM_CHUNKS)  // Total buffer size 64KB

// Status codes
#define STATUS_OK       0
#define STATUS_ERROR   -1
#define STATUS_FULL    -2
#define STATUS_BUSY    -3

// Chunk states
#define CHUNK_FREE     0
#define CHUNK_FILLING  1
#define CHUNK_FULL     2
#define CHUNK_ERROR    3

/**
 * @brief Structure to manage a single data chunk
 */
typedef struct {
    uint8_t data[CHUNK_SIZE];    // Chunk data buffer
    uint32_t bytes_received;     // Bytes received in this chunk
    uint8_t state;              // Chunk state (FREE/FILLING/FULL/ERROR)
} Chunk;

/**
 * @brief Structure to track file reception
 */
typedef struct {
    uint32_t total_size;         // Total expected file size
    uint32_t total_received;     // Total bytes received
    Chunk chunks[NUM_CHUNKS];    // Array of chunk buffers
    uint8_t current_chunk;       // Index of current chunk
    uint8_t is_receiving;        // Currently receiving data?
} FileReceiver;

/**
 * @brief Initialize a new file reception
 * @param receiver Pointer to FileReceiver structure
 * @param total_size Expected size of the file
 * @return STATUS_OK on success, STATUS_ERROR on failure
 */
int file_init(FileReceiver* receiver, uint32_t total_size);

/**
 * @brief Process received data bytes
 * @param receiver Pointer to FileReceiver structure
 * @param data Pointer to received data
 * @param size Size of received data
 * @return Number of bytes processed, or STATUS_ERROR on failure
 */
int file_process_data(FileReceiver* receiver, const uint8_t* data, size_t size);

/**
 * @brief Check if file reception is complete
 * @param receiver Pointer to FileReceiver structure
 * @return 1 if complete, 0 if not complete
 */
int file_is_complete(const FileReceiver* receiver);

/**
 * @brief Get pointer to received data buffer
 * @param receiver Pointer to FileReceiver structure
 * @return Pointer to data buffer
 */
const uint8_t* file_get_data(const FileReceiver* receiver);

/**
 * @brief Get current chunk data
 * @param receiver Pointer to FileReceiver structure
 * @param chunk_index Index of the chunk to access
 * @param size Pointer to store chunk size
 * @return Pointer to chunk data, NULL if invalid
 */
const uint8_t* file_get_chunk(const FileReceiver* receiver, uint8_t chunk_index, uint32_t* size);

/**
 * @brief Reset a chunk to free state
 * @param receiver Pointer to FileReceiver structure
 * @param chunk_index Index of the chunk to reset
 * @return STATUS_OK on success, STATUS_ERROR on failure
 */
int file_reset_chunk(FileReceiver* receiver, uint8_t chunk_index);

/**
 * @brief Get progress of file reception
 * @param receiver Pointer to FileReceiver structure
 * @param total Pointer to store total size
 * @param received Pointer to store received bytes
 * @return Progress percentage (0-100)
 */
uint8_t file_get_progress(const FileReceiver* receiver, uint32_t* total, uint32_t* received);

#endif /* BYTE_CONVERTER_H */
