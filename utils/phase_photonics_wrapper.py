# 
# Python wrapper for the spectrometer API in "SensorT.dll"
# 

import ctypes
from threading import Lock
import numpy as np

# The constants ported from the header file. 
SENSOR_DATA_LEN             =   1848 # = 3696/2 (works with old Sensor.dll)
CONFIG_TRANSFER_SIZE        =   256
STATE_MAX_SIZE              =   256
FT245_PAGE_SIZE             =   1024
MAX_DEV_NUM                 =   127

CONFIG_DATA_AREA_SIZE       =   (16*CONFIG_TRANSFER_SIZE)
NUMBER_OF_CONFIG_SECTORS    =   32

DEFAULT_READ_TIMEOUT        =   5000

# The "TRIG_MODE" enum encapsulated as a Python class. 
class TRIG_MODE:
    INTERNAL_TRIG       = 0
    EXTERNAL_NEG_TRIG   = 1
    EXTERNAL_POS_TRIG   = 2

# The "SHUTTER_STATE" enum encapsulated as a class. 
class SHUTTER_STATE:
    SHUTTER_OFF         = 0
    SHUTTER_ON          = 1

# The "LAMP_STATE". 
class LAMP_STATE:
    LAMP_OFF            = 0
    LAMP_ON             = 1

# The C struct "config_contents" encapsulated into a class. 
class config_contents(ctypes.Structure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("data", ctypes.c_uint8 * CONFIG_DATA_AREA_SIZE)]

# The C struct "SENSOR_STATE_T" encapsulated as a Python class. 
class SENSOR_STATE_T(ctypes.Structure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("sof", ctypes.c_uint32),
                ("major_version", ctypes.c_uint32),
                ("minor_version", ctypes.c_uint32),
                ("integration", ctypes.c_uint32),
                ("offset", ctypes.c_uint32),
                ("averaging", ctypes.c_uint32),
                ("trig_mode", ctypes.c_int32),
                ("trig_tmo", ctypes.c_uint32),
                ("shutter_state", ctypes.c_int32),
                ("shutter_tmo", ctypes.c_uint32),
                ("lamp_state", ctypes.c_int32),
                ("eeprom_addr", ctypes.c_uint32),
                ("trig_tmo_flag", ctypes.c_uint32),
                ("gpio", ctypes.c_uint32)
                ]
    
# The C struct "SENSOR_FRAME_T" encapsulated into a Python class. 
class SENSOR_FRAME_T(ctypes.Structure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("state", SENSOR_STATE_T),
                ("spare1", ctypes.c_uint8 * (STATE_MAX_SIZE - ctypes.sizeof(SENSOR_STATE_T))),
                ("cfg_page", ctypes.c_uint8 * CONFIG_TRANSFER_SIZE),
                ("pixels", ctypes.c_uint16 * SENSOR_DATA_LEN)
                ]



