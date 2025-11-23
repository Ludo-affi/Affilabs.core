from time import monotonic, sleep

from numpy import arange, asarray, frombuffer, savez, zeros
from numpy.polynomial import Polynomial
from scipy.optimize import root_scalar

from utils.controller import PicoEZSPR
from utils.SpectrometerAPI import SENSOR_DATA_LEN, SpectrometerAPI

api = SpectrometerAPI("./utils/Sensor.dll")
h = api.usb_initialize("ST00014")
f = Polynomial(frombuffer(api.usb_read_config(h, 0)[1].data, ">d", 4, 3072))
w = f(arange(SENSOR_DATA_LEN))
start, end = w.searchsorted((560, 720))
delay = 0.3


def capture():
    return asarray(api.usb_read_image(h)[1].pixels, float)[start:end]


def set_integration(x):
    api.usb_set_interval(h, int(x * 1000))


def find_integration():
    def f(x):
        set_integration(x)
        sleep(delay)
        return capture().max() - 3000

    return root_scalar(f, bracket=(0.01, 200), xtol=0.01).root


def main():
    p = PicoEZSPR()
    if not p.open():
        raise RuntimeError

    for ch in "abcd":
        print(f"Capturing channel {ch}")

        p.set_intensity(ch, 255)
        p.set_mode("s")
        sleep(1)
        print(f"S mode integration time: {find_integration():.3} ms")

        p.turn_off_channels()
        sleep(delay)
        dark = capture()
        p.turn_on_channel(ch)
        sleep(delay)
        ref = capture() - dark

        p.set_mode("p")
        sleep(delay)
        m = 500
        t = find_integration()
        n = int(200 / t)
        print(f"P mode integration time: {t:.3} ms")

        p.turn_off_channels()
        sleep(delay)
        dark = capture()
        p.turn_on_channel(ch)
        sleep(delay)

        num = n * m
        spectra = zeros((num, end - start))
        times = zeros(num)
        start_time = monotonic()

        print(f"Spectra \033[s     /{num:<5} taken")
        for i in range(m * n):
            print(f"\033[u{i:5}")
            times[i] = monotonic()
            spectra[i] = capture()
        print(f"\033[u{num:5}")

        times -= start_time

        spectra -= dark
        spectra /= ref

        savez(f"Phase_{ch}", spectra=spectra, times=times, wavelengths=w[start:end])


if __name__ == "__main__":
    main()
