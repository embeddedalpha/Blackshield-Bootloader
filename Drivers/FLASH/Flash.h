/*
 * Flash.h
 *
 *  Created on: Jun 1, 2025
 *      Author: kunal
 */

#ifndef FLASH_FLASH_H_
#define FLASH_FLASH_H_

#include "main.h"



void Flash_Unlock(void);
void Flash_Lock(void);
void Flash_Erase_Sector(uint8_t sector_number);

#endif /* FLASH_FLASH_H_ */
