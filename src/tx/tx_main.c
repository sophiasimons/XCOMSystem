#include "byte_converter.h"
#include <stdio.h>   // for printf
#include <string.h>  // for memset
//#include "stm32f4xx_hal.h"  // Adjust according to your STM32 series
//#include "usart.h"  // or however you output debug info




int main(void) {
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART2_UART_Init();  // For debug output
    
    // Run tests from test_byte_converter.c:
    run_all_tests();
    
    while (1) {
        // Your main loop
    }
}
