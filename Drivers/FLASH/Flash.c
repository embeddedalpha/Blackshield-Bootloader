/*
 * Flash.c
 *
 *  Created on: Jun 1, 2025
 *      Author: kunal
 */


#include "Flash.h"

#define FLASH_KEY1 0x45670123
#define FLASH_KEY2 0xCDEF89AB


void Flash_Unlock(void)
{
	if (FLASH->CR & FLASH_CR_LOCK) {
		FLASH->KEYR = FLASH_KEY1;
		FLASH->KEYR = FLASH_KEY2;
	}
}

void Flash_Lock(void)
{
    FLASH->CR |= FLASH_CR_LOCK;
}


void Flash_Write_Enable(void)
{
	FLASH->CR |= FLASH_CR_PG;
}
void Flash_Write_Disable(void)
{
	FLASH->CR &= ~FLASH_CR_PG;
}

void Flash_Erase_Sector(Flash_Sectors_Typedef sector_number)
{
    while (FLASH->SR & FLASH_SR_BSY); // Wait if busy

    FLASH->CR &= ~FLASH_CR_SNB;
    FLASH->CR |= (sector_number << FLASH_CR_SNB_Pos);
    FLASH->CR |= FLASH_CR_SER;  // Sector erase
    FLASH->CR |= FLASH_CR_STRT;

    while (FLASH->SR & FLASH_SR_BSY); // Wait for completion

    FLASH->CR &= ~FLASH_CR_SER; // Clear SER
}


//void Flash_Write_Sector(void *source, uint8_t data_length, )
