################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/POST/POST.c 

OBJS += \
./Drivers/POST/POST.o 

C_DEPS += \
./Drivers/POST/POST.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/POST/%.o Drivers/POST/%.su Drivers/POST/%.cyclo: ../Drivers/POST/%.c Drivers/POST/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -DSTM32 -DSTM32F4 -DSTM32F407VGTx -c -I../Inc -I"D:/STM32_Bootloader/Blackshield_Bootloader/Drivers" -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Drivers-2f-POST

clean-Drivers-2f-POST:
	-$(RM) ./Drivers/POST/POST.cyclo ./Drivers/POST/POST.d ./Drivers/POST/POST.o ./Drivers/POST/POST.su

.PHONY: clean-Drivers-2f-POST

