################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (12.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/CAN/CAN.c 

OBJS += \
./Drivers/CAN/CAN.o 

C_DEPS += \
./Drivers/CAN/CAN.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/CAN/%.o Drivers/CAN/%.su Drivers/CAN/%.cyclo: ../Drivers/CAN/%.c Drivers/CAN/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -DSTM32 -DSTM32F4 -DSTM32F407VGTx -c -I../Inc -I"D:/STM32F407_Projects/Blackshield_Bootloader/Drivers" -Os -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Drivers-2f-CAN

clean-Drivers-2f-CAN:
	-$(RM) ./Drivers/CAN/CAN.cyclo ./Drivers/CAN/CAN.d ./Drivers/CAN/CAN.o ./Drivers/CAN/CAN.su

.PHONY: clean-Drivers-2f-CAN

