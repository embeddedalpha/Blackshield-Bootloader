/*
 * CRC.c
 *
 *  Created on: May 28, 2025
 *      Author: kunal
 */


#include "CRC.h"

void CRC_Init(void)
{
	RCC->AHB1ENR |= RCC_AHB1ENR_CRCEN;
}

void CRC_Reset(void)
{
	CRC->CR |= CRC_CR_RESET;
}

uint32_t CRC_Compute_Single_Word(uint32_t word)
{
	CRC_Reset();
	CRC->DR = (uint32_t)(word);
	return (CRC->DR);
}

uint32_t CRC_Compute_8Bit_Block(volatile uint8_t *wordBlock, size_t length)
{
	uint8_t temp=0;
	CRC_Reset();
	for(uint32_t i = 0; i < length; i++)
	{
		temp = wordBlock[i];
		CRC -> DR = 0x00000000 | (temp);

	}
	return (CRC -> DR);
}

uint32_t CRC_Compute_32Bit_Block(volatile uint32_t *wordBlock, size_t length)
{
	uint32_t temp = 0;
	CRC_Reset();
	for(uint32_t i = 0; i < length; i++)
	{
		temp = *wordBlock++;
		CRC -> DR = (uint32_t)(temp);
	}
	return (CRC -> DR)&0xFFFFffff;
}


uint32_t CRC_Compute_Flash_Data(volatile uint32_t Flash_Address, size_t length)
{
//	RCC->AHB1ENR |= RCC_AHB1ENR_DMA2EN;
//
//	DMA2_Stream0->CR = 0;
//	while (DMA2_Stream0->CR & DMA_SxCR_EN);  // Make sure stream is disabled
//
//	DMA2_Stream0->PAR = (uint32_t)&CRC->DR;
//	DMA2_Stream0->M0AR = (uint32_t)Flash_Address;
//	DMA2_Stream0->NDTR = length;
//	DMA2_Stream0->CR |=
//			(0 << DMA_SxCR_CHSEL_Pos) |      // Channel 0
//			(1 << DMA_SxCR_DIR_Pos)    |     // Memory-to-peripheral
//			(0 << DMA_SxCR_PINC_Pos)   |     // Peripheral address not incremented
//			(1 << DMA_SxCR_MINC_Pos)   |     // Memory address incremented
//			(2 << DMA_SxCR_MSIZE_Pos)  |     // Memory size: word (32-bit)
//			(2 << DMA_SxCR_PSIZE_Pos);       // Peripheral size: word
//	DMA2_Stream0->FCR = 0; // Direct mode, no FIFO
//
//	    DMA2_Stream0->CR |= DMA_SxCR_EN;
//
//	    // Wait for transfer complete
//	    while (!(DMA2->LISR & DMA_LISR_TCIF0));
//	    DMA2->LIFCR |= DMA_LIFCR_CTCIF0;

	DMA_Memory_To_Memory_Transfer(Flash_Address, 32, 1, &CRC->DR, 32, 0, length);

	    uint32_t crc_value = CRC->DR;

	    return crc_value;
}
