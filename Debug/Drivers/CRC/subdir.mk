################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/CRC/CRC.c 

OBJS += \
./Drivers/CRC/CRC.o 

C_DEPS += \
./Drivers/CRC/CRC.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/CRC/%.o Drivers/CRC/%.su Drivers/CRC/%.cyclo: ../Drivers/CRC/%.c Drivers/CRC/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -g3 -DDEBUG -DSTM32 -DSTM32F4 -DSTM32F407VGTx -c -I../Inc -I"D:/STM32_Bootloader/Blackshield_Bootloader/Drivers" -I"D:/STM32_Bootloader/Blackshield_Bootloader/Bootloader" -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Drivers-2f-CRC

clean-Drivers-2f-CRC:
	-$(RM) ./Drivers/CRC/CRC.cyclo ./Drivers/CRC/CRC.d ./Drivers/CRC/CRC.o ./Drivers/CRC/CRC.su

.PHONY: clean-Drivers-2f-CRC

