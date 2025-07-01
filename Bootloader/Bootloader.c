/*
 * Bootloader.c
 *
 *  Created on: Jul 1, 2025
 *      Author: kunal
 */


#include "Bootloader.h"





void Bootloader_Init(void);
void Bootloader_Jump(void)
{
	MCU_Clock_DeInit();
	/* 1. Disable SysTick */
	SysTick->CTRL = 0;
	SysTick->LOAD = 0;
	SysTick->VAL  = 0;
	SCB->SHCSR &= ~SCB_SHCSR_SYSTICKACT_Msk;

	/* 2. Disable all NVIC interrupts */
	for (uint32_t irq = 0; irq < 8; irq++) {
		NVIC->ICER[irq] = 0xFFFFFFFFU;
		NVIC->ICPR[irq] = 0xFFFFFFFFU;
	}
	__DSB(); /* 1. Disable SysTick */
	SysTick->CTRL = 0;
	SysTick->LOAD = 0;
	SysTick->VAL  = 0;

	/* 2. Disable all NVIC interrupts */
	for (uint32_t irq = 0; irq < 8; irq++) {
		NVIC->ICER[irq] = 0xFFFFFFFFU;
		NVIC->ICPR[irq] = 0xFFFFFFFFU;
	}
	__DSB();
	__ISB();

	/* 3. Reset all peripheral clocks via RCC reset registers */
	/* AHB1 peripherals */
	RCC->AHB1RSTR = 0xFFFFFFFFU;  // assert reset
	RCC->AHB1RSTR = 0x00000000U;  // release reset
	/* AHB2 peripherals */
	RCC->AHB2RSTR = 0xFFFFFFFFU;
	RCC->AHB2RSTR = 0x00000000U;
	/* AHB3 peripherals */
	RCC->AHB3RSTR = 0xFFFFFFFFU;
	RCC->AHB3RSTR = 0x00000000U;
	/* APB1 peripherals */
	RCC->APB1RSTR = 0xFFFFFFFFU;
	RCC->APB1RSTR = 0x00000000U;
	/* APB2 peripherals */
	RCC->APB2RSTR = 0xFFFFFFFFU;
	RCC->APB2RSTR = 0x00000000U;

	/* 4. Disable all peripheral clocks (to save power / clean state) */
	RCC->AHB1ENR = 0x00000000U;
	RCC->AHB2ENR = 0x00000000U;
	RCC->AHB3ENR = 0x00000000U;
	RCC->APB1ENR = 0x00000000U;
	RCC->APB2ENR = 0x00000000U;

	/* 5. Reset and lock the Flash interface */
	if (FLASH->CR & FLASH_CR_LOCK_Msk) {
		/* already locked */
	} else {
		Flash_Unlock();
		FLASH->CR |= FLASH_CR_SER;     // sector erase reset
		FLASH->CR |= FLASH_CR_PSIZE_1; // program size reset
		FLASH->SR  = FLASH_SR_EOP  | FLASH_SR_WRPERR
				| FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR;
		Flash_Lock();
	}

	/* 7. Remap vector table to application start */
	SCB->VTOR = APP_START_ADDRESS; // your defined app address macro
	__DSB();
	__ISB();

	__disable_irq();

	__set_MSP(*((__IO uint32_t*) APP_START_ADDRESS));
	void (*app_reset_handler)(void) = (void*)(*(volatile uint32_t *)(APP_RESET_HANDLER));
	app_reset_handler();


}
