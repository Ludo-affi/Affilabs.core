"""Minimal working detector test using only confirmed working methods."""

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

print("Opening detector...")
det = PhasePhotonics()

if det.open():
    print(f"Connected: {det.serial_number}")
    print(f"Pixels: {det.num_pixels}")

    print("\nSetting integration to 100ms...")
    det.set_integration(100)

    print("\nReading spectrum...")
    spectrum = det.read_intensity()

    if spectrum is not None:
        print(f"SUCCESS! Got {len(spectrum)} points")
        print(f"Min: {spectrum.min()}, Max: {spectrum.max()}, Mean: {spectrum.mean():.1f}")
    else:
        print("FAILED to get spectrum")

    det.close()
else:
    print("FAILED to open detector")