class SpectrometerAPI:
    # The constructor of the class. 
    # It takes only one argument which is the path to the DLL. 
    def __init__(self, dllPathStr: str) -> None:
        self.sensor_t_dll = ctypes.CDLL(dllPathStr)

        # Pre-allocated SENSOR_FRAME_T()
        self.sensor_frame = SENSOR_FRAME_T()

        # Lock to protect the above sensor frame data from race conditions.
        self.lock = Lock()

    # Implementation of the Python wrapper of all APIs in "SensorT.h"
    # This function returns an FT_HANDLE object to the device. 
    def usb_initialize(self, snum: str) -> ctypes.c_void_p:
        name = snum.encode("ascii") + b"\x00" # The null terminator is important!
        _usb_initialize = self.sensor_t_dll.usb_initialize
        # Setting up the argtypes. 
        _usb_initialize.argtypes = [ctypes.c_char_p]
        # Setting the return type. 
        _usb_initialize.restype = ctypes.c_void_p
        # Invoking the API and returning the handle. 
        return ctypes.c_void_p(_usb_initialize(name))
    
    # Python wrapper for "usb_deinit"
    # It takes the handle as the only argument. 
    # The return value is the error code that should be examined for success of the operation.
    def usb_deinit(self, ftHandle: ctypes.c_void_p) -> int:
        # Fetching the API from the DLL. 
        _usb_deinit = self.sensor_t_dll.usb_deinit
        # Setting the argtypes. 
        _usb_deinit.argtypes = [ctypes.c_void_p]
        # Setting the return type. 
        _usb_deinit.restype = ctypes.c_int32
        # Invoking the API and returning the error code. 
        return ctypes.c_int32(_usb_deinit(ftHandle)).value
    
    # Python wrapper for "usb_ping"
    # It takes the handle as the only argument. 
    # The return value is the error code that should be examined to check success of the operation. 
    def usb_ping(self, ftHandle: ctypes.c_void_p) -> int:
        # Fetching the API from the DLL. '
        _usb_ping = self.sensor_t_dll.usb_ping
        # Setting the argtypes. 
        _usb_ping.argtypes = [ctypes.c_void_p]
        # Setting the return type. 
        _usb_ping.restype  = ctypes.c_int32
        # Invoking the API and returning the return code. 
        return ctypes.c_int32(_usb_ping(ftHandle)).value
    
    # Python wrapper for "usb_dll_revision" that, 
    # fetches the revison number of the DLL. 
    # This function returns a tuple! 
    # The first element of the tuple is the return code. 
    # The second element is the Python int object that stores the revision number. 
    def usb_dll_revision(self):
        # Fetching the API from the DLL. 
        _usb_dll_revision = self.sensor_t_dll.usb_dll_revision
        # Setting the argument types. 
        _usb_dll_revision.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
        # Setting the return type. 
        _usb_dll_revision.restype = ctypes.c_int32
        # The integer that stores the revison number. 
        revison_number = ctypes.c_uint32(0)
        # Invoking the API. 
        ret = ctypes.c_int32(_usb_dll_revision(ctypes.byref(revison_number)))

        # Returning the tuple!
        return (ret.value, revison_number.value)
    
    # Python wrapper for the function that returns the USB firmware revison number. 
    # This function also returns a tuple!
    # The only arg this function takes is the handle to the USB device. 
    # The first element is the return code of the API. 
    # The second element is the revision number (Python int)
    def usb_fw_revision(self, ftHandle: ctypes.c_void_p):
        # Fetching the API from the DLL. 
        _usb_fw_revision = self.sensor_t_dll.usb_fw_revision
        # Setting the argtypes. 
        _usb_fw_revision.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        # Setting the return type. 
        _usb_fw_revision.restype = ctypes.c_int32
        # Variable to store the revision number. 
        revision_number = ctypes.c_uint32(0)
        # Invoking the API. 
        ret = ctypes.c_int32(_usb_fw_revision(ftHandle, ctypes.byref(revision_number)))
        # Returning the result as a tuple. 
        return (ret.value, revision_number.value)
    
    # Python wrapper for the function "usb_read_image"
    # This function returns a tuple!
    # The first element is the return code of the C API, 
    # which should be checked by the developer. 
    #
    # The second is the SENSOR_FRAME_T object containing the data. 
    def usb_read_image(self, ftHandle: ctypes.c_void_p):
        # Fetching the API from the DLL. 
        _usb_read_image = self.sensor_t_dll.usb_read_image
        # Setting the argtypes. 
        _usb_read_image.argtypes = [ctypes.c_void_p, ctypes.POINTER(SENSOR_FRAME_T)]
        # Setting the restype.
        _usb_read_image.restype = ctypes.c_int32
        # The SENSOR_FRAME_T class that stores the result. 
        sensor_frame_t_obj = SENSOR_FRAME_T()
        # Invoking the API and getting the return value. 
        ret = ctypes.c_int32(_usb_read_image(ftHandle, ctypes.byref(sensor_frame_t_obj)))

        # NOTE: Return code -1 means partial read (device sends 1848 pixels but DLL expects 3700)
        # The data in the first 1848 pixels is still valid, so we return success (0) instead
        actual_ret = 0 if ret.value == -1 else ret.value
        
        # Returning the tuple containing the return code and resulting SENSOR_FRAME_T object. 
        return (actual_ret, sensor_frame_t_obj)

    # Implementation of the function that reads and returns the pixels in sensor frame.
    def usb_read_pixels(self, ftHandle: ctypes.c_void_p, data_type=np.float32):
        """Implementation of the function that reads and returns the pixels in sensor frame."""
        
        # Acquiring the lock.
        self.lock.acquire()

        # Calling the API.
        ret_val = self.usb_read_image_v2(ftHandle, self.sensor_frame)

        # The pixel data. 
        pixel_data = np.asarray(self.sensor_frame.pixels, dtype=data_type)

        # Releasing the lock.
        self.lock.release()

        # Returning a view to the pixels and the return value as a tuple.
        return (ret_val, pixel_data)


    
    # Implementation of a faster version of `usb_read_image`. 
    # This version returns the return code of the C API. 
    # It fills a preallocated struct object (SENSOR_FRAME_T)
    def usb_read_image_v2(self, ftHandle: ctypes.c_void_p, sensor_frame_t_obj: SENSOR_FRAME_T) -> int:
    	
        # Fetching the API from the DLL. 
        _usb_read_image = self.sensor_t_dll.usb_read_image
        # Setting the argtypes. 
        _usb_read_image.argtypes = [ctypes.c_void_p, ctypes.POINTER(SENSOR_FRAME_T)]
        # Setting the restype.
        _usb_read_image.restype = ctypes.c_int32
        
        # Invoking the API and getting the return value. 
        ret = ctypes.c_int32(_usb_read_image(ftHandle, ctypes.byref(sensor_frame_t_obj)))

        # NOTE: Return code -1 means partial read (device sends 1848 pixels but DLL expects 3700)
        # The data in the first 1848 pixels is still valid, so we return success (0) instead
        actual_ret = 0 if ret.value == -1 else ret.value
        
        # Returning the return code of the API in the DLL.
        return actual_ret
    
    # Python wrapper for "usb_set_trig_mode"
    # This function takes the exact same list of args as the original, 
    # API and returns the status code. 
    def usb_set_trig_mode(self, ftHandle: ctypes.c_void_p, trig_mode: int) -> int:
        # Fetching the API from the DLL. 
        _usb_set_trig_mode = self.sensor_t_dll.usb_set_trig_mode
        # Setting the argtypes. 
        _usb_set_trig_mode.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        # Setting the return type. 
        _usb_set_trig_mode.restype = ctypes.c_int32

        # Invoking the API and returning the return value. 
        return ctypes.c_int32(_usb_set_trig_mode(ftHandle, trig_mode)).value
    
    # Python wrapper for "usb_set_trig_tmo"
    # Same argument list like C API. 
    # Developer must check return value!
    def usb_set_trig_tmo(self, ftHandle: ctypes.c_void_p, tmo: ctypes.c_uint32) -> int:
        # Fetching the API from the DLL. 
        _usb_set_trig_tmo = self.sensor_t_dll.usb_set_trig_tmo
        # Setting the argtypes. 
        _usb_set_trig_tmo.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        # Setting the return type. 
        _usb_set_trig_tmo.restype = ctypes.c_int32
        # Invoking the API and returning the return code. 
        return ctypes.c_int32(_usb_set_trig_tmo(ftHandle, tmo)).value
    
    # Python wrapper for "usb_set_lamp"
    # Same argument list like C API. 
    # Return value must be checked to see if function succeeded. 
    def usb_set_lamp(self, ftHandle: ctypes.c_void_p, lamp_state: int) -> int:
        # Fetching the API signature from the DLL. 
        _usb_set_lamp = self.sensor_t_dll.usb_set_lamp
        # Setting the argtypes. 
        _usb_set_lamp.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        # Setting the return type. 
        _usb_set_lamp.restype = ctypes.c_int32
        # Invoking the API and returning the return code!
        return ctypes.c_int32(_usb_set_lamp(ftHandle, lamp_state)).value
    
    # Python wrapper for "usb_set_shutter_tmo"
    def usb_set_shutter_tmo(self, ftHandle: ctypes.c_void_p, tmo: ctypes.c_uint32) -> int:
        # Fetching the API from the DLL.
        _usb_set_shutter_tmo = self.sensor_t_dll.usb_set_shutter_tmo
        # Setting the argtypes. 
        _usb_set_shutter_tmo.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        # Setting the return type!
        _usb_set_shutter_tmo.restype = ctypes.c_int32
        # Invoking the API and returning the return code. 
        return ctypes.c_int32(_usb_set_shutter_tmo(ftHandle, tmo)).value
    
    # Python wrapper for "usb_set_shutter"
    # It takes the same list of arguments as the C API
    # Return value must be checked to see if function succeeded. 
    def usb_set_shutter(self, ftHandle: ctypes.c_void_p, shutterState: int) -> int:
        # Fetching the function from the DLL. 
        _usb_set_shutter = self.sensor_t_dll.usb_set_shutter
        # Setting up the argument types. 
        _usb_set_shutter.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        # Setting the return type. 
        _usb_set_shutter.restype = ctypes.c_int32
        # Invoking the API and returning the return value.
        return ctypes.c_int32(_usb_set_shutter(ftHandle, shutterState)).value
    
    # Python wrapper for the function: "usb_set_interval"
    def usb_set_interval(self, ftHandle: ctypes.c_void_p, data: int) -> int:
        # Fetching the API from the DLL. 
        _usb_set_interval = self.sensor_t_dll.usb_set_interval
        # Setting the argument types. 
        _usb_set_interval.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        # Setting the return type. 
        _usb_set_interval.restype = ctypes.c_int32
        # Invoking the API and returning the return value. 
        return ctypes.c_int32(_usb_set_interval(ftHandle, data)).value
    
    # Python wrapper for the function "usb_set_offset"
    def usb_set_offset(self, ftHandle: ctypes.c_void_p, data: int) -> int:
        # Fetching the API from the DLL. 
        _usb_set_offset = self.sensor_t_dll.usb_set_offset
        # Setting the argument types. 
        _usb_set_offset.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        # Setting the restype. 
        _usb_set_offset.restype = ctypes.c_int32
        # Invoking the API and returning the return value. 
        return ctypes.c_int32(_usb_set_offset(ftHandle, data)).value
    
    # Python wrapper for the function "usb_set_averaging"
    def usb_set_averaging(self, ftHandle: ctypes.c_void_p, avg: int) -> int:
        # Fetching the API from the DLL. 
        _usb_set_averaging = self.sensor_t_dll.usb_set_averaging
        # Setting the argument types. 
        _usb_set_averaging.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        # Setting the restype. 
        _usb_set_averaging.restype = ctypes.c_int32
        # Invoking the API and returning the return value. 
        return ctypes.c_int32(_usb_set_averaging(ftHandle, avg)).value
    
    # Python wrapper for the function "mult_and_subtract". 
    # This function takes in an integer and returns an integer!
    # This function looks like it deosn't deal with the sensor!
    def mult_and_subtract(self, a: int) -> int:
        # Fetching the API from the DLL. 
        _mult_and_subtract = self.sensor_t_dll.mult_and_subtract
        # Setting the argument types. 
        _mult_and_subtract.argtypes = [ctypes.c_int32]
        # Setting the return type. 
        _mult_and_subtract.restype = ctypes.c_int32
        # Invoking the API and returning the value. 
        return ctypes.c_int32(_mult_and_subtract(a)).value
    
    # Python wrapper for "usb_erase_config"
    # This function takes only the handle to the USB device. 
    # Return value can be checked if the function succeeded!
    def usb_erase_config(self, ftHandle: ctypes.c_void_p) -> int:
        # Fetching the function from the DLL. 
        _usb_erase_config = self.sensor_t_dll.usb_erase_config
        # Setting the argument types. 
        _usb_erase_config.argtypes = [ctypes.c_void_p]
        # Setting the return type. 
        _usb_erase_config.restype = ctypes.c_int32
        # Invoking the API "usb_erase_config" and returning the return value. 
        return ctypes.c_int32(_usb_erase_config(ftHandle)).value
    
    # Python wrapper for the function "usb_read_config"
    # This function takes the handle to the device and the "area_number" it's only argument. 
    # It returns a tuple: 
    #           The first element of the tuple is the API's return code. 
    #           The second element of the tuple is the "config_contents" struct containing the read data.  
    def usb_read_config(self, ftHandle: ctypes.c_void_p, area_number: int):
        # Fetching the function from the DLL. 
        _usb_read_config = self.sensor_t_dll.usb_read_config
        # Setting the argument types. 
        _usb_read_config.argtypes = [ctypes.c_void_p, ctypes.POINTER(config_contents), ctypes.c_uint32]
        # Setting the return type. 
        _usb_read_config.restype = ctypes.c_int32
        # The "config_contents" object that will be returned in the tuple!
        cc = config_contents()
        ret = ctypes.c_int32(_usb_read_config(ftHandle, ctypes.byref(cc), area_number)).value
        # Returning the tuple!
        return (ret, cc)
    
    # Python wrapper for the function "usb_write_config"
    # This function takes the handle to the device, the "config_contents" object containing data to write, and the area number as the arguments. 
    # The return value needs to be checked to see if it was successful. 
    def usb_write_config(self, ftHandle: ctypes.c_void_p, cc: config_contents, area_number: int) -> int:
        # Fetching the function from the DLL. 
        _usb_write_config = self.sensor_t_dll.usb_write_config
        # Setting the argument types. 
        _usb_write_config.argtypes = [ctypes.c_void_p, 
                                      ctypes.POINTER(config_contents),
                                      ctypes.c_uint32]
        # Setting the return type. 
        _usb_write_config.restype = ctypes.c_int32
        # Invoking the API and returning the return code. 
        return ctypes.c_int32(_usb_write_config(ftHandle, ctypes.byref(cc), area_number)).value
    

    def usb_set_gpio(self, ftHandle: ctypes.c_void_p, value: int) -> int:
        """The DLL API ```usb_set_gpio(FT_HANDLE, uint32_t)```"""

        # The API.
        _usb_set_gpio = self.sensor_t_dll.usb_set_gpio

        # Arg types & return value. 
        _usb_set_gpio.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        _usb_set_gpio.restype = ctypes.c_int32

        # Invoking the API and returning the code.
        return ctypes.c_int32(_usb_set_gpio(ftHandle, value)).value

    def glow_led(self, ftHandle: ctypes.c_void_p, ledIndex: int) -> int:
        """Function that glows the LEDs\n
           0 - All LEDs Off.\n
           1 - Turn first LED only on.\n
           2 - Turn second LED only on.. and so on. \n
        """
        if ledIndex == 0:
            value = 0
        else:
            value = 1 << (ledIndex - 1)
        
        return self.usb_set_gpio(ftHandle, value)
    



##### END OF IMPLEMENTATION #####    
