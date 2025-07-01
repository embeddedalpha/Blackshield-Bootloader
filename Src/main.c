/* =========================== BOOTLOADER: REFACTORED FOR COMMAND PATTERN =========================== */


#define DEBUG_PRINTF 0



#define APP_DATA_LEN_ADDRESS				0x0801FFF0U
#define APP_DATA_CRC_ADDRESS				0x0801FFF4U


#define APP_MAX_SIZE           65535U
#define APP_CRC_VALUE      0xD41F4487
#define APP_CRC_ADDRESS    0x08018000

#define Bootmode_Toggle_Count 6


#include "main.h"
#include "Bootloader.h"
#include "CRC/CRC.h"
#include "Custom_RS485_Comm/Custom_RS485_Comm.h"
#if DEBUG_PRINTF
#include "Console/Console.h"
#endif
#include "POST/POST.h"
#include "Flash/Flash.h"

#define LOCATE_APP_FUNC    __attribute__((section(".app_section")))

#define HEADER_1           0xAA
#define HEADER_2           0x55
#define FOOTER_1           0xBB
#define FOOTER_2           0x66
#define PACKET_LENGTH_MIN  10U
#define PACKET_LENGTH_MAX  (256 + PACKET_LENGTH_MIN)

volatile uint32_t flash_write_address_counter = APP_START_ADDRESS;
volatile uint32_t flash_read_address_counter = APP_START_ADDRESS;

typedef void (*pFunction)(void);
pFunction JumpToApplication;
uint32_t JumpAddress;



typedef enum {
	Connect_Device      = 0xA0,
	Disconnect_Device   = 0xA1,
	Fetch_Info          = 0xA2,
	Write_Firmware      = 0xA3,
	Read_Firmware       = 0xA4,
	Erase_Firmware      = 0xA5,
	Reboot_MCU          = 0xA6,
	Write_Complete      = 0xA7,
} Commands_t;

Commands_t command_rec ;

typedef void (*CommandHandler_t)(void);

typedef struct {
	uint8_t opcode;
	CommandHandler_t handler;
} CommandEntry_t;

/* =========================== Command Handlers =========================== */
void Connect_Device_Func(void);
void Disconnect_Device_Func(void);
void Write_Firmware_Func(void);
void Read_Firmware_Func(void);
void Erase_Firmware_Func(void);
void Reboot_MCU_Func(void);
void Fetch_Info_Func(void);
void Write_Complete_Func(void);

const CommandEntry_t command_table[] = {
		{Connect_Device,      Connect_Device_Func},
		{Disconnect_Device,   Disconnect_Device_Func},
		{Fetch_Info, Fetch_Info_Func},
		{Write_Firmware,      Write_Firmware_Func},
		{Read_Firmware,       Read_Firmware_Func},
		{Erase_Firmware,      Erase_Firmware_Func},
		{Reboot_MCU,          Reboot_MCU_Func},
		{Write_Complete,      Write_Complete_Func},
};

/* =========================== Global Buffers =========================== */
uint8_t  buffer1[3] = {0,0,0};
volatile uint8_t buffer[PACKET_LENGTH_MAX];
uint16_t len = 0;
uint32_t CRC_Rec1 = 0, CRC_Rec2 = 0;

/* =========================== Packet Validation =========================== */
bool Validate_And_Execute_Command(uint8_t *buf, uint16_t len)
{
	if (len < PACKET_LENGTH_MIN || len > PACKET_LENGTH_MAX) return false;

	if (buf[0] != HEADER_1 || buf[1] != HEADER_2 ||
			buf[len-2] != FOOTER_1 || buf[len-1] != FOOTER_2)
		return false;

	uint32_t received_crc = ((uint32_t)buf[len-6] << 24) | ((uint32_t)buf[len-5] << 16) |
			((uint32_t)buf[len-4] << 8)  | ((uint32_t)buf[len-3]);

	uint32_t computed_crc = CRC_Compute_8Bit_Block(&buf[2], len - 8);

	if (received_crc != computed_crc) return false;

	uint8_t opcode = buf[2];
	command_rec = buf[2];
	for (int i = 0; i < sizeof(command_table)/sizeof(command_table[0]); i++) {
		if (command_table[i].opcode == opcode) {
			command_table[i].handler();
			return true;
		}
	}

	return false;
}


/* =========================== Bootloader Functions =========================== */
typedef enum {
	STATE_WAIT_CONNECT,
	STATE_CONNECTED,
} SystemState;
SystemState state = STATE_WAIT_CONNECT;

typedef enum _Request_List_{
	Req_Request     = 0x01,
	Req_ACK  	= 0x02,
}Request_List;

