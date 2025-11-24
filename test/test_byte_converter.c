#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "../src/conversion/byte_converter.h"

// ============================================================================
// Simple Test Framework
// ============================================================================

static int tests_run = 0;
static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) \
    printf("\n--- Test %d: %s ---\n", ++tests_run, name)

#define ASSERT(condition, msg) \
    do { \
        if (condition) { \
            printf("  ✓ %s\n", msg); \
        } else { \
            printf("  ✗ FAIL: %s\n", msg); \
            tests_failed++; \
            return; \
        } \
    } while(0)

#define TEST_PASS() \
    do { \
        tests_passed++; \
        printf("  PASSED\n"); \
    } while(0)

// ============================================================================
// Unit Tests
// ============================================================================

// Test 1: Basic initialization
void test_init(void) {
    TEST("Initialize receiver");
    
    FileReceiver receiver;
    int result = file_init(&receiver, 1000);
    
    ASSERT(result == STATUS_OK, "Init returns OK");
    ASSERT(receiver.total_size == 1000, "Total size is 1000");
    ASSERT(receiver.total_received == 0, "Received is 0");
    ASSERT(receiver.current_chunk == 0, "Current chunk is 0");
    ASSERT(receiver.is_receiving == 1, "Is receiving flag set");
    ASSERT(receiver.chunks[0].state == CHUNK_FILLING, "First chunk is FILLING");
    
    TEST_PASS();
}

// Test 2: Error handling - null pointer: not null
void test_null_pointer(void) {
    TEST("Null pointer handling");
    
    int result = file_init(NULL, 1000);
    ASSERT(result == STATUS_ERROR, "Returns error for NULL");
    
    TEST_PASS();
}

// Test 3: Error handling - zero size: not zero
void test_zero_size(void) {
    TEST("Zero size handling");
    
    FileReceiver receiver;
    int result = file_init(&receiver, 0);
    ASSERT(result == STATUS_ERROR, "Returns error for zero size");
    
    TEST_PASS();
}

// Test 4: Process small data: 10-byte chunks
void test_small_data(void) {
    TEST("Process 100 bytes in 10-byte chunks");
    
    FileReceiver receiver;
    uint8_t test_data[100];
    
    // Fill test pattern
    for (int i = 0; i < 100; i++) {
        test_data[i] = i;
    }
    
    file_init(&receiver, 100);
    
    // Process in chunks
    for (int i = 0; i < 10; i++) {
        int result = file_process_data(&receiver, &test_data[i*10], 10);
        ASSERT(result == 10, "Processed 10 bytes");
    }
    
    ASSERT(receiver.total_received == 100, "Total received is 100");
    ASSERT(file_is_complete(&receiver), "Reception complete");
    
    TEST_PASS();
}


// Test 5: Multi-chunk (large file)
void test_multi_chunk(void) {
    TEST("Multi-chunk file (20KB)");
    
    FileReceiver receiver;
    file_init(&receiver, 20000);
    
    // Fill first chunk (16384 bytes)
    uint8_t buffer1[16384];
    memset(buffer1, 0xAA, sizeof(buffer1));
    int result1 = file_process_data(&receiver, buffer1, 16384);
    
    ASSERT(result1 == 16384, "First chunk processed");
    ASSERT(receiver.chunks[0].state == CHUNK_FULL, "First chunk FULL");
    ASSERT(receiver.current_chunk == 1, "Moved to chunk 1");
    
    // Fill remaining (3616 bytes)
    uint8_t buffer2[3616];
    memset(buffer2, 0xBB, sizeof(buffer2));
    int result2 = file_process_data(&receiver, buffer2, 3616);
    
    ASSERT(result2 == 3616, "Remaining bytes processed");
    ASSERT(receiver.total_received == 20000, "Total is 20000");
    ASSERT(file_is_complete(&receiver), "File complete");
    
    TEST_PASS();
}

