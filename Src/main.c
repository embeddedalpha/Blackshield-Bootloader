#include "main.h"
#include "CRC/CRC.h"
#include "Custom_RS485_Comm/Custom_RS485_Comm.h"

#define APP_ADDRESS      0x08008000U
typedef void (*pFunction)(void);
pFunction JumpToApplication;
uint32_t JumpAddress;

#define APP_SIZE_BYTES      (64 * 1024)   // 64KB
#define APP_CRC_ADDRESS     0x08018000

#define LOCATE_APP_FUNC  __attribute__((section(".app_section")))


void LOCATE_APP_FUNC Blink_App(void)
{
//	MCU_Clock_Setup();
//	Delay_Config();
	GPIO_Pin_Init(GPIOD, 12, GPIO_Configuration.Mode.General_Purpose_Output, GPIO_Configuration.Output_Type.Push_Pull, GPIO_Configuration.Speed.High_Speed, GPIO_Configuration.Pull.None, GPIO_Configuration.Alternate_Functions.None);

	while(1)
	{
		GPIO_Pin_High(GPIOD, 12);
		Delay_s(1);
		GPIO_Pin_Low(GPIOD, 12);
		Delay_s(1);
	}

}


volatile uint8_t  buffer1[3] = {0,0,0};
volatile uint8_t  buffer[256];
uint16_t len = 0;



typedef enum _Commands_Typedef_{
	Connect_Device =             0xA1,
	Disconnect_Device =          0xA2,
	Write_Firmware =             0xA3,
	Read_Firmware =              0xA4,
	Erase_Firmware =             0xA5,
	Reboot_MCU =                 0xA6
}Commands;

typedef enum _Request_List_{
	Req_Request     = 0x01,
	Req_ACK  		= 0x02,
}Request_List;

Commands Command_RX;
Request_List Req_RX;

uint32_t CRC_Rec1 = 0, CRC_Rec2 = 0;

void Bootloader(void);
void Application();
void Connect_Device_Func(void);
void Disconnect_Device_Func(void);
void Write_Firmware_Func(void);
void Read_Firmware_Func(void);
void Reboot_MCU_Func(void);
void Erase_Firmware_Func(void);
bool Validate_Command(uint16_t len, Commands command);
/*==============================================================================================*/

int main(void)
{
	MCU_Clock_Setup();
	Delay_Config();
	CRC_Init();

	GPIO_Pin_Init(GPIOC, 0, GPIO_Configuration.Mode.Input, GPIO_Configuration.Output_Type.None, GPIO_Configuration.Speed.None, GPIO_Configuration.Pull.None, GPIO_Configuration.Alternate_Functions.None);

	if((GPIOC -> IDR & GPIO_IDR_ID0) == true)
	{
//		Custom_Comm_Init(115200);
//		Bootloader();
	}
	else
	{
//		Application();

		//Validate Firmware:
		uint32_t calculated_crc = CRC_Compute_Flash_Data(APP_ADDRESS, APP_SIZE_BYTES);
		uint32_t stored_crc     = *((uint32_t*)APP_CRC_ADDRESS);

		if (calculated_crc == stored_crc) {
			Blink_App();
		}
	}

//	while(1)
//	{
//		Blink_App();
//	}



//	GPIO_Pin_Init(GPIOC, 0, GPIO_Configuration.Mode.Input, GPIO_Configuration.Output_Type.None, GPIO_Configuration.Speed.None, GPIO_Configuration.Pull.None, GPIO_Configuration.Alternate_Functions.None);
//
//	if((GPIOC -> IDR & GPIO_IDR_ID0) == true)
//	{
//		Custom_Comm_Init(115200);
//		Bootloader();
//	}
//	else
//	{
//		Application();
//	}
//
//	while(1)
//	{
//
//	}

}

/*==============================================================================================*/







