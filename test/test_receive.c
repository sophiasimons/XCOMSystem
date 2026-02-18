/**
 * @file test_receive.c
 * @brief Ethernet connectivity test - RX STM32 reception verification
 * @description Tests receiving data from RX STM32 after it receives from X-ray circuit
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>

#ifndef _WIN32
    #include <sys/socket.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    #include <netinet/in.h>
    #include <errno.h>
#else
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
#endif

// Default test configuration
#define DEFAULT_PORT 5000
#define RECEIVE_TIMEOUT_SEC 30  // Wait up to 30 seconds for data

/**
 * @brief Test if host is reachable via ping
 * @param ip_address IP address to ping
 * @return true if reachable, false otherwise
 */
bool test_ping(const char *ip_address) {
    char command[256];
    
#ifndef _WIN32
    // macOS/Linux: ping -c 1 -W 2 (1 packet, 2 second timeout)
    snprintf(command, sizeof(command), "ping -c 1 -W 2 %s > /dev/null 2>&1", ip_address);
#else
    // Windows: ping -n 1 -w 2000 (1 packet, 2000ms timeout)
    snprintf(command, sizeof(command), "ping -n 1 -w 2000 %s > NUL 2>&1", ip_address);
#endif
    
    int result = system(command);
    return (result == 0);
}

/**
 * @brief Test TCP connection to STM32
 * @param ip_address IP address of STM32
 * @param port TCP port number
 * @return true if connection successful, false otherwise
 */
bool test_tcp_connection(const char *ip_address, int port) {
    int sock;
    struct sockaddr_in server_addr;
    
#ifdef _WIN32
    // Initialize Winsock on Windows
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) {
        return false;
    }
#endif
    
    // Create socket
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("  ✗ Failed to create socket\n");
#ifdef _WIN32
        WSACleanup();
#endif
        return false;
    }
    
    // Set connection timeout (2 seconds)
#ifndef _WIN32
    struct timeval timeout;
    timeout.tv_sec = 2;
    timeout.tv_usec = 0;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
#else
    DWORD timeout_ms = 2000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout_ms, sizeof(timeout_ms));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&timeout_ms, sizeof(timeout_ms));
#endif
    
    // Setup server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    
    if (inet_pton(AF_INET, ip_address, &server_addr.sin_addr) <= 0) {
        printf("  ✗ Invalid IP address format\n");
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        return false;
    }
    
    // Attempt connection
    if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        // Connection failed
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        return false;
    }
    
    // Connection successful - close it
#ifndef _WIN32
    close(sock);
#else
    closesocket(sock);
    WSACleanup();
#endif
    
    return true;
}

/**
 * @brief Receive data from RX STM32 and save to file
 * @param ip_address IP address of STM32
 * @param port TCP port number
 * @return true if successful
 */
bool receive_test_data(const char *ip_address, int port) {
    int sock;
    struct sockaddr_in server_addr;
    char *file_buffer = NULL;
    bool success = false;
    
#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);
#endif
    
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("  ✗ Failed to create socket\n");
        return false;
    }
    
    // Set receive timeout to wait for data
#ifndef _WIN32
    struct timeval timeout;
    timeout.tv_sec = RECEIVE_TIMEOUT_SEC;
    timeout.tv_usec = 0;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
#else
    DWORD timeout_ms = RECEIVE_TIMEOUT_SEC * 1000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout_ms, sizeof(timeout_ms));
