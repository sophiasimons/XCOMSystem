/**
 * @file tx_main.c
 * @brief XCOM Transmitter - Sends file data to STM32 (FIXED VERSION)
 */

#include "../conversion/byte_converter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Test file path (will be replaced with UI input later)
#define TEST_FILE_PATH "test/butterfly.jpeg"

// Function prototypes
int load_file(const char* filepath, uint8_t** buffer, uint32_t* size);
void transmit_chunk(const uint8_t* data, uint32_t size);
void cleanup(uint8_t* buffer);

/**
 * @brief Main transmitter function
 */
int main(void) {
    printf("=== XCOM Transmitter Started ===\n");
    
    // STEP 1: Initialize hardware (STM32 peripherals)
    // TODO: Uncomment when ready for hardware
    // HAL_Init();
    // SystemClock_Config();
    // MX_GPIO_Init();
    // MX_USART2_UART_Init();
    printf("Hardware initialized\n");
    
    // STEP 2: Load file from disk
    uint8_t* file_data = NULL;
    uint32_t file_size = 0;
    
    printf("Loading file: %s\n", TEST_FILE_PATH);
    
    if (load_file(TEST_FILE_PATH, &file_data, &file_size) != 0) {
        printf("ERROR: Failed to load file\n");
        return -1;
    }
    
    printf("File loaded: %u bytes\n", file_size);
    
    // STEP 3: Initialize transmitter
    FileReceiver transmitter;
    
    // STEP 4 & 5: Stream file in multiple 64KB passes

    printf("\nStarting transmission (file will be sent in 64KB passes)...\n");
    printf("Total file size: %u bytes\n", file_size);
    
    uint32_t total_sent = 0;
    uint32_t file_offset = 0;
    uint32_t pass = 0;
    
    // Process file in BUFFER_SIZE (64KB) chunks
    while (total_sent < file_size) {
        // Calculate how much to process in this pass
        uint32_t remaining = file_size - file_offset;
        uint32_t pass_size = (remaining > BUFFER_SIZE) ? BUFFER_SIZE : remaining;
        
        // Skip if no data left (safety check)
        if (pass_size == 0) {
            break;
        }
        
        printf("\n>>> Pass %u: Processing %u bytes (offset %u) <<<\n", 
               pass, pass_size, file_offset);
        
        // Initialize for this pass
        if (file_init(&transmitter, pass_size) != STATUS_OK) {
            printf("ERROR: Failed to init transmitter for pass %u\n", pass);
            cleanup(file_data);
            return -1;
        }
        
        // Load ALL data for this pass (may need multiple calls to fill all chunks)
        uint32_t pass_offset = 0;
        while (pass_offset < pass_size) {
            int result = file_process_data(&transmitter, 
                                          file_data + file_offset + pass_offset, 
                                          pass_size - pass_offset);
            if (result < 0) {
                printf("ERROR: Failed to process data\n");
                cleanup(file_data);
                return -1;
            } else if (result == 0) {
                break;  // No more data processed
            }
            pass_offset += result;
        }
        
        // Transmit all chunks in this pass
        for (uint8_t chunk_idx = 0; chunk_idx < NUM_CHUNKS; chunk_idx++) {
            uint32_t chunk_size;
            const uint8_t* chunk_data = file_get_chunk(&transmitter, chunk_idx, &chunk_size);
            
            if (chunk_data != NULL && chunk_size > 0) {
                printf("  Chunk %u: Transmitting %u bytes\n", chunk_idx, chunk_size);
                transmit_chunk(chunk_data, chunk_size);
                total_sent += chunk_size;
                
                // Show overall progress
                uint8_t progress = (total_sent * 100) / file_size;
                printf("  Progress: %u%% (%u/%u bytes)\n", 
                       progress, total_sent, file_size);
            } else {
                break;  // No more chunks in this pass
            }
        }
        
        file_offset += pass_size;
        pass++;
    }
    
    // STEP 6: Verify transmission complete
    printf("\n");
    if (total_sent == file_size) {
        printf("✓ Transmission complete: %u bytes sent in %u passes\n", total_sent, pass);
    } else {
        printf("✗ Transmission incomplete: %u/%u bytes\n", total_sent, file_size);
    }
    
    // STEP 7: Cleanup
    cleanup(file_data);
    printf("=== Transmitter Finished ===\n");
    
    while (1) {
        // Main loop
    }
    
    return 0;
}

/**
 * @brief Load file from disk into memory
 */
int load_file(const char* filepath, uint8_t** buffer, uint32_t* size) {
    FILE* file = fopen(filepath, "rb");
    if (!file) {
        printf("ERROR: Cannot open file: %s\n", filepath);
        return -1;
    }
    
    fseek(file, 0, SEEK_END);
    *size = ftell(file);
    fseek(file, 0, SEEK_SET);
    
    *buffer = (uint8_t*)malloc(*size);
    if (!*buffer) {
        printf("ERROR: Cannot allocate memory\n");
        fclose(file);
        return -1;
    }
    
    size_t bytes_read = fread(*buffer, 1, *size, file);
    fclose(file);
    
    if (bytes_read != *size) {
        printf("ERROR: Failed to read complete file\n");
        free(*buffer);
        *buffer = NULL;
        return -1;
    }
    
    return 0;
}

/**
 * @brief Transmit chunk via UART/SPI
 */
void transmit_chunk(const uint8_t* data, uint32_t size) {
    // TODO: HAL_UART_Transmit(&huart4, (uint8_t*)data, size, HAL_MAX_DELAY);
    printf("    [TX] Sent %u bytes\n", size);
}

/**
 * @brief Cleanup allocated memory
 */
void cleanup(uint8_t* buffer) {
    if (buffer) {
        free(buffer);
        printf("Memory cleaned up\n");
    }
}
