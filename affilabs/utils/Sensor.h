#ifndef SENSOR_DLL_H
#define SENSOR_DLL_H


#if defined _WIN32

	#ifdef BUILDING_DLL
		#define SENSOR_DLL __declspec(dllexport)
	#else
		#define SENSOR_DLL __declspec(dllimport)
	#endif
#else
		#define SENSOR_DLL 
#endif

#include <stdio.h>
#include <stdint.h>
#include "ftd2xx.h"

#define SENSOR_DATA_T     uint16_t
#define SENSOR_DATA_LEN   3700
#define CONFIG_TRANSFER_SIZE 256
#define STATE_MAX_SIZE       256

#define FT245_PAGE_SIZE      1024
#define MAX_DEV_NUM    127

#define CONFIG_DATA_AREA_SIZE  (16*CONFIG_TRANSFER_SIZE)  // 4kB config area
#define NUMBER_OF_CONFIG_SECTORS (32)     // 21*4kB = 128kB in total
#define APP_MAX_LENGTH (0x20000)         //  128kB in total

#define DEFAULT_READ_TIMEOUT 5000
#define APP_SIZE_MAX         0x20000

/* Data Types */
// Config area contents

typedef enum {
	INTERNAL_TRIG = 0,
	EXTERNAL_NEG_TRIG,
	EXTERNAL_POS_TRIG
} TRIG_MODE;


typedef enum {
	SHUTTER_OFF = 0,
	SHUTTER_ON
} SHUTTER_STATE;

typedef enum {
	LAMP_OFF = 0,
	LAMP_ON
} LAMP_STATE;



typedef struct
{
	uint8_t  data[CONFIG_DATA_AREA_SIZE];
} config_contents;


#pragma pack(push, 1)
typedef struct {
	uint32_t  sof;
	uint32_t  major_version;
	uint32_t  minor_version;
	uint32_t  integration;
	uint32_t  offset;
	uint32_t  averaging;
	TRIG_MODE trig_mode;
	uint32_t trig_tmo;
	SHUTTER_STATE shutter_state;
	uint32_t shutter_tmo;
	LAMP_STATE    lamp_state;
	uint32_t eeprom_addr;
	uint32_t trig_tmo_flag;
	uint32_t gpio;
} SENSOR_STATE_T;

typedef struct {
	uint32_t  sof;
	uint32_t  major_version;
	uint32_t  minor_version;
	uint32_t  crc;
	uint32_t  eeprom_addr;
} BOOTLOADER_STATE_T;


typedef struct sensor_frame_ {
	SENSOR_STATE_T state;
	uint8_t spare1[STATE_MAX_SIZE - sizeof(SENSOR_STATE_T)];
	uint8_t cfg_page[CONFIG_TRANSFER_SIZE];
	uint8_t spare2[FT245_PAGE_SIZE - CONFIG_TRANSFER_SIZE - STATE_MAX_SIZE];
	SENSOR_DATA_T pixels[SENSOR_DATA_LEN];
} SENSOR_FRAME_T;
#pragma pack(pop)


/* Function prototypes common functions*/

// Open Close and Ping the device

FT_HANDLE SENSOR_DLL usb_initialize(char * snum);
int SENSOR_DLL usb_deinit(FT_HANDLE ftHandle);
int SENSOR_DLL usb_ping(FT_HANDLE ftHandle);

// Revision read and write functions
int SENSOR_DLL usb_dll_revision(unsigned int *revision);
int SENSOR_DLL usb_fw_revision(FT_HANDLE ftHandle, unsigned int *revision);

// Read image synchronously (internal trigger) and with external trigger
int SENSOR_DLL usb_read_image(FT_HANDLE ftHandle, SENSOR_FRAME_T *frame);

// Device configuration
int SENSOR_DLL usb_set_trig_mode(FT_HANDLE ftHandle, TRIG_MODE mode);
int SENSOR_DLL usb_set_trig_tmo(FT_HANDLE ftHandle, uint32_t tmo);
int SENSOR_DLL usb_set_lamp(FT_HANDLE ftHandle, LAMP_STATE mode);
int SENSOR_DLL usb_set_shutter_tmo(FT_HANDLE ftHandle, uint32_t tmo);
int SENSOR_DLL usb_set_shutter(FT_HANDLE ftHandle, SHUTTER_STATE state);
int SENSOR_DLL usb_set_interval(FT_HANDLE ftHandle, uint32_t data);
int SENSOR_DLL usb_set_offset(FT_HANDLE ftHandle, uint32_t data);
int SENSOR_DLL  usb_set_averaging(FT_HANDLE ftHandle, uint32_t avg);
int SENSOR_DLL mult_and_subtract(int32_t a);
int SENSOR_DLL usb_erase_config(FT_HANDLE ftHandle);
int SENSOR_DLL usb_read_config(FT_HANDLE ftHandle, config_contents  *config_contents_p, uint32_t area_number);
int SENSOR_DLL usb_write_config(FT_HANDLE ftHandle, config_contents *config_contents_p, uint32_t area_number);
int SENSOR_DLL usb_write_crc_app(FT_HANDLE ftHandle);
int SENSOR_DLL usb_restart_app(FT_HANDLE ftHandle);
int SENSOR_DLL usb_erase_app(FT_HANDLE ftHandle);
int SENSOR_DLL usb_write_app(FT_HANDLE ftHandle, uint8_t* app_data_p, uint32_t  length);
int SENSOR_DLL usb_set_gpio(FT_HANDLE ftHandle, uint32_t data);
int SENSOR_DLL usb_get_state(FT_HANDLE ftHandle, void * state);


#endif