// Test 6: Progress tracking
void test_progress(void) {
    TEST("Progress tracking");
    
    FileReceiver receiver;
    file_init(&receiver, 1000);
    
    uint8_t buffer[250];
    memset(buffer, 0xFF, sizeof(buffer));
    
    uint32_t total, received;
    uint8_t progress;
    
    // 0%
    progress = file_get_progress(&receiver, &total, &received);
    ASSERT(progress == 0, "Progress at 0%");
    
    // 25%
    file_process_data(&receiver, buffer, 250);
    progress = file_get_progress(&receiver, &total, &received);
    ASSERT(progress == 25, "Progress at 25%");
    
    // 50%
    file_process_data(&receiver, buffer, 250);
    progress = file_get_progress(&receiver, &total, &received);
    ASSERT(progress == 50, "Progress at 50%");
    
    // 100%
    file_process_data(&receiver, buffer, 250);
    file_process_data(&receiver, buffer, 250);
    progress = file_get_progress(&receiver, &total, &received);
    ASSERT(progress == 100, "Progress at 100%");
    
    TEST_PASS();
}

// Test 7: Chunk reset: reusing memory 
void test_chunk_reset(void) {
    TEST("Chunk reset functionality");
    
    FileReceiver receiver;
    file_init(&receiver, 100);
    
    uint8_t buffer[100];
    file_process_data(&receiver, buffer, 100);
    
    int result = file_reset_chunk(&receiver, 0);
    ASSERT(result == STATUS_OK, "Reset successful");
    ASSERT(receiver.chunks[0].state == CHUNK_FREE, "Chunk is FREE");
    ASSERT(receiver.chunks[0].bytes_received == 0, "Bytes reset to 0");
    
    TEST_PASS();
}

// Test 8: Large file stress test
void test_large_file(void) {
    TEST("Large file stress test (50KB)");
    
    FileReceiver receiver;
    uint32_t test_size = 50000;
    
    file_init(&receiver, test_size);
    
    // Send 1KB at a time
    uint8_t buffer[1024];
    for (uint32_t i = 0; i < test_size; i += 1024) {
        for (int j = 0; j < 1024; j++) {
            buffer[j] = (i + j) & 0xFF;
        }
        
        uint32_t bytes_to_send = (test_size - i > 1024) ? 1024 : (test_size - i);
        int result = file_process_data(&receiver, buffer, bytes_to_send);
        
        ASSERT(result > 0, "Data processed");
    }
    
    ASSERT(file_is_complete(&receiver), "Large file complete");
    ASSERT(receiver.total_received == test_size, "All bytes received");
    
    TEST_PASS();
}

// Test 9: Error - process with null data
void test_null_data(void) {
    TEST("Null data handling");
    
    FileReceiver receiver;
    file_init(&receiver, 100);
    
    int result = file_process_data(&receiver, NULL, 10);
    ASSERT(result == STATUS_ERROR, "Returns error for null data");
    
    TEST_PASS();
}

