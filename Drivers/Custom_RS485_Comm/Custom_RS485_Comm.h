/*
 * Custom_RS485_Comm.h
 *
 *  Created on: Jun 4, 2025
 *      Author: kunal
 */

#ifndef CUSTOM_RS485_COMM_CUSTOM_RS485_COMM_H_
#define CUSTOM_RS485_COMM_CUSTOM_RS485_COMM_H_

#include "main.h"
#include "GPIO/GPIO.h"
#include "USART/USART.h"
#include "DMA/DMA.h"

void Custom_Comm_Init(int32_t baudrate);
void Custom_Comm_Send(volatile uint8_t *buffer, size_t buffer_size);
uint16_t Custom_Comm_Receive(volatile uint8_t *buffer);


#endif /* CUSTOM_RS485_COMM_CUSTOM_RS485_COMM_H_ */
