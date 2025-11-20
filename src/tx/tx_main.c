/**
 * @file tx_main.c
 * @brief XCOM TX STM32 - Receives file from TX laptop via Ethernet
 * 
 * This STM32 receives files from the TX laptop and stores them in memory.
 * The X-ray communication circuit will access this data to transmit to RX STM32.
 * 
 * Architecture:
 * TX Laptop → [Ethernet] → THIS STM32 → [X-ray circuit code] → RX STM32
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// Uncomment when integrating with STM32 HAL:
//#define HAL_ETH_MODULE_ENABLED
//#include "stm32h7xx_hal.h"
//#include "lwip/tcp.h"
//#include "lwip/sockets.h"

// Server configuration (this STM32 is the server)
#define SERVER_PORT 5000
#define MAX_FILE_SIZE (10 * 1024 * 1024)  // 10MB max

// Global file buffer for X-ray circuit to access
static uint8_t* g_file_buffer = NULL;
static uint32_t g_file_size = 0;
static volatile uint8_t g_file_ready = 0;  // Flag for X-ray circuit

// Function prototypes
int start_ethernet_server(void);
int receive_file(int client_sock, uint8_t** buffer, uint32_t* size);
void process_file(uint8_t* data, uint32_t size);
void cleanup(uint8_t* buffer);

/**
 * @brief Main function - STM32 TX receiver
 */
int main(void) {
    printf("=== XCOM TX STM32 Receiver Started ===\n");
    
    // STEP 1: Initialize hardware (STM32 peripherals + Ethernet)
#ifdef HAL_ETH_MODULE_ENABLED
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_ETH_Init();
    MX_LWIP_Init();
    printf("Hardware and Ethernet initialized\n");
#else
    printf("Running in simulation mode (no hardware)\n");
#endif
    
    // STEP 2: Start server and wait for files from TX laptop
    printf("Starting TCP server on port %d...\n", SERVER_PORT);
    printf("Waiting for files from TX laptop...\n");
    
    if (start_ethernet_server() != 0) {
        printf("ERROR: Failed to start server\n");
        return -1;
    }
    
#ifdef HAL_ETH_MODULE_ENABLED
    while (1) {
        // Main loop for embedded systems
        MX_LWIP_Process();  // Process lwIP stack
    }
#endif
    
    return 0;
}

/**
 * @brief Start TCP server and listen for connections
 */