// Test 10: Byte-by-byte comparison with original data
void test_byte_comparison(void) {
    TEST("Byte-by-byte comparison of chunks vs original");
    
    // Create test data with recognizable pattern
    uint32_t test_size = 50000;  // 50KB to span multiple chunks
    uint8_t* original_data = (uint8_t*)malloc(test_size);
    
    // Fill with pattern: each byte = (index % 256)
    for (uint32_t i = 0; i < test_size; i++) {
        original_data[i] = (uint8_t)(i % 256);
    }
    
    // Process through byte_converter
    FileReceiver receiver;
    file_init(&receiver, test_size);
    
    uint32_t offset = 0;
    while (offset < test_size) {
        int result = file_process_data(&receiver, original_data + offset, test_size - offset);
        ASSERT(result > 0, "Data processed successfully");
        offset += result;
    }
    
    ASSERT(file_is_complete(&receiver), "File reception complete");
    
    // Reconstruct data from chunks
    uint8_t* reconstructed = (uint8_t*)malloc(test_size);
    uint32_t reconstructed_offset = 0;
    
    for (uint8_t chunk_idx = 0; chunk_idx < NUM_CHUNKS; chunk_idx++) {
        uint32_t chunk_size;
        const uint8_t* chunk_data = file_get_chunk(&receiver, chunk_idx, &chunk_size);
        
        if (chunk_data && chunk_size > 0) {
            memcpy(reconstructed + reconstructed_offset, chunk_data, chunk_size);
            reconstructed_offset += chunk_size;
            printf("  Chunk %d: %u bytes copied\n", chunk_idx, chunk_size);
        }
    }
    
    ASSERT(reconstructed_offset == test_size, "Reconstructed size matches original");
    
    // Byte-by-byte comparison
    int mismatches = 0;
    for (uint32_t i = 0; i < test_size; i++) {
        if (original_data[i] != reconstructed[i]) {
            if (mismatches == 0) {
                printf("  First mismatch at byte %u: original=0x%02X, reconstructed=0x%02X\n",
                       i, original_data[i], reconstructed[i]);
            }
            mismatches++;
        }
    }
    
    ASSERT(mismatches == 0, "All bytes match exactly");
    printf("  Verified %u bytes match perfectly\n", test_size);
    
    free(original_data);
    free(reconstructed);
    
    TEST_PASS();
}

// Test 11: Print chunk bytes for debugging
void test_print_chunks(void) {
    TEST("Print chunk contents for visual inspection");
    
    // Small test data (256 bytes) for easy visualization
    uint32_t test_size = 256;
    uint8_t* test_data = (uint8_t*)malloc(test_size);
    
    // Fill with sequential values 0-255
    for (uint32_t i = 0; i < test_size; i++) {
        test_data[i] = (uint8_t)i;
    }
    
    // Process through byte_converter
    FileReceiver receiver;
    file_init(&receiver, test_size);
    file_process_data(&receiver, test_data, test_size);
    
    printf("\n  Original data (first 32 bytes):\n  ");
    for (int i = 0; i < 32; i++) {
        printf("%02X ", test_data[i]);
        if ((i + 1) % 16 == 0) printf("\n  ");
    }
    
    printf("\n  Chunk 0 (first 32 bytes):\n  ");
    uint32_t chunk_size;
    const uint8_t* chunk_data = file_get_chunk(&receiver, 0, &chunk_size);
    ASSERT(chunk_data != NULL, "Chunk 0 exists");
    
    for (int i = 0; i < 32 && i < (int)chunk_size; i++) {
        printf("%02X ", chunk_data[i]);
        if ((i + 1) % 16 == 0) printf("\n  ");
    }
    printf("\n");
    
    // Verify they match
    int match = (memcmp(test_data, chunk_data, test_size) == 0);
    ASSERT(match, "Original and chunk bytes are identical");
    
    free(test_data);
    
    TEST_PASS();
}

// ============================================================================
// Test Runner
// ============================================================================

void run_all_tests(void) {
    printf("\n");
    printf("========================================\n");
    printf("  BYTE CONVERTER UNIT TESTS\n");
    printf("========================================\n");
    
    // Run all tests
    test_init();
    test_null_pointer();
    test_zero_size();
    test_small_data();
    test_multi_chunk();
    test_progress();
    test_chunk_reset();
    test_large_file();
    test_null_data();
    test_byte_comparison();
    test_print_chunks();
    
    // Print summary
    printf("\n");
    printf("========================================\n");
    printf("  TEST SUMMARY\n");
    printf("========================================\n");
    printf("Total:   %d\n", tests_run);
    printf("Passed:  %d\n", tests_passed);
    printf("Failed:  %d\n", tests_failed);
    printf("========================================\n");
    
    if (tests_failed == 0) {
        printf("✓ ALL TESTS PASSED!\n");
    } else {
        printf("✗ %d TEST(S) FAILED\n", tests_failed);
    }
    printf("\n");
}

int main(void) {
    run_all_tests();
    return (tests_failed == 0) ? 0 : 1;
}
