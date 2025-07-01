/*
 * Bootloader.h
 *
 *  Created on: Jul 1, 2025
 *      Author: kunal
 */

#ifndef BOOTLOADER_H_
#define BOOTLOADER_H_

#include "main.h"
#include "Flash/Flash.h"

#define APP_START_ADDRESS   0x08010000U
#define APP_VECTOR_ADDR    (APP_START_ADDRESS + 0x0U)
#define APP_RESET_HANDLER  (APP_START_ADDRESS + 0x4U)
#define APP_END_BOUNDARY_ADDRESS			0x0801FFFFU


void Bootloader_Init(void);
void Bootloader_Jump(void);


#endif /* BOOTLOADER_H_ */
