from time import monotonic, sleep

from numpy import arange, asarray, frombuffer, full, savez, zeros
from numpy.polynomial import Polynomial
from scipy.optimize import root_scalar

from utils.controller import PicoEZSPR
from utils.SpectrometerAPI import SENSOR_DATA_LEN, SpectrometerAPI


def main():
    p = PicoEZSPR()
    if not p.open():
        raise RuntimeError

    api = SpectrometerAPI("./utils/SensorT_x64.dll")
    h = api.usb_initialize("ST00014")

    f = Polynomial(frombuffer(api.usb_read_config(h, 0)[1].data, ">d", 4, 3072))
    w = f(arange(SENSOR_DATA_LEN))

    start, end = w.searchsorted((560, 720))

    delay = 0.1

    def capture():
        return asarray(api.usb_read_image(h)[1].pixels, float)[start:end]

    def set_integration(x):
        api.usb_set_interval(h, int(x * 1000))

    def find_integration():
        def f(x):
            set_integration(x)
            sleep(0.3)
            return capture().max() - 3000

        return root_scalar(f, bracket=(2, 200), xtol=0.01).root

    n = 300
    data = {ch: zeros((n, end - start)) for ch in "abcd"}
    times = {ch: full(n, -monotonic()) for ch in "abcd"}
    darks = {ch: zeros(end - start) for ch in "abcd"}
    refs = {ch: zeros(end - start) for ch in "abcd"}
    ints = {}
    nums = {}

    print("Taking references")
    p.set_mode("s")
    for ch in "abcd":
        p.set_intensity(ch, 255)
        sleep(delay)
        find_integration()

        p.turn_off_channels()
        sleep(delay)
        darks[ch] = capture()

        p.turn_on_channel(ch)
        sleep(delay)
        refs[ch] = capture() - darks[ch]

    print("Taking darks")
    p.set_mode("p")
    for ch in "abcd":
        p.turn_on_channel(ch)
        sleep(delay)
        ints[ch] = find_integration()
        nums[ch] = int(200 / ints[ch])

        p.turn_off_channels()
        darks[ch][:] = 0
        sleep(delay)
        darks[ch] = capture()

    print(f"Spectra \033[s     /{n:<5} taken")
    for i in range(n):
        print(f"\033[u{i:5}")
        for ch in "abcd":
            set_integration(ints[ch])
            p.turn_on_channel(ch)
            sleep(delay)
            times[ch][i] += monotonic()
            for _ in range(nums[ch]):
                data[ch][i] += capture()
    print(f"\033[u{n:5}")

    for ch in "abcd":
        data[ch] = (data[ch] / nums[ch] - darks[ch]) / refs[ch]
        savez(
            f"Phase_new_{ch}",
            spectra=data[ch],
            wavelengths=w[start:end],
            times=times[ch],
        )


if __name__ == "__main__":
    main()
