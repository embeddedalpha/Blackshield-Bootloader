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

void FLash_Write_Data(volatile void  *desitnation_buffer,uint8_t data_length, uint16_t length, uint32_t Flash_Address)
{
	DMA_Memory_To_Memory_Transfer(desitnation_buffer, data_length, 1, Flash_Address, data_length, 1, length);
}

uint32_t Flash_Read_Single_Word(uint32_t Flash_Address)
{
	return *(__IO uint32_t *)Flash_Address;
}

uint16_t Flash_Read_Single_Half_Word(uint32_t Flash_Address)
{
	return *(__IO uint32_t *)Flash_Address;
}

uint8_t Flash_Read_Single_Byte(uint32_t Flash_Address)
{
	return *(__IO uint32_t *)Flash_Address;
}



//void Flash_Write_Sector(void *source, uint8_t data_length, )
