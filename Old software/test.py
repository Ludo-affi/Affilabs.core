from matplotlib.pyplot import plot, show

from utils.SpectrometerAPI import SpectrometerAPI

# Load DLL and connect to spectrometer
api = SpectrometerAPI("./utils/SensorT_x64.dll")
handle = api.usb_initialize("ST00005")

# Set integration time and take 10 spectra
api.usb_set_interval(handle, 5_000)
for _ in range(10):
    _retrun_value, data = api.usb_read_image(handle)
    # 274 to 1931 is the range we care about
    plot(data.pixels[274:1931], color="red")

# Set new integration time and take 10 more spectra
api.usb_set_interval(handle, 10_000)
for _ in range(10):
    _retrun_value, data = api.usb_read_image(handle)
    plot(data.pixels[274:1931], color="green")

# Show plots
show()
