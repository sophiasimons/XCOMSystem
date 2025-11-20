/**
 * @file rx_main.c
 * @brief XCOM RX STM32 - Receives file from X-ray circuit and sends to RX laptop
 * 
 * This STM32 receives data from the X-ray communication circuit,
 * reassembles the file, and sends it to the RX laptop via Ethernet.
 * 
 * Architecture:
 * TX STM32 → [X-ray circuit] → THIS STM32 → [Ethernet] → RX Laptop
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

// RX Laptop configuration
#define RX_LAPTOP_IP "192.168.1.200"  // RX laptop IP address
#define RX_LAPTOP_PORT 5000

// Global buffer for X-ray circuit to write received data
static uint8_t* g_rx_buffer = NULL;
static uint32_t g_rx_size = 0;
static volatile uint8_t g_rx_complete = 0;  // Flag from X-ray circuit

// Function prototypes
int send_to_rx_laptop(const uint8_t* data, uint32_t size);
void wait_for_xray_data(void);
void cleanup(uint8_t* buffer);

/**
 * @brief Main function - STM32 RX sender
 */
int main(void) {
    printf("=== XCOM RX STM32 Sender Started ===\n");
    
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
    
    // STEP 2: Wait for X-ray circuit to receive data
    printf("Waiting for data from X-ray circuit...\n");
    
    while (1) {
        wait_for_xray_data();
        
        if (g_rx_complete && g_rx_buffer && g_rx_size > 0) {
            printf("✓ Received %u bytes from X-ray circuit\n", g_rx_size);
            
            // Send to RX laptop
            if (send_to_rx_laptop(g_rx_buffer, g_rx_size) == 0) {
                printf("✓ File sent to RX laptop successfully\n");
            } else {
                printf("✗ Failed to send file to RX laptop\n");
            }
            
            // Cleanup
            cleanup(g_rx_buffer);
            g_rx_buffer = NULL;
            g_rx_size = 0;
            g_rx_complete = 0;
        }
        
#ifdef HAL_ETH_MODULE_ENABLED
        MX_LWIP_Process();  // Process lwIP stack
        HAL_Delay(100);     // Small delay
#else
        // In simulation, break after first iteration
        break;
#endif
    }
    
    return 0;
}

/**
 * @brief Wait for X-ray circuit to signal data is ready
 */
void wait_for_xray_data(void) {
    // Poll the g_rx_complete flag set by X-ray circuit
    // In real implementation, this could be interrupt-driven
    
#ifdef HAL_ETH_MODULE_ENABLED
    // Wait for flag
    while (!g_rx_complete) {
        MX_LWIP_Process();
        HAL_Delay(10);
    }
#else
    printf("Simulating wait for X-ray data reception...\n");
    
    // Simulate receiving some test data
    const char* test_data = "Test file from X-ray circuit";
    g_rx_size = strlen(test_data);
    g_rx_buffer = (uint8_t*)malloc(g_rx_size);
    if (g_rx_buffer) {
        memcpy(g_rx_buffer, test_data, g_rx_size);
        g_rx_complete = 1;
    }
#endif
}

/**
 * @brief Send file to RX laptop via Ethernet
 */
int send_to_rx_laptop(const uint8_t* data, uint32_t size) {
    if (!data || size == 0) {
        printf("ERROR: Invalid data or size\n");
        return -1;
    }
    
#ifdef HAL_ETH_MODULE_ENABLED
    // Real STM32 lwIP TCP transmission
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("ERROR: Failed to create socket\n");
        return -1;
    }
    
    struct sockaddr_in laptop_addr;
    laptop_addr.sin_family = AF_INET;
    laptop_addr.sin_port = htons(RX_LAPTOP_PORT);
    inet_pton(AF_INET, RX_LAPTOP_IP, &laptop_addr.sin_addr);
    
    // Connect to RX laptop
    if (connect(sock, (struct sockaddr*)&laptop_addr, sizeof(laptop_addr)) < 0) {
        printf("ERROR: Failed to connect to RX laptop at %s:%d\n", 
               RX_LAPTOP_IP, RX_LAPTOP_PORT);
        close(sock);
        return -1;
    }
    
    printf("Connected to RX laptop\n");
    
    // Send file size first (4 bytes, little-endian)
    send(sock, &size, sizeof(size), 0);
    
    // Send entire file
    uint32_t sent = 0;
    while (sent < size) {
        int result = send(sock, data + sent, size - sent, 0);
        if (result < 0) {
            printf("ERROR: Failed to send data\n");
            close(sock);
            return -1;
        }
        sent += result;
        
        // Show progress every 10%
        if (size > 1000 && (sent * 10 / size) != ((sent - result) * 10 / size)) {
            printf("Progress: %u%%\n", (sent * 100) / size);
        }
    }
    
    close(sock);
    printf("Sent %u bytes successfully to RX laptop\n", sent);
    return 0;
    
#else
    // Simulation mode
    printf("Simulating Ethernet transmission to RX laptop:\n");
    printf("  Destination: %s:%d\n", RX_LAPTOP_IP, RX_LAPTOP_PORT);
    printf("  Data size: %u bytes\n", size);
    printf("  First 32 bytes: ");
    for (uint32_t i = 0; i < (size < 32 ? size : 32); i++) {
        printf("%02X ", data[i]);
        if ((i + 1) % 16 == 0) printf("\n                  ");
    }
    printf("\n");
    return 0;
#endif
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

