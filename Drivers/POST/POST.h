/*
 * POST.h
 *
 *  Created on: Jun 23, 2025
 *      Author: kunal
 */

#ifndef POST_POST_H_
#define POST_POST_H_

#include "main.h"

#define TIMEOUT_COUNT 0x5000U

typedef enum {
	POST_OK=0,
	POST_FAIL
} POST_Result;

POST_Result POST_ClockCheck(void);
POST_Result POST_CPUCoreTest(void);
POST_Result POST_SRAM_Test(void);
POST_Result POST_FlashCRC(void);
POST_Result POST_InterruptTest(void);
POST_Result POST_WatchdogTest(void);
void fail_safe(void);

#endif /* POST_POST_H_ */
