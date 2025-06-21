################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/Custom_RS485_Comm/Custom_RS485_Comm.c 

OBJS += \
./Drivers/Custom_RS485_Comm/Custom_RS485_Comm.o 

C_DEPS += \
./Drivers/Custom_RS485_Comm/Custom_RS485_Comm.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/Custom_RS485_Comm/%.o Drivers/Custom_RS485_Comm/%.su Drivers/Custom_RS485_Comm/%.cyclo: ../Drivers/Custom_RS485_Comm/%.c Drivers/Custom_RS485_Comm/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -DSTM32 -DSTM32F4 -DSTM32F407VGTx -c -I../Inc -I"D:/STM32_Bootloader/Blackshield_Bootloader/Drivers" -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Drivers-2f-Custom_RS485_Comm

clean-Drivers-2f-Custom_RS485_Comm:
	-$(RM) ./Drivers/Custom_RS485_Comm/Custom_RS485_Comm.cyclo ./Drivers/Custom_RS485_Comm/Custom_RS485_Comm.d ./Drivers/Custom_RS485_Comm/Custom_RS485_Comm.o ./Drivers/Custom_RS485_Comm/Custom_RS485_Comm.su

.PHONY: clean-Drivers-2f-Custom_RS485_Comm

