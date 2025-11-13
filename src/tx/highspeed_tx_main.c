/**
 * @file tx_main.c
 * @brief XCOM Transmitter - High-Speed (80MHz+) LibUSB Version
 */

#include <libusb-1.0/libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Your Nucleo's VID/PID
// 0x0483 is STMicroelectronics
#define STM_VID 0x0483 
// Unique PID for pairing
#define NUCLEO_PID 0xXXXX 

// Bulk out endpoint
#define ENDPOINT_OUT 0x02

// File to send
#define TEST_FILE_PATH "test/butterfly.jpeg"
#define CHUNK_SIZE 16384 // 16KB per transfer

// Global libusb handle
libusb_device_handle *dev_handle = NULL;

// Function Prototypes
int load_file(const char* filepath, uint8_t** buffer, uint32_t* size);
void cleanup(uint8_t* buffer);
int init_usb();
int transmit_chunk(const uint8_t* data, uint32_t size);


/**
 * @brief Main transmitter function
 */
int main(void) {
    printf("=== XCOM High-Speed Transmitter ===\n");

    // STEP 1: Initialize LibUSB and find device
    if (init_usb() != 0) {
        return -1;
    }

    // STEP 2: Load file from disk
    uint8_t* file_data = NULL;
    uint32_t file_size = 0;
    
    if (load_file(TEST_FILE_PATH, &file_data, &file_size) != 0) {
        printf("ERROR: Failed to load file\n");
        libusb_release_interface(dev_handle, 0);
        libusb_close(dev_handle);
        libusb_exit(NULL);
        return -1;
    }
    printf("File loaded: %u bytes\n", file_size);

    // STEP 3: Stream file in chunks
    printf("Starting transmission...\n");
    
    uint32_t total_sent = 0;
    while (total_sent < file_size) {
        uint32_t remaining = file_size - total_sent;
        uint32_t pass_size = (remaining > CHUNK_SIZE) ? CHUNK_SIZE : remaining;
        
        int bytes_sent = transmit_chunk(file_data + total_sent, pass_size);
        
        if (bytes_sent < 0) {
            printf("Transmission failed with error: %s\n", libusb_strerror(bytes_sent));
            break;
        } else if (bytes_sent != pass_size) {
            printf("WARN: Sent %d bytes, expected %d\n", bytes_sent, pass_size);
        }
        
        total_sent += bytes_sent;
        
        uint8_t progress = (total_sent * 100) / file_size;
        printf("Progress: %u%% (%u/%u bytes)\n", 
               progress, total_sent, file_size);
    }

    // STEP 4: Verify
    if (total_sent == file_size) {
        printf("✓ Transmission complete: %u bytes sent\n", total_sent);
    } else {
        printf("✗ Transmission incomplete: %u/%u bytes\n", total_sent, file_size);
    }

    // STEP 5: Cleanup
    cleanup(file_data);
    libusb_release_interface(dev_handle, 0);
    libusb_close(dev_handle);
    libusb_exit(NULL);
    printf("=== Transmitter Finished ===\n");
    
    return 0;
}

/**
 * @brief Initialize libusb, find, and claim the Nucleo
 */
int init_usb() {
    if (libusb_init(NULL) < 0) {
        printf("ERROR: Failed to initialize libusb\n");
        return -1;
    }

    dev_handle = libusb_open_device_with_vid_pid(NULL, STM_VID, NUCLEO_PID);
    if (dev_handle == NULL) {
        printf("ERROR: Cannot find Nucleo device (VID=0x%04X, PID=0x%04X)\n", STM_VID, NUCLEO_PID);
        printf("       Is it plugged in? Check PID in CubeMX!\n");
        printf("       WINDOWS: Did you run Zadig to install WinUSB driver?\n");
        libusb_exit(NULL);
        return -1;
    }
    printf("Nucleo device found!\n");

    // Detach kernel driver if active (common on Linux)
    if (libusb_kernel_driver_active(dev_handle, 0) == 1) {
        printf("Detaching kernel driver...\n");
        libusb_detach_kernel_driver(dev_handle, 0);
    }

    // Claim the interface (usually interface 0)
    if (libusb_claim_interface(dev_handle, 0) < 0) {
        printf("ERROR: Cannot claim interface\n");
        libusb_close(dev_handle);
        libusb_exit(NULL);
        return -1;
    }
    printf("Interface claimed.\n");
    return 0;
}

/**
 * @brief Transmit chunk via USB BULK transfer
 */
int transmit_chunk(const uint8_t* data, uint32_t size) {
    int actual_length; // Number of bytes actually sent
    
    // This is the core function
    // We send 'size' bytes to the 'ENDPOINT_OUT'
    // with a 1000ms timeout.
    int r = libusb_bulk_transfer(
        dev_handle,
        ENDPOINT_OUT,
        (unsigned char*)data, // Data to send
        size,                 // Length of data
        &actual_length,       // Bytes actually written
        1000                  // Timeout (ms)
    );

    if (r < 0) {
        return r; // Return the libusb error code
    }
    
    return actual_length;
}


// --- load_file and cleanup are unchanged ---

int load_file(const char* filepath, uint8_t** buffer, uint32_t* size) {
    // ... (same as before) ...
    FILE* file = fopen(filepath, "rb");
    if (!file) { return -1; }
    fseek(file, 0, SEEK_END);
    *size = ftell(file);
    fseek(file, 0, SEEK_SET);
    *buffer = (uint8_t*)malloc(*size);
    if (!*buffer) { fclose(file); return -1; }
    fread(*buffer, 1, *size, file);
    fclose(file);
    return 0;
}

void cleanup(uint8_t* buffer) {
    // ... (same as before) ...
    if (buffer) free(buffer);
}