/*
 * Flash.h
 *
 *  Created on: Jun 1, 2025
 *      Author: kunal
 */

#ifndef FLASH_FLASH_H_
#define FLASH_FLASH_H_

#include "main.h"

typedef enum {

	Sector_0,  //0x0800 0000 - 0x0800 3FFF 16 Kbytes
	Sector_1,  //0x0800 4000 - 0x0800 7FFF 16 Kbytes
	Sector_2,  //0x0800 8000 - 0x0800 BFFF 16 Kbytes
	Sector_3,  //0x0800 C000 - 0x0800 FFFF 16 Kbytes
	Sector_4,  //0x0801 0000 - 0x0801 FFFF 64 Kbytes
	Sector_5,  //0x0802 0000 - 0x0803 FFFF 128 Kbytes
	Sector_6,  //0x0804 0000 - 0x0805 FFFF 128 Kbytes
	Sector_7,  //0x0806 0000 - 0x0807 FFFF 128 Kbytes
	Sector_8,  //0x0808 0000 - 0x0809 FFFF 128 Kbytes
	Sector_9,  //0x080A 0000 - 0x080B FFFF 128 Kbytes
	Sector_10, //0x080C 0000 - 0x080D FFFF 128 Kbytes
	Sector_11, //0x080E 0000 - 0x080F FFFF 128 Kbytes

}Flash_Sectors_Typedef;

void Flash_Unlock(void);
void Flash_Lock(void);
void Flash_Write_Enable(void);
void Flash_Write_Disable(void);
void Flash_Erase_Sector(Flash_Sectors_Typedef sector_number);

#endif /* FLASH_FLASH_H_ */
