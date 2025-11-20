# Detector Configuration Example

## Switching Between USB4000 and PhasePhotonics Detectors

Add this entry to your `config.json` file:

```json
{
  "detector_type": "USB4000",
  ...rest of your configuration...
}
```

### Options:

**USB4000 (Default - OceanOptics)**
```json
"detector_type": "USB4000"
```
- Uses Ocean Optics USB4000 or FLAME-T spectrometer
- Requires SeaBreeze (pyseabreeze) library
- 3700 data points
- Production ready ✅

**PhasePhotonics (Placeholder)**
```json
"detector_type": "PhasePhotonics"
```
- Uses PhasePhotonics spectrometer
- Requires SensorT.dll and ftd2xx library
- 1848 data points
- ⚠️ PLACEHOLDER - Not yet implemented

### If not specified

If `detector_type` is missing from config.json, the system defaults to `"USB4000"`.

### Full Documentation

See `PHASE_PHOTONICS_INTEGRATION.md` for complete implementation guide.