void Bootloader(void)
{
	while(1)
	{
		len = Custom_Comm_Receive(buffer);
		if(Validate_Command(len, Connect_Device))
		{
			Connect_Device_Func();

			while(1)
			{
				len = Custom_Comm_Receive(buffer);
				if(Validate_Command(len, Write_Firmware))
				{
					Write_Firmware_Func();
				}
				else if(Validate_Command(len, Read_Firmware))
				{

				}
				else if(Validate_Command(len, Erase_Firmware))
				{

				}
				else if(Validate_Command(len, Reboot_MCU))
				{

				}
				else if(Validate_Command(len, Disconnect_Device))
				{
					break;
				}
			}
		}

		if(buffer[0] == 0xAA && buffer[1] == 0x55)
		{
			if(buffer[0] == 0xAA && buffer[1] == 0x55)
			{
				if(buffer[len-2] == 0xBB && buffer[len-1] == 0x66)
				{
					CRC_Rec2 = (((uint32_t)buffer[len-6] << 24) | ((uint32_t)buffer[len-5] << 16) | ((uint32_t)buffer[len-4] << 8) | ((uint32_t)buffer[len-3] << 0)) ;
					CRC_Rec2 = CRC_Compute_8Bit_Block(&buffer[2], len-8);
					if(CRC_Rec1 == CRC_Rec2)
					{
						Command_RX = buffer[2];
						Req_RX = buffer[3];
						switch (Command_RX)
						{
						case Connect_Device:
						{
							Connect_Device_Func();
						}
						break;

						case Disconnect_Device:
						{
							Disconnect_Device_Func();
						}
						break;

						case Write_Firmware:
						{
							Write_Firmware_Func();
						}
						break;

						case Read_Firmware:
						{
							Read_Firmware_Func();
						}
						break;

						case Erase_Firmware:
						{
							Erase_Firmware_Func();
						}
						break;

						case Reboot_MCU:
						{
							Reboot_MCU_Func();
						}
						break;
						}
					}
				}
			}
		}
	}
}

void Connect_Device_Func(void)
{
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Connect_Device;
	buffer[3] = Req_ACK;
	buffer[4] = 0x01;
	buffer[5] = 0x19;
	buffer[6] = 0x01;
	buffer[7] = 0x01;
	buffer[8] = 0x01;
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[9]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[10]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[11]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[12] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[13] = 0xBB;
	buffer[14] = 0x66;
	Custom_Comm_Send(buffer, 14);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 256);

//	DMA_Memory_To_Memory_Transfer(buffer1, 8,8, (uint8_t *)buffer, 0, 1, 256);
}

void Disconnect_Device_Func(void)
{
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Disconnect_Device;
	buffer[3] = Req_ACK;
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[4]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[5]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[6]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[7] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[8] = 0xBB;
	buffer[9] = 0x66;
	Custom_Comm_Send(buffer, 10);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 256);


}


void Write_Firmware_Func(void)
{
	// Write Flash Memory

	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Write_Firmware;
	buffer[3] = Req_ACK;

	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[9]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[10]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[11]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[12] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[13] = 0xBB;
	buffer[14] = 0x66;
	Custom_Comm_Send(buffer, 14);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 256);
}

void Read_Firmware_Func(void)
{
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Read_Firmware;
	buffer[3] = Req_ACK;
	//Read Flash Memory
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[9]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[10]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[11]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[12] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[13] = 0xBB;
	buffer[14] = 0x66;
	Custom_Comm_Send(buffer, 14);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 256);
}

void Erase_Firmware_Func(void)
{
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Erase_Firmware;
	buffer[3] = Req_ACK;
	//Read Flash Memory
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[9]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[10]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[11]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[12] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[13] = 0xBB;
	buffer[14] = 0x66;
	Custom_Comm_Send(buffer, 14);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 256);
}

void Reboot_MCU_Func(void)
{

	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Reboot_MCU;
	buffer[3] = Req_ACK;
	//Read Flash Memory
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[9]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[10]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[11]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[12] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[13] = 0xBB;
	buffer[14] = 0x66;
	Custom_Comm_Send(buffer, 14);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 256);

	NVIC_SystemReset();
}

void Application()
{
	// Perform CRC on Flash


	System_DeInit();
	MCU_Clock_DeInit();
	Systick_DeInit();

	__set_PRIMASK(1);
	__disable_irq();
	__DSB();
	__ISB();

	SCB->VTOR = APP_ADDRESS;
	__set_MSP(*((__IO uint32_t*) APP_ADDRESS));

	// 5. Set PC to application reset handler
	JumpAddress = *(__IO uint32_t*) (APP_ADDRESS + 4);
	JumpToApplication = (pFunction) JumpAddress;

	// 6. Jump!
	JumpToApplication();


	while(1);
}


bool Validate_Command(uint16_t len, Commands command)
{
	bool retval = 0;
	if((buffer[0] == 0xAA) && (buffer[1] == 0x55) && (buffer[len-2] == 0xBB) && (buffer[len-1] == 0x66) && (buffer[2] == command))
	{
		CRC_Rec2 = (((uint32_t)buffer[len-6] << 24) | ((uint32_t)buffer[len-5] << 16) | ((uint32_t)buffer[len-4] << 8) | ((uint32_t)buffer[len-3] << 0)) ;
		CRC_Rec2 = CRC_Compute_8Bit_Block(&buffer[2], len-8);
		if(CRC_Rec1 == CRC_Rec2)
		{
			retval = 1;
		}
	}

	return retval;
}
