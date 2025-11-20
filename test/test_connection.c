/**
 * @file test_connection.c
 * @brief Ethernet connectivity test - TX STM32 connection verification
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

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

// Default test configuration (can be overridden with command line args)
#define DEFAULT_TX_STM32_IP "192.168.1.100"
#define DEFAULT_PORT 5000

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
 * @brief Send test data through TCP connection
 * @param ip_address IP address of STM32
 * @param port TCP port number
 * @return true if successful
 */
bool send_test_data(const char *ip_address, int port) {
    int sock;
    struct sockaddr_in server_addr;
    FILE *file = NULL;
    char *file_buffer = NULL;
    long file_size = 0;
    bool success = false;
    
    // Open and read the test text file
    const char *filename = "txtFile.txt";
    file = fopen(filename, "rb");
    if (!file) {
        printf("  ✗ Failed to open %s\n", filename);
        printf("    Make sure %s exists in the current directory\n", filename);
        return false;
    }
    
    // Get file size
    fseek(file, 0, SEEK_END);
    file_size = ftell(file);
    fseek(file, 0, SEEK_SET);
    
    if (file_size <= 0) {
        printf("  ✗ File %s is empty or invalid\n", filename);
        fclose(file);
        return false;
    }
    
    // Allocate buffer and read file
    file_buffer = (char *)malloc(file_size);
    if (!file_buffer) {
        printf("  ✗ Memory allocation failed\n");
        fclose(file);
        return false;
    }
    
    size_t bytes_read = fread(file_buffer, 1, file_size, file);
    fclose(file);
    file = NULL;
    
    if (bytes_read != file_size) {
        printf("  ✗ Failed to read complete file\n");
        free(file_buffer);
        return false;
    }
    
    printf("  Loaded %ld bytes from '%s'\n", file_size, filename);
    
    // Initialize socket
#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);
#endif
    
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("  ✗ Failed to create socket\n");
        free(file_buffer);
        return false;
    }
    
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, ip_address, &server_addr.sin_addr);
    
    if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        printf("  ✗ Connection failed\n");
#ifndef _WIN32
        close(sock);
#else
        closesocket(sock);
        WSACleanup();
#endif
        free(file_buffer);
        return false;
    }
    
    // Send file size first (4 bytes, little-endian)
    uint32_t size_to_send = (uint32_t)file_size;
    send(sock, (char*)&size_to_send, sizeof(size_to_send), 0);
    
    // Send file data
    int sent = send(sock, file_buffer, file_size, 0);
    
    if (sent == file_size) {
        printf("  ✓ Sent %d bytes from '%s'\n", sent, filename);
        // Print first 50 chars of file content
        int preview_len = (file_size < 50) ? file_size : 50;
        printf("  Content preview: \"");
        for (int i = 0; i < preview_len; i++) {
            if (file_buffer[i] == '\n') printf("\\n");
            else if (file_buffer[i] == '\r') printf("\\r");
            else printf("%c", file_buffer[i]);
        }
        if (file_size > 50) printf("...");
        printf("\"\n");
        success = true;
    } else {
        printf("  ✗ Failed to send complete file (sent %d/%ld bytes)\n", sent, file_size);
    }
    
#ifndef _WIN32
    close(sock);
#else
    closesocket(sock);
    WSACleanup();
#endif
    
    free(file_buffer);
    return success;
}

/**
 * @brief Main test function
 */
int main(int argc, char *argv[]) {
    const char *tx_stm32_ip = DEFAULT_TX_STM32_IP;
    int port = DEFAULT_PORT;
    
    // Parse command line arguments
    if (argc > 1) tx_stm32_ip = argv[1];
    if (argc > 2) port = atoi(argv[2]);
    
    printf("\n");
    printf("═══════════════════════════════════════════════════════\n");
    printf("  XCOM TX STM32 Ethernet Connection Test\n");
    printf("═══════════════════════════════════════════════════════\n\n");
    printf("Configuration:\n");
    printf("  TX STM32 IP: %s:%d\n", tx_stm32_ip, port);
    printf("\n");
    
    bool all_passed = true;
    
    // Test 1: Ping TX STM32
    printf("[1/3] Testing network connectivity to TX STM32...\n");
    if (test_ping(tx_stm32_ip)) {
        printf("  ✓ TX STM32 is reachable at %s\n", tx_stm32_ip);
    } else {
        printf("  ✗ TX STM32 not reachable at %s\n", tx_stm32_ip);
        printf("    Troubleshooting:\n");
        printf("    - Check Ethernet cable is connected\n");
        printf("    - Verify IP address is correct\n");
        printf("    - Ensure both devices on same network/subnet\n");
        printf("    - Try: ping %s\n", tx_stm32_ip);
        all_passed = false;
    }
    
    // Test 2: TCP connection to TX STM32
    printf("\n[2/3] Testing TCP connection to TX STM32 port %d...\n", port);
    if (test_tcp_connection(tx_stm32_ip, port)) {
        printf("  ✓ TCP server is running on TX STM32\n");
    } else {
        printf("  ✗ Cannot connect to TX STM32 on port %d\n", port);
        printf("    Troubleshooting:\n");
        printf("    - Verify tx_main.c is flashed and running on STM32\n");
        printf("    - Check port %d is not blocked by firewall\n", port);
        printf("    - Ensure Ethernet peripheral is initialized\n");
        printf("    - Verify LwIP is configured in STM32CubeIDE\n");
        all_passed = false;
    }
    
    // Test 3: Send test data
    if (all_passed) {
        printf("\n[3/3] Sending test data to TX STM32...\n");
        if (send_test_data(tx_stm32_ip, port)) {
            printf("  ✓ Test data sent successfully\n");
            printf("  ✓ TX STM32 is accepting file transfers\n");
        } else {
            printf("  ✗ Failed to send test data\n");
            printf("    - Connection may have been lost\n");
            printf("    - STM32 may not be processing data correctly\n");
            all_passed = false;
        }
    } else {
        printf("\n[3/3] Skipping data send test (connection failed)\n");
    }
    
    // Final summary
    printf("\n");
    printf("═══════════════════════════════════════════════════════\n");
    if (all_passed) {
        printf("  ✓ All tests PASSED!\n");
        printf("\n  TX STM32 is ready to receive files:\n");
        printf("  • Network: Connected ✓\n");
        printf("  • TCP Server: Running ✓\n");
        printf("  • Data Transfer: Working ✓\n");
        printf("\n  Next steps:\n");
        printf("  1. Start TX bridge: python bridge.py --stm32-ip %s\n", tx_stm32_ip);
        printf("  2. Open web UI: http://127.0.0.1:8000\n");
        printf("  3. Upload a file to test end-to-end\n");
    } else {
        printf("  ✗ Some tests FAILED\n");
        printf("\n  Please fix the issues above before proceeding\n");
        printf("\n  Common fixes:\n");
        printf("  • Check Ethernet cables and connections\n");
        printf("  • Verify STM32 IP in .ioc file matches %s\n", tx_stm32_ip);
        printf("  • Ensure tx_main.c is compiled with HAL_ETH_MODULE_ENABLED\n");
        printf("  • Flash tx_main.c to STM32 TX board\n");
    }
    printf("═══════════════════════════════════════════════════════\n\n");
    
    printf("Usage: %s [tx_ip] [port]\n", argv[0]);
    printf("Example: %s %s %d\n\n", argv[0], tx_stm32_ip, port);
    
    return all_passed ? 0 : 1;
}