#endif
    
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, ip_address, &server_addr.sin_addr);
    
    printf("  Connecting to RX STM32 at %s:%d...\n", ip_address, port);
    if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        printf("  ✗ Connection failed\n");
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        return false;
    }
    
    printf("  ✓ Connected! Waiting for data (timeout: %d seconds)...\n", RECEIVE_TIMEOUT_SEC);
    
    // Receive file size first (4 bytes, little-endian)
    uint32_t file_size = 0;
    int received = recv(sock, (char*)&file_size, sizeof(file_size), 0);
    
    if (received != sizeof(file_size)) {
        printf("  ✗ Failed to receive file size (got %d bytes)\n", received);
        if (received == 0) {
            printf("    Connection closed by RX STM32\n");
        } else if (received < 0) {
            printf("    Receive timeout - no data from RX STM32\n");
            printf("    Make sure X-ray circuit has transmitted data\n");
        }
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        return false;
    }
    
    printf("  File size: %u bytes\n", file_size);
    
    if (file_size == 0 || file_size > 10 * 1024 * 1024) {  // Sanity check: max 10MB
        printf("  ✗ Invalid file size: %u bytes\n", file_size);
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        return false;
    }
    
    // Allocate buffer for file data
    file_buffer = (char *)malloc(file_size);
    if (!file_buffer) {
        printf("  ✗ Memory allocation failed\n");
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        return false;
    }
    
    // Receive file data
    uint32_t total_received = 0;
    while (total_received < file_size) {
        int chunk = recv(sock, file_buffer + total_received, file_size - total_received, 0);
        if (chunk <= 0) {
            printf("  ✗ Connection lost during transfer (received %u/%u bytes)\n", 
                   total_received, file_size);
            free(file_buffer);
#ifndef _WIN32
            close(sock);
#else
            closesocket(sock);
            WSACleanup();
#endif
            return false;
        }
        total_received += chunk;
        printf("  Received %u/%u bytes (%.1f%%)\n", 
               total_received, file_size, (total_received * 100.0) / file_size);
    }
    
#ifndef _WIN32
    close(sock);
#else
    closesocket(sock);
    WSACleanup();
#endif
    
    // Save received data to file with timestamp
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    char filename[256];
    snprintf(filename, sizeof(filename), "received_%04d%02d%02d_%02d%02d%02d.txt",
             t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
             t->tm_hour, t->tm_min, t->tm_sec);
    
    FILE *outfile = fopen(filename, "wb");
    if (!outfile) {
        printf("  ✗ Failed to create output file: %s\n", filename);
        free(file_buffer);
        return false;
    }
    
    fwrite(file_buffer, 1, file_size, outfile);
    fclose(outfile);
    
    printf("  ✓ Received %u bytes successfully\n", total_received);
    printf("  ✓ Saved to: %s\n", filename);
    
    // Print content preview
    printf("\n  Content preview:\n");
    printf("  ┌─────────────────────────────────────────────────────┐\n");
    printf("  │ ");
    int preview_len = (file_size < 100) ? file_size : 100;
    for (int i = 0; i < preview_len; i++) {
        if (file_buffer[i] == '\n') {
            printf("\n  │ ");
        } else if (file_buffer[i] == '\r') {
            // Skip carriage returns
        } else if (file_buffer[i] >= 32 && file_buffer[i] <= 126) {
            printf("%c", file_buffer[i]);
        } else {
            printf(".");  // Non-printable characters
        }
    }
    if (file_size > 100) printf("...");
    printf("\n  └─────────────────────────────────────────────────────┘\n");
    
    free(file_buffer);
    return true;
}

/**
 * @brief Main test function
 */
