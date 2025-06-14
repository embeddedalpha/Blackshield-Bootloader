################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/Flash/Flash.c 

OBJS += \
./Drivers/Flash/Flash.o 

C_DEPS += \
./Drivers/Flash/Flash.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/Flash/%.o Drivers/Flash/%.su Drivers/Flash/%.cyclo: ../Drivers/Flash/%.c Drivers/Flash/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -g3 -DDEBUG -DSTM32 -DSTM32F4 -DSTM32F407VGTx -c -I../Inc -I"D:/STM32F407_Projects/Blackshield_Bootloader/Drivers" -Oz -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Drivers-2f-Flash

clean-Drivers-2f-Flash:
	-$(RM) ./Drivers/Flash/Flash.cyclo ./Drivers/Flash/Flash.d ./Drivers/Flash/Flash.o ./Drivers/Flash/Flash.su

.PHONY: clean-Drivers-2f-Flash