int start_ethernet_server(void) {
#ifdef HAL_ETH_MODULE_ENABLED
    // Real STM32 lwIP TCP server
    int server_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (server_sock < 0) {
        printf("ERROR: Failed to create socket\n");
        return -1;
    }
    
    // Allow port reuse
    int opt = 1;
    setsockopt(server_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(SERVER_PORT);
    server_addr.sin_addr.s_addr = INADDR_ANY;
    
    // Bind to port
    if (bind(server_sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        printf("ERROR: Failed to bind to port %d\n", SERVER_PORT);
        close(server_sock);
        return -1;
    }
    
    // Listen for connections
    if (listen(server_sock, 5) < 0) {
        printf("ERROR: Failed to listen on port %d\n", SERVER_PORT);
        close(server_sock);
        return -1;
    }
    
    printf("✓ Server listening on port %d\n", SERVER_PORT);
    
    // Accept connections in a loop
    while (1) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        
        printf("\nWaiting for connection from TX laptop...\n");
        int client_sock = accept(server_sock, (struct sockaddr*)&client_addr, &client_len);
        
        if (client_sock < 0) {
            printf("ERROR: Failed to accept connection\n");
            continue;
        }
        
        printf("✓ TX Laptop connected\n");
        
        // Clean up old file if exists
        if (g_file_buffer) {
            cleanup(g_file_buffer);
            g_file_buffer = NULL;
        }
        g_file_ready = 0;
        
        // Receive file
        if (receive_file(client_sock, &g_file_buffer, &g_file_size) == 0) {
            printf("✓ File received: %u bytes\n", g_file_size);
            process_file(g_file_buffer, g_file_size);
            g_file_ready = 1;  // Signal to X-ray circuit that file is ready
            
            // Note: Don't cleanup g_file_buffer - X-ray circuit needs it!
        } else {
            printf("✗ File reception failed\n");
        }
        
        close(client_sock);
        printf("TX Laptop disconnected\n");
    }
    
    close(server_sock);
    return 0;
    
#else
    // Simulation mode (for testing without hardware)
    printf("Simulating TCP server on port %d\n", SERVER_PORT);
    printf("In simulation mode - server would wait for TX laptop connections here\n");
    return 0;
#endif
}

/**
 * @brief Receive file data from TCP socket
 */
int receive_file(int client_sock, uint8_t** buffer, uint32_t* size) {
#ifdef HAL_ETH_MODULE_ENABLED
    // Receive file size first (4 bytes, little-endian)
    uint32_t file_size = 0;
    int received = recv(client_sock, &file_size, sizeof(file_size), 0);
    
    if (received != sizeof(file_size)) {
        printf("ERROR: Failed to receive file size\n");
        return -1;
    }
    
    printf("Receiving file: %u bytes\n", file_size);
    
    if (file_size > MAX_FILE_SIZE) {
        printf("ERROR: File too large (%u bytes, max %u)\n", file_size, MAX_FILE_SIZE);
        return -1;
    }
    
    // Allocate buffer for file
    *buffer = (uint8_t*)malloc(file_size);
    if (!*buffer) {
        printf("ERROR: Cannot allocate %u bytes\n", file_size);
        return -1;
    }
    
    // Receive file data
    uint32_t total_received = 0;
    while (total_received < file_size) {
        received = recv(client_sock, *buffer + total_received, file_size - total_received, 0);
        
        if (received <= 0) {
            printf("ERROR: Connection lost during transfer\n");
            free(*buffer);
            *buffer = NULL;
            return -1;
        }
        
        total_received += received;
        
        // Show progress every 10%
        if ((total_received * 10 / file_size) != ((total_received - received) * 10 / file_size)) {
            printf("Progress: %u%%\n", (total_received * 100) / file_size);
        }
    }
    
    *size = file_size;
    return 0;
    
#else
    // Simulation mode
    printf("Simulating file reception...\n");
    *size = 0;
    *buffer = NULL;
    return 0;
#endif
}

/**
 * @brief Process received file - prepare for X-ray transmission
 */
void process_file(uint8_t* data, uint32_t size) {
    printf("\n=== File Ready for X-ray Transmission ===\n");
    printf("Size: %u bytes\n", size);
    printf("Buffer address: %p\n", (void*)data);
    
    // Show first 32 bytes
    printf("First 32 bytes (hex):\n");
    for (uint32_t i = 0; i < (size < 32 ? size : 32); i++) {
        printf("%02X ", data[i]);
        if ((i + 1) % 16 == 0) printf("\n");
    }
    printf("\n");
    
    // TODO: X-ray circuit code will access g_file_buffer and g_file_size
    // Examples:
    // - Read bytes sequentially: data[0], data[1], ...
    // - Use byte_converter.c to chunk if needed for X-ray protocol
    // - Modulate bytes into X-ray signal
    
    printf("✓ File ready - X-ray circuit can now access global buffer\n");
    printf("  Access via: extern uint8_t* g_file_buffer;\n");
    printf("  Size via:   extern uint32_t g_file_size;\n");
    printf("  Ready flag: extern volatile uint8_t g_file_ready;\n");
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

/**
 * @brief Public API for X-ray circuit code to access file data
 */
 
// Declare these as extern in your X-ray circuit code:
// extern uint8_t* g_file_buffer;
// extern uint32_t g_file_size;
// extern volatile uint8_t g_file_ready;

/**
 * Example usage from X-ray circuit code:
 * 
 * extern uint8_t* g_file_buffer;
 * extern uint32_t g_file_size;
 * extern volatile uint8_t g_file_ready;
 * 
 * void xray_transmit_file(void) {
 *     // Wait for file to be ready
 *     while (!g_file_ready);
 *     
 *     // Transmit all bytes
 *     for (uint32_t i = 0; i < g_file_size; i++) {
 *         uint8_t byte = g_file_buffer[i];
 *         xray_send_byte(byte);  // Your X-ray modulation function
 *     }
 *     
 *     g_file_ready = 0;  // Mark as processed
 * }
 */
