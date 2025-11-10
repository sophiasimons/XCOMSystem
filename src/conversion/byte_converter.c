/**
 * @file byte_converter.c
 * @brief Simple implementation for receiving files on STM32
 */

#include "byte_converter.h"
#include <string.h>  // for memcpy

int file_init(FileReceiver* receiver, uint32_t total_size) {
    if (!receiver || total_size == 0) {
        return STATUS_ERROR;
    }
    
    receiver->total_size = total_size;
    receiver->total_received = 0;
    receiver->current_chunk = 0;
    receiver->is_receiving = 1;

    // Initialize all chunks
    for (int i = 0; i < NUM_CHUNKS; i++) {
        receiver->chunks[i].bytes_received = 0;
        receiver->chunks[i].state = CHUNK_FREE;
    }
    
    // Set first chunk as ready to receive
    receiver->chunks[0].state = CHUNK_FILLING;
    
    return STATUS_OK;
}

int file_process_data(FileReceiver* receiver, const uint8_t* data, size_t size) {
    if (!receiver || !data || !receiver->is_receiving) {
        return STATUS_ERROR;
    }

    Chunk* current = &receiver->chunks[receiver->current_chunk];
    
    // Check if current chunk is ready for data
    if (current->state != CHUNK_FILLING) {
        return STATUS_BUSY;
    }

    // Calculate space left in current chunk
    size_t space_left = CHUNK_SIZE - current->bytes_received;
    size_t bytes_to_copy = (size > space_left) ? space_left : size;

    if (bytes_to_copy > 0) {
        // Copy data to current chunk
        memcpy(current->data + current->bytes_received, data, bytes_to_copy);
        current->bytes_received += bytes_to_copy;
        receiver->total_received += bytes_to_copy;

        // Check if chunk is full
        if (current->bytes_received == CHUNK_SIZE) {
            current->state = CHUNK_FULL;
            
            // Move to next chunk if available
            if (receiver->current_chunk < NUM_CHUNKS - 1) {
                receiver->current_chunk++;
                receiver->chunks[receiver->current_chunk].state = CHUNK_FILLING;
            }
        }

        // Check if entire transfer is complete
        if (receiver->total_received >= receiver->total_size) {
            receiver->is_receiving = 0;
            current->state = CHUNK_FULL;
        }
    }

    return bytes_to_copy;
}

int file_is_complete(const FileReceiver* receiver) {
    if (!receiver) {
        return 0;
    }
    return (!receiver->is_receiving && receiver->total_received >= receiver->total_size);
}

const uint8_t* file_get_data(const FileReceiver* receiver) {
    if (!receiver || receiver->is_receiving) {
        return NULL;
    }
    return receiver->chunks[0].data;
}

const uint8_t* file_get_chunk(const FileReceiver* receiver, uint8_t chunk_index, uint32_t* size) {
    if (!receiver || chunk_index >= NUM_CHUNKS || !size) {
        return NULL;
    }

    const Chunk* chunk = &receiver->chunks[chunk_index];
    
    // Only return data if chunk is full or it's the last chunk and reception is complete
    if (chunk->state == CHUNK_FULL || 
        (!receiver->is_receiving && chunk_index == receiver->current_chunk)) {
        *size = chunk->bytes_received;
        return chunk->data;
    }
    
    return NULL;
}

int file_reset_chunk(FileReceiver* receiver, uint8_t chunk_index) {
    if (!receiver || chunk_index >= NUM_CHUNKS) {
        return STATUS_ERROR;
    }

    Chunk* chunk = &receiver->chunks[chunk_index];
    chunk->bytes_received = 0;
    chunk->state = CHUNK_FREE;

    return STATUS_OK;
}

uint8_t file_get_progress(const FileReceiver* receiver, uint32_t* total, uint32_t* received) {
    if (!receiver || !total || !received) {
        return 0;
    }

    *total = receiver->total_size;
    *received = receiver->total_received;

    // Calculate progress percentage
    if (receiver->total_size == 0) {
        return 0;
    }
    
    return (uint8_t)((receiver->total_received * 100) / receiver->total_size);
}