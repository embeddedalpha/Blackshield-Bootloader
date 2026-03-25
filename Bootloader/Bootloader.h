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

#define CHUNK_SIZE                          ((uint32_t)256U)
#define APP_START_ADDRESS                   0x08010000U
#define APP_VECTOR_ADDR                     (APP_START_ADDRESS + 0x0U)
#define APP_RESET_HANDLER                   (APP_START_ADDRESS + 0x4U)
#define APP_END_BOUNDARY_ADDRESS			0x0801FFFFU
#define APP_SIZE_ADDRESS                    0x08020000U
#define APP_CRC_ADDRESS                     0x08020004U


typedef struct __attribute__((packed))
{
    uint8_t bootloader_version;
    uint8_t firmware_version;
    uint8_t product_id;
    uint8_t product_version;
    uint8_t app_version;
    uint8_t firmware_present_flag;
    uint8_t firmware_valid_flag;
    uint32_t app_crc;
    uint32_t app_size;
    uint32_t magic_number;
} bl_metadata_t;

#define BL_METADATA_ADDR   ((uint32_t)0x08020000U)





void Bootloader_Init(void);
void Bootloader_Jump(void);

bool Bootloader_Write_Meta_Data(const bl_metadata_t *data);
static inline void Bootloader_Read_Meta_Data(bl_metadata_t *data)
{
    memcpy(data, (const void *)BL_METADATA_ADDR, sizeof(bl_metadata_t));
}


#endif /* BOOTLOADER_H_ */