void Bootloader(void)
{
	DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, PACKET_LENGTH_MAX);

	Custom_Comm_Init(256000);


	while (1) {
		switch (state) {
		case STATE_WAIT_CONNECT:
			DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, PACKET_LENGTH_MAX);
			len = 0;
			len = Custom_Comm_Receive((uint8_t *)buffer);
			if (Validate_And_Execute_Command((uint8_t *)buffer, len))
				state = STATE_CONNECTED;
			break;

		case STATE_CONNECTED:
			DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, PACKET_LENGTH_MAX);
			len = 0;
			len = Custom_Comm_Receive((uint8_t *)buffer);
			Validate_And_Execute_Command((uint8_t *)buffer, len);
			break;
		}
	}
}

bool Check_Firmware_Presence(void);

POST_Result result;


/* =========================== Application CRC Boot Decision =========================== */
int main(void)
{


	MCU_Clock_Setup();
	Delay_Config();
	CRC_Init();


	GPIO_Pin_Init(GPIOD, 12, GPIO_Configuration.Mode.General_Purpose_Output,
			GPIO_Configuration.Output_Type.Push_Pull,
			GPIO_Configuration.Speed.Very_High_Speed,
			GPIO_Configuration.Pull.Pull_Down,
			GPIO_Configuration.Alternate_Functions.None);

	GPIO_Pin_Init(GPIOD, 13, GPIO_Configuration.Mode.General_Purpose_Output,
			GPIO_Configuration.Output_Type.Push_Pull,
			GPIO_Configuration.Speed.Very_High_Speed,
			GPIO_Configuration.Pull.Pull_Down,
			GPIO_Configuration.Alternate_Functions.None);
	GPIO_Pin_Init(GPIOD, 14, GPIO_Configuration.Mode.General_Purpose_Output,
			GPIO_Configuration.Output_Type.Push_Pull,
			GPIO_Configuration.Speed.Very_High_Speed,
			GPIO_Configuration.Pull.Pull_Down,
			GPIO_Configuration.Alternate_Functions.None);
	GPIO_Pin_Init(GPIOD, 15, GPIO_Configuration.Mode.General_Purpose_Output,
			GPIO_Configuration.Output_Type.Push_Pull,
			GPIO_Configuration.Speed.Very_High_Speed,
			GPIO_Configuration.Pull.Pull_Down,
			GPIO_Configuration.Alternate_Functions.None);

	for(int i = 0; i < Bootmode_Toggle_Count; i++)
	{
		GPIO_Pin_Toggle(GPIOD, 12);
		GPIO_Pin_Toggle(GPIOD, 13);
		GPIO_Pin_Toggle(GPIOD, 14);
		GPIO_Pin_Toggle(GPIOD, 15);
		Delay_s(1);
	}


	GPIO_Pin_Init(GPIOC, 0, GPIO_Configuration.Mode.Input, GPIO_Configuration.Output_Type.None,
			GPIO_Configuration.Speed.None, GPIO_Configuration.Pull.None, GPIO_Configuration.Alternate_Functions.None);

	volatile uint16_t jumper_read = GPIOC->IDR & GPIO_IDR_ID0;

	volatile bool firmware_check = false;

	firmware_check = Check_Firmware_Presence();

	uint32_t APP_SIZE_Temp = __REV(Flash_Read_Single_Word(0x08020000));

	uint32_t APP_CRC_Temp = __REV(Flash_Read_Single_Word(0x08020004));


	if ((jumper_read == 0) || (firmware_check == false)) {
		Bootloader();
	} else {

		CRC_Reset();
		uint32_t Calculated_CRC = CRC_Compute_8Bit_Block(APP_START_ADDRESS, APP_SIZE_Temp);

		if (Calculated_CRC == APP_CRC_Temp) {
			// Jump to App

#if DEBUG_PRINTF
			Console_Init(115200);
			printConsole("Jumping from Bootloader to Application 1 \r\n");
			Delay_milli(20);
#endif

#if DEBUG_PRINTF
			printConsole("Application CRC = 0x%x \r\n",CRC_Rec1);
			Delay_milli(20);
#endif


			Bootloader_Jump();




		}
		else{
			while(1)
			{
				GPIO_Pin_Toggle(GPIOD, 14);
				Delay_s(1);
			}

		}
	}

	while (1);
}

void Connect_Device_Func(void)
{

	GPIO_Pin_High(GPIOD, 12);
	GPIO_Pin_Low(GPIOD, 13);
	DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, len);

	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Connect_Device;
	buffer[3] = Req_ACK;
	buffer[4] = 5;
	buffer[5] = 0x01;
	buffer[6] = 0x19;
	buffer[7] = 0x01;
	buffer[8] = 0x01;
	buffer[9] = 0x01;
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 8);
	buffer[10]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[11]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[12]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[13] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[14] = 0xBB;
	buffer[15] = 0x66;
	Custom_Comm_Send(buffer, 16);
	DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, 16);

}

void Fetch_Info_Func(void)
{
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Fetch_Info;
	buffer[3] = Req_ACK;
	buffer[4] = 5;
	buffer[5] = 0x01;
	buffer[6] = 0x19;
	buffer[7] = 0x01;
	buffer[8] = 0x01;
	buffer[9] = 0x01;
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 8);
	buffer[10]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[11]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[12]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[13] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[14] = 0xBB;
	buffer[15] = 0x66;
	Custom_Comm_Send(buffer, 16);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 16);

}