int main(int argc, char *argv[]) {
    const char *rx_stm32_ip = NULL;
    int port = DEFAULT_PORT;
    
    // Parse command line arguments
    if (argc < 2) {
        printf("\n");
        printf("═══════════════════════════════════════════════════════\n");
        printf("  XCOM RX STM32 Ethernet Reception Test\n");
        printf("═══════════════════════════════════════════════════════\n\n");
        printf("Error: IP address is required\n\n");
        printf("Usage: %s <ip_address> [port]\n", argv[0]);
        printf("\nExamples:\n");
        printf("  %s 192.168.1.10          (uses default port 5000)\n", argv[0]);
        printf("  %s 192.168.1.10 5000     (specify custom port)\n", argv[0]);
        printf("  %s 169.254.100.10        (link-local address)\n", argv[0]);
        printf("\n");
        return 1;
    }
    
    rx_stm32_ip = argv[1];
    if (argc > 2) port = atoi(argv[2]);
    
    printf("\n");
    printf("═══════════════════════════════════════════════════════\n");
    printf("  XCOM RX STM32 Ethernet Reception Test\n");
    printf("═══════════════════════════════════════════════════════\n\n");
    printf("Configuration:\n");
    printf("  RX STM32 IP: %s:%d\n", rx_stm32_ip, port);
    printf("\n");
    
    bool all_passed = true;
    
    // Test 1: Ping RX STM32
    printf("[1/3] Testing network connectivity to RX STM32...\n");
    if (test_ping(rx_stm32_ip)) {
        printf("  ✓ RX STM32 is reachable at %s\n", rx_stm32_ip);
    } else {
        printf("  ✗ RX STM32 not reachable at %s\n", rx_stm32_ip);
        printf("    Troubleshooting:\n");
        printf("    - Check Ethernet cable is connected\n");
        printf("    - Verify IP address is correct\n");
        printf("    - Ensure both devices on same network/subnet\n");
        printf("    - Try: ping %s\n", rx_stm32_ip);
        all_passed = false;
    }
    
    // Test 2: TCP connection to RX STM32
    printf("\n[2/3] Testing TCP connection to RX STM32 port %d...\n", port);
    if (test_tcp_connection(rx_stm32_ip, port)) {
        printf("  ✓ RX STM32 is responding on port %d\n", port);
    } else {
        printf("  ✗ Cannot connect to RX STM32 on port %d\n", port);
        printf("    Troubleshooting:\n");
        printf("    - Verify rx_main.c is flashed and running on STM32\n");
        printf("    - Check port %d is not blocked by firewall\n", port);
        printf("    - Ensure Ethernet peripheral is initialized\n");
        printf("    - Verify LwIP is configured in STM32CubeIDE\n");
        all_passed = false;
    }
    
    // Test 3: Receive data
    if (all_passed) {
        printf("\n[3/3] Waiting to receive data from RX STM32...\n");
        printf("  NOTE: RX STM32 sends data when it receives from X-ray circuit\n");
        printf("  Make sure TX side has sent data first!\n\n");
        
        if (receive_test_data(rx_stm32_ip, port)) {
            printf("  ✓ Data received successfully from RX STM32\n");
            printf("  ✓ End-to-end communication is working!\n");
        } else {
            printf("  ✗ Failed to receive data\n");
            printf("    - RX STM32 may not have data to send yet\n");
            printf("    - X-ray circuit may not have transmitted anything\n");
            printf("    - Try sending data from TX side first\n");
            all_passed = false;
        }
    } else {
        printf("\n[3/3] Skipping data receive test (connection failed)\n");
    }
    
    // Final summary
    printf("\n");
    printf("═══════════════════════════════════════════════════════\n");
    if (all_passed) {
        printf("  ✓ All tests PASSED!\n");
        printf("\n  RX STM32 is working correctly:\n");
        printf("  • Network: Connected ✓\n");
        printf("  • TCP Connection: Working ✓\n");
        printf("  • Data Reception: Successful ✓\n");
    } else {
        printf("  ✗ Some tests FAILED\n");
        printf("\n  Please fix the issues above before proceeding\n");
        printf("\n  Common fixes:\n");
        printf("  • Check Ethernet cables and connections\n");
        printf("  • Verify STM32 IP in .ioc file matches %s\n", rx_stm32_ip);
        printf("  • Ensure rx_main.c is compiled with HAL_ETH_MODULE_ENABLED\n");
        printf("  • Flash rx_main.c to STM32 RX board\n");
        printf("  • Make sure data was sent from TX side first\n");
    }
    printf("═══════════════════════════════════════════════════════\n\n");
    
    return all_passed ? 0 : 1;
}
