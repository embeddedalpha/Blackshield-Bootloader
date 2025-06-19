/* =========================== BOOTLOADER: REFACTORED FOR COMMAND PATTERN =========================== */
#include "main.h"
#include "CRC/CRC.h"
#include "Custom_RS485_Comm/Custom_RS485_Comm.h"

#define APP_ADDRESS        0x08008000U
#define APP_SIZE           (20)  // 64KB
#define APP_CRC_VALUE      0xD41F4487
#define APP_CRC_ADDRESS    0x08018000
#define LOCATE_APP_FUNC    __attribute__((section(".app_section")))

#define HEADER_1           0xAA
#define HEADER_2           0x55
#define FOOTER_1           0xBB
#define FOOTER_2           0x66
#define PACKET_LENGTH_MIN  10U
#define PACKET_LENGTH_MAX  (256 + PACKET_LENGTH_MIN)

typedef void (*pFunction)(void);
pFunction JumpToApplication;
uint32_t JumpAddress;

typedef enum {
    Connect_Device      = 0xA1,
    Disconnect_Device   = 0xA2,
    Write_Firmware      = 0xA3,
    Read_Firmware       = 0xA4,
    Erase_Firmware      = 0xA5,
    Reboot_MCU          = 0xA6
} Commands_t;

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

const CommandEntry_t command_table[] = {
    {Connect_Device,      Connect_Device_Func},
    {Disconnect_Device,   Disconnect_Device_Func},
    {Write_Firmware,      Write_Firmware_Func},
    {Read_Firmware,       Read_Firmware_Func},
    {Erase_Firmware,      Erase_Firmware_Func},
    {Reboot_MCU,          Reboot_MCU_Func},
};

/* =========================== Global Buffers =========================== */
const uint8_t  buffer1[3] = {0,0,0};
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
    for (int i = 0; i < sizeof(command_table)/sizeof(command_table[0]); i++) {
        if (command_table[i].opcode == opcode) {
            command_table[i].handler();
            return true;
        }
    }

    return false;
}

/* =========================== Bootloader FSM =========================== */
typedef enum {
    STATE_WAIT_CONNECT,
    STATE_CONNECTED,
} SystemState;

typedef enum _Request_List_{
	Req_Request     = 0x01,
	Req_ACK  	= 0x02,
}Request_List;

void Bootloader(void)
{
    Custom_Comm_Init(115200);
    SystemState state = STATE_WAIT_CONNECT;

    while (1) {
        len = Custom_Comm_Receive((uint8_t *)buffer);

        switch (state) {
            case STATE_WAIT_CONNECT:
                if (Validate_And_Execute_Command((uint8_t *)buffer, len))
                    state = STATE_CONNECTED;
                break;

            case STATE_CONNECTED:
                Validate_And_Execute_Command((uint8_t *)buffer, len);
                break;
        }
    }
}

/* =========================== Application CRC Boot Decision =========================== */
int main(void)
{
    MCU_Clock_Setup();
    Delay_Config();
    CRC_Init();

    GPIO_Pin_Init(GPIOC, 0, GPIO_Configuration.Mode.Input, GPIO_Configuration.Output_Type.None,
                  GPIO_Configuration.Speed.None, GPIO_Configuration.Pull.None, GPIO_Configuration.Alternate_Functions.None);

    if ((GPIOC->IDR & GPIO_IDR_ID0) != 0) {
        Bootloader();
    } else {
        //uint32_t calculated_crc = CRC_Compute_Flash_Data(APP_ADDRESS, APP_SIZE);
//        if (calculated_crc == APP_CRC_VALUE) {
            // Jump to App
            System_DeInit();
            MCU_Clock_DeInit();
            Systick_DeInit();
            __disable_irq();
            SCB->VTOR = APP_ADDRESS;
            __set_MSP(*((__IO uint32_t*) APP_ADDRESS));
            JumpAddress = *(__IO uint32_t*)(APP_ADDRESS + 4);
            JumpToApplication = (pFunction)JumpAddress;
            JumpToApplication();
//        }
    }

    while (1);
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