void Disconnect_Device_Func(void)
{

	GPIO_Pin_High(GPIOD, 13);
	GPIO_Pin_Low(GPIOD, 12);
	DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, len);

	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Disconnect_Device;
	buffer[3] = Req_ACK;
	buffer[4] = 0;
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[5]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[6]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[7]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[8] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[9] = 0xBB;
	buffer[10] = 0x66;
	Custom_Comm_Send(buffer, 11);
	DMA_Memory_To_Memory_Transfer(buffer1, 8, 0, (uint8_t *)buffer, 8, 1, 11);

	state = STATE_WAIT_CONNECT;

}


void Write_Firmware_Func(void)
{

	Flash_Unlock();
	//	Flash_Write_Enable();
	FLASH->CR &= ~FLASH_CR_PSIZE;
	FLASH->CR |= (0 << FLASH_CR_PSIZE_Pos);
	FLASH->CR |= FLASH_CR_PG;
	DMA_Memory_To_Memory_Transfer(&buffer[5], 8, 1, flash_write_address_counter, 8, 1, buffer[4]);
	Flash_Write_Disable();
	Flash_Lock();
	flash_write_address_counter += (buffer[4]);

	// Write Flash Memory
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, PACKET_LENGTH_MAX);
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Write_Firmware;
	buffer[3] = Req_ACK;
	buffer[4] = Req_ACK;
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 7);
	buffer[5]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[6]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[7]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[8] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[9] = 0xBB;
	buffer[10] = 0x66;
	Custom_Comm_Send(buffer, 11);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 11);

}

void Read_Firmware_Func(void)
{
	//flash_read_address_counter
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Read_Firmware;
	buffer[3] = Req_ACK;
	buffer[4] = 255;

	DMA_Memory_To_Memory_Transfer(&buffer[5], 8, 1, flash_write_address_counter, 8, 1, buffer[4]);

	//Read Flash Memory
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2],3);
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
	Flash_Unlock();
	Flash_Write_Enable();
	Flash_Erase_Sector(Sector_4_0x08010000);
	Flash_Erase_Sector(Sector_5);
	Flash_Write_Disable();
	Flash_Lock();
	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Erase_Firmware;
	buffer[3] = Req_ACK;
	buffer[4] = 0x00;
	//Read Flash Memory
	CRC_Rec1   = CRC_Compute_8Bit_Block(&buffer[2], 3);
	buffer[5]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[6] = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[7] = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[8] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[9] = 0xBB;
	buffer[10] = 0x66;
	Custom_Comm_Send(buffer, 11);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 11);
}

void Reboot_MCU_Func(void)
{

	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Reboot_MCU;
	buffer[3] = Req_ACK;
	buffer[4] = 0x00;
	//Read Flash Memory
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 3);
	buffer[5]  =  (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[6]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[7]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[8] =  (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[9] = 0xBB;
	buffer[10] = 0x66;
	Custom_Comm_Send(buffer, 11);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 11);

	NVIC_SystemReset();
}

bool Check_Firmware_Presence(void)
{
	uint32_t APP_SIZE_BYTES = __REV(Flash_Read_Single_Word(0x08020000));
	return ((APP_SIZE_BYTES != 0xFFFFFFFFU) && (APP_SIZE_BYTES <= APP_MAX_SIZE));
}

void Write_Complete_Func(void)
{
	//	Flash_Erase_Sector(5);

	Flash_Unlock();
	FLASH->CR &= ~FLASH_CR_PSIZE;
	FLASH->CR |= (0 << FLASH_CR_PSIZE_Pos);
	FLASH->CR |= FLASH_CR_PG;
	DMA_Memory_To_Memory_Transfer(&buffer[5], 8, 1, 0x08020000, 8, 1, buffer[4]);
	Flash_Write_Disable();
	Flash_Lock();

	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, len);


	buffer[0] = 0xAA;
	buffer[1] = 0x55;
	buffer[2] = Write_Complete;
	buffer[3] = Req_ACK;
	buffer[4] = Req_ACK;
	//Read Flash Memory
	CRC_Rec1 = CRC_Compute_8Bit_Block(&buffer[2], 3);
	buffer[5]  = (CRC_Rec1 & 0xFF000000) >> 24;
	buffer[6]  = (CRC_Rec1 & 0x00FF0000) >> 16;
	buffer[7]  = (CRC_Rec1 & 0x0000FF00) >> 8;
	buffer[8] = (CRC_Rec1 & 0x000000FF) >> 0;
	buffer[9] = 0xBB;
	buffer[10] = 0x66;
	Custom_Comm_Send(buffer, 11);
	DMA_Memory_To_Memory_Transfer(buffer1, 8,0, (uint8_t *)buffer, 8, 1, 11);
}
