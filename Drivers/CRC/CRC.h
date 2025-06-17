/*
 * CRC.h
 *
 *  Created on: May 28, 2025
 *      Author: kunal
 */

#ifndef CRC_CRC_H_
#define CRC_CRC_H_

#include "main.h"
#include "DMA/DMA.h"

#define CRC_Polynomial 0x4C11DB7


void CRC_Init(void);
void CRC_Reset(void);
uint32_t CRC_Compute_Single_Word(uint32_t word);
uint32_t CRC_Compute_8Bit_Block(volatile uint8_t *wordBlock, size_t length);
uint32_t CRC_Compute_32Bit_Block(volatile uint32_t *wordBlock, size_t length);
uint32_t CRC_Compute_Flash_Data(volatile uint32_t Flash_Address, size_t length);
#endif /* CRC_CRC_H_ */
