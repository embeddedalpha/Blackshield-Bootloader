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
    CRC->DR = (word);
    return (CRC->DR);
}

uint32_t CRC_Compute_8Bit_Block(uint8_t *wordBlock, size_t length)
{
	CRC_Reset();
	for(uint32_t i = 0; i < length; i++)
	{
		CRC -> DR = (uint32_t)(wordBlock[i]);
	}
	return (CRC -> DR);
}

