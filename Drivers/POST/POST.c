/*
 * POST.c
 *
 *  Created on: Jun 23, 2025
 *      Author: kunal
 */


#include "POST.h"

#define LED_PIN 1  // e.g. PA1 on Nucleo

#define BOOT_START_ADDR   ((uint32_t)0x08000000)
#define BOOT_SIZE_WORDS   ((uint32_t)(0x0000FFFFU / 4))  // 64 KB bootloader
#define CRC_GOLDEN_ADDR   (BOOT_START_ADDR + 0x0000FFFB)

#define SRAM_START ((uint32_t)0x20000000)
#define SRAM_SIZE  ((uint32_t)0x00020000)  // 128 KB
#define SRAM_END   ((uint32_t)0x2001FFC0)

volatile uint8_t systick_flag = 0;

void SysTick_Handler(void) {
	systick_flag = 1;
	SysTick->CTRL = 0;  // disable SysTick
}

POST_Result POST_ClockCheck(void)
{
	uint32_t timeout;

	RCC -> CR |= RCC_CR_HSEON;
	timeout = TIMEOUT_COUNT;
	while (!(RCC->CR & RCC_CR_HSERDY)) {
		if (--timeout == 0) {
			return POST_FAIL;
		}
	}

	RCC->PLLCFGR = (8U       << RCC_PLLCFGR_PLLM_Pos)   |
			(336U     << RCC_PLLCFGR_PLLN_Pos)   |
			(0U       << RCC_PLLCFGR_PLLP_Pos)   | // PLLP = 2
			(RCC_PLLCFGR_PLLSRC_HSE)             |
			(7U       << RCC_PLLCFGR_PLLQ_Pos);

	RCC->CR |= RCC_CR_PLLON;
	// 5. Wait for PLL ready
	timeout = TIMEOUT_COUNT;
	while (!(RCC->CR & RCC_CR_PLLRDY)) {
		if (--timeout == 0){
			return POST_FAIL;
		}
	}

	RCC->CFGR &= ~RCC_CFGR_SW;          // clear SW
	RCC->CFGR |= RCC_CFGR_SW_PLL;       // select PLL
	// 7. Wait for switch
	timeout = TIMEOUT_COUNT;
	while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) {
		if (--timeout == 0){
			return POST_FAIL;
		}
	}

	return POST_OK;

}


POST_Result POST_CPUCoreTest(void)
{
	uint32_t a = 0x12345678U;
	uint32_t b = 0x87654321U;
	uint32_t sum, xor;

	// Simple ALU test: addition
	sum = a + b;
	if (sum != 0x99999999U) return POST_FAIL;

	// Simple ALU test: XOR
	xor = a ^ b;
	if (xor != 0x95511559U) return POST_FAIL;

	// Simple shift/rotate test
	uint32_t ror = (a >> 4) | (a << 28);
	if (ror != 0x81234567U) return POST_FAIL;

	return POST_OK;
}


POST_Result POST_SRAM_Test(void)
{
	volatile uint32_t *addr;
	uint32_t pattern;

	// Phase 1: write 0xAAAAAAAA
	pattern = 0xAAAAAAAAU;
	for (addr = (uint32_t*)SRAM_START; addr < (uint32_t*)SRAM_END; ++addr) {
		*addr = pattern;
	}
	// Phase 2: check and write 0x55555555
	for (addr = (uint32_t*)SRAM_START; addr < (uint32_t*)SRAM_END; ++addr) {
		if (*addr != pattern) return POST_FAIL; //
		*addr = 0x55555555U;
	}
	// Phase 3: check 0x55555555
	for (addr = (uint32_t*)SRAM_START; addr < (uint32_t*)SRAM_END; ++addr) {
		if (*addr != 0x55555555U) return POST_FAIL;
	}
	return POST_OK;
}


POST_Result POST_FlashCRC(void)
{
	uint32_t i;
	uint32_t golden = *(__IO uint32_t*)CRC_GOLDEN_ADDR;
	uint32_t crc_val;

	// 1. Enable CRC clock
	RCC->AHB1ENR |= RCC_AHB1ENR_CRCEN;
	CRC->CR = 0;          // reset CRC peripheral

	// 2. Feed words
	for (i = 0; i < BOOT_SIZE_WORDS; ++i) {
		crc_val = CRC->DR = *(__IO uint32_t*)(BOOT_START_ADDR + i*4);
	}
	// 3. Compare
	if (crc_val != golden) return POST_FAIL;

	return POST_OK;
}


POST_Result POST_InterruptTest(void)
{
	uint32_t timeout = TIMEOUT_COUNT;

	// 1. Configure SysTick for a short interval (~1 ms @168 MHz/8)
	SysTick->LOAD = (168000000U/8/1000U) - 1U;
	SysTick->VAL = 0;
	SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk | // processor clock / 8
			SysTick_CTRL_TICKINT_Msk   | // enable interrupt
			SysTick_CTRL_ENABLE_Msk;     // start

	// 2. Wait for flag
	while (!systick_flag) {
		if (--timeout == 0) return POST_FAIL;
	}
	return POST_OK;
}


POST_Result POST_WatchdogTest(void)
{
	// 1. Enable write access
	IWDG->KR = 0x5555;
	// 2. Set prescaler to /32
	IWDG->PR = IWDG_PR_PR_0;   // divide by 32
	// 3. Reload max (0x0FFF)
	IWDG->RLR = 0x0FFF;
	// 4. Reload counter
	IWDG->KR = 0xAAAA;
	// 5. Start IWDG
	IWDG->KR = 0xCCCC;

	// Wait a short while (< timeout) then refresh once
	for (volatile uint32_t i=0; i<100000; ++i);
	IWDG->KR = 0xAAAA;  // prove we can service it

	return POST_OK;
}


void fail_safe(void) {
    // 1. Disable all interrupts
    __disable_irq();
    // 2. Turn off peripheral clocks
    RCC->APB1ENR = 0;
    RCC->APB2ENR = 0;
    // 3. Configure LED_PIN as output
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    GPIOA->MODER  = (GPIOA->MODER & ~(3U<<(LED_PIN*2))) | (1U<<(LED_PIN*2));
    // 4. Blink LED rapidly forever
    while (1) {
        GPIOA->ODR ^= (1U<<LED_PIN);
        for (volatile uint32_t d=0; d<200000; ++d);
    }
}



