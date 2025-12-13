from __future__ import annotations

import json
from pathlib import Path
import argparse
import sys

# Use non-interactive backend by default
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as e:
    print(f"matplotlib not available: {e}")
    plt = None

CONFIG_DEVICES_DIR = Path(__file__).resolve().parents[1] / 'config' / 'devices'


def find_latest_device_config() -> Path | None:
    if not CONFIG_DEVICES_DIR.exists():
        return None
    latest_path = None
    latest_mtime = -1.0
    for d in CONFIG_DEVICES_DIR.iterdir():
        if not d.is_dir():
            continue
        cfg = d / 'device_config.json'
        if cfg.exists():
            mtime = cfg.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_path = cfg
    return latest_path


def load_device_config(serial: str | None) -> tuple[Path, dict] | None:
    if serial:
        cfg = CONFIG_DEVICES_DIR / serial / 'device_config.json'
        if not cfg.exists():
            return None
        with open(cfg, 'r') as f:
            return cfg, json.load(f)
    else:
        latest = find_latest_device_config()
        if not latest:
            return None
        with open(latest, 'r') as f:
            data = json.load(f)
        return latest, data


def plot_s_ref(serial: str | None = None, show: bool = False) -> Path | None:
    if plt is None:
        print("matplotlib not installed. Unable to render plot.")
        return None

    loaded = load_device_config(serial)
    if not loaded:
        print('No device_config.json found. Expected under src/config/devices/<SERIAL>/')
        return None

    cfg_path, cfg = loaded
    device_dir = cfg_path.parent
    serial = device_dir.name
    led_cal = cfg.get('led_calibration') or {}
    s_ref = led_cal.get('s_ref_baseline')

    if not s_ref:
        print(f"No s_ref_baseline found in {cfg_path}")
        return None

    wavelengths = led_cal.get('s_ref_wavelengths')

    # Determine x-axis
    # Use wavelengths if present and shape-compatible; else fallback to pixel index
    first_spec = next(iter(s_ref.values()))
    npts = len(first_spec)
    if wavelengths is not None and isinstance(wavelengths, list) and len(wavelengths) == npts:
        x = wavelengths
        x_label = 'Wavelength (nm)'
    else:
        x = list(range(npts))
        x_label = 'Pixel Index'

    # Create plot
    plt.figure(figsize=(10, 6), dpi=120)
    for ch in sorted(s_ref.keys()):
        y = s_ref[ch]
        if not isinstance(y, list):
            # Ensure list-like
            try:
                y = list(y)
            except Exception:
                continue
        # Sanity: lengths
        if len(y) != npts:
            print(f"Warning: channel {ch} length mismatch ({len(y)} vs {npts}); skipping")
            continue
        plt.plot(x, y, label=f"S-ref {ch.upper()}", linewidth=1.0)

    plt.title(f"S-Polarization Reference (device {serial})")
    plt.xlabel(x_label)
    plt.ylabel('Intensity (AU)')
    plt.grid(True, alpha=0.25)
    plt.legend(loc='best')
    plt.tight_layout()

    out_path = device_dir / 's_ref_latest.png'
    try:
        plt.savefig(out_path)
        if show:
            try:
                # Switch to interactive if requested
                import matplotlib
                matplotlib.use(matplotlib.get_backend())
                plt.show()
            except Exception:
                pass
        print(f"Saved: {out_path}")
        return out_path
    except Exception as e:
        print(f"Failed to save plot: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Plot S-pol (S-ref) from latest device config')
    parser.add_argument('--serial', '-s', help='Device serial (e.g., FLMT09116)')
    parser.add_argument('--show', action='store_true', help='Show interactive window (if supported)')
    args = parser.parse_args()

    path = plot_s_ref(args.serial, args.show)
    if path is None:
        sys.exit(1)


if __name__ == '__main__':
    main()
