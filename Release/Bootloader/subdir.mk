################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Bootloader/Bootloader.c 

OBJS += \
./Bootloader/Bootloader.o 

C_DEPS += \
./Bootloader/Bootloader.d 


# Each subdirectory must supply rules for building sources it contributes
Bootloader/%.o Bootloader/%.su Bootloader/%.cyclo: ../Bootloader/%.c Bootloader/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -DSTM32 -DSTM32F4 -DSTM32F407VGTx -c -I../Inc -I"D:/STM32_Bootloader/Blackshield_Bootloader/Drivers" -I"D:/STM32_Bootloader/Blackshield_Bootloader/Bootloader" -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Bootloader

clean-Bootloader:
	-$(RM) ./Bootloader/Bootloader.cyclo ./Bootloader/Bootloader.d ./Bootloader/Bootloader.o ./Bootloader/Bootloader.su

.PHONY: clean-Bootloader

