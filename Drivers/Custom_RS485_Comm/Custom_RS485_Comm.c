
#include "Custom_RS485_Comm.h"

// Flags to control and monitor UART reception
volatile int custom_rx_get_flag = 0; // Indicates if the reception is active
volatile int custom_rx_flag = 0;     // Indicates if data reception is complete

#define Custom_RX_Buffer_Length 300 // Length of the reception buffer

// Variables to track the length of received data and the reception buffer
volatile int Custom_RX_Length = 0;
volatile uint8_t Custom_TRX_Buffer[Custom_RX_Buffer_Length]; // Buffer for received and transmitted data

// USART configuration structure
USART_Config Custom_Comm;

void Custom_Console_IRQ(void){
	if (custom_rx_get_flag == 1) { // Check if reception is active
		(void)UART4->SR; // Read the status register to clear flags
		(void)UART4->DR; // Read the data register to clear flags

		__disable_irq(); // Disable interrupts to safely update DMA configurations

		// Disable DMA stream
		Custom_Comm.USART_DMA_Instance_RX.Request.Stream->CR &= ~DMA_SxCR_EN;

		// Calculate the length of received data
		Custom_RX_Length = Custom_RX_Buffer_Length - Custom_Comm.USART_DMA_Instance_RX.Request.Stream->NDTR;

		// Prevent buffer overflow
		if (Custom_RX_Length > Custom_RX_Buffer_Length) {
			Custom_RX_Length = Custom_RX_Buffer_Length;
		}

		// Reset DMA stream for the next reception
		Custom_Comm.USART_DMA_Instance_RX.Request.Stream->NDTR = Custom_RX_Buffer_Length;
		Custom_Comm.USART_DMA_Instance_RX.Request.Stream->CR |= DMA_SxCR_EN;

		__enable_irq(); // Re-enable interrupts

		custom_rx_flag = 1; // Set the flag indicating data reception is complete
	}
}


void Custom_Comm_Init(int32_t baudrate) {
	// Reset USART configuration to default values
	USART_Config_Reset(&Custom_Comm);

	// Configure USART parameters
	Custom_Comm.Port = UART4; // Use UART4 for console communication
	Custom_Comm.baudrate = baudrate; // Set the baud rate
	Custom_Comm.mode = USART_Configuration.Mode.Asynchronous; // Asynchronous mode
	Custom_Comm.stop_bits = USART_Configuration.Stop_Bits.Bit_1; // 1 stop bit
	Custom_Comm.TX_Pin = UART4_TX_Pin.PC10; // TX pin is PC10
	Custom_Comm.RX_Pin = UART4_RX_Pin.PC11; // RX pin is PC11
	Custom_Comm.interrupt = USART_Configuration.Interrupt_Type.IDLE_Enable; // Enable IDLE interrupt
	Custom_Comm.dma_enable = USART_Configuration.DMA_Enable.TX_Enable | USART_Configuration.DMA_Enable.RX_Enable; // Enable DMA for TX and RX
	Custom_Comm.ISR_Routines.Idle_Line_ISR = Custom_Console_IRQ;
	// Initialize USART
	if (USART_Init(&Custom_Comm) != true) {}
}


void Custom_Comm_Send(volatile uint8_t *buffer, size_t buffer_size) {

	if(buffer_size == 1)
	{
		USART_TX_Single_Byte(&Custom_Comm, buffer[0]);
	}

	// Transmit the buffer using DMA
	USART_TX_Buffer(&Custom_Comm, (uint8_t *)&buffer[0], buffer_size);

}


uint16_t Custom_Comm_Receive(volatile uint8_t *buffer)
{
	int result;

	custom_rx_get_flag = 1; // Enable reception

	// Start DMA reception
	USART_RX_Buffer(&Custom_Comm, (uint8_t *)Custom_TRX_Buffer, Custom_RX_Buffer_Length, 0);

	// Wait until data reception is complete
	while (custom_rx_flag == 0) {
		// Wait loop
	}

	// Check for valid input length
	if (Custom_RX_Length < 2) {
		// Reset flags and return error
		custom_rx_get_flag = 0;
		custom_rx_flag = 0;
		return -1;
	}

	result = Custom_RX_Length;

	DMA_Memory_To_Memory_Transfer(Custom_TRX_Buffer, 8,1,  buffer, 8, 1, Custom_RX_Length);

	custom_rx_get_flag = 0; // Indicates if the reception is active
	custom_rx_flag = 0;


	return result;


}
