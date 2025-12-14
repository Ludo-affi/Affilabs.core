## Width vs. Shift: Bias Mechanism, Modeling, and Robust Peak Tracking

This note documents how transmission-band width/asymmetry biases wide-window peak estimates, how our system times acquisitions, and two robust strategies to separate “true shift” (SPR physics) from width changes (e.g., afterglow/timing).

### TL;DR

- Single-LED collection is safe: we wait ~1.0 s after setting intensity before acquiring; width bias from afterglow is negligible.
- Live cycling depends on LED_DELAY (settings). Too small a delay lets afterglow from LED N bleed into LED N+1 → right-side broadening → wide-window centroid bias.
- Two robust solutions:
  1) Parametric fit (exGaussian dip) that returns center μ (true shift) and separate width/tail (σ, τ).
  2) Fast physics-aware centroid (wide + right-side decay) plus a simple asymmetry correction learned on synthetic variants.
- A new simulator lets you sweep width/asymmetry vs true shift and quantify bias for different estimators.

---

## 1) Acquisition timing and afterglow

Where the delays come from and how they’re applied:

- Single-LED training collector: `collect_training_data.py`
  - After setting LED intensity and integration time, we wait 1.0 s before capturing spectra.
  - Dark frames are collected 0.5 s after turning LEDs off.
  - Polarizer moves add 2.0 s + 0.5 s settle, but they occur before dark collection.
  - Net: single-LED runs are conservative; afterglow/timing does not bias width.

- Live cycling (multi-channel):
  - LED settle delay is `LED_DELAY` from `settings/settings.py` (current default: 0.020 s).
  - Acquisition core (`utils/spr_data_acquisition.py`) turns on channel → sleeps `led_delay` → acquires.
  - If afterglow calibration is available (see `led_afterglow_model.py` and device config), the calibrator sets an optimized LED delay for live mode; otherwise the default is used.

Recommendation for cycling:

- Characterize afterglow and adopt an LED delay that yields ≤1–2% residual at your integration time. This minimizes right-tail broadening and reduces width-induced bias at the source.

References in repo:

- `settings/settings.py`: LED_DELAY default and acquisition timing model
- `utils/spr_data_acquisition.py`: where delay is enforced before acquisition
- `utils/spr_calibrator.py`: loads afterglow calibration and can set optimized delay
- `led_afterglow_model.py`: tool to measure decay and recommend delays

---

## 2) Why width/asymmetry biases wide-window peak estimates

- A wider (or right-skewed) transmission dip drags a wide-window centroid to the right, even if the physical resonance center hasn’t shifted.
- In single-LED tests, width is stable → wide windows are great (low P–P/STD). In cycling, afterglow/timing varies width between channels/frames → mean gets biased.

We validated these effects and their fixes on your dataset via:

- Wide centroid windows (40–150 nm), with and without physics-aware right-side decay
- Bias correction aligning to a small baseline window (e.g., 8 nm)
- Edge-based and parabolic methods for cross-check

---

## 3) New simulator: width vs. true shift and estimator bias

Script: `analyze_width_vs_shift_model.py`

What it does:

- Loads a base transmission spectrum, or generates a synthetic baseline if none is provided.
- Synthesizes spectra with:
  - True shift ±Δ nm
  - Symmetric Gaussian broadening (σ nm)
  - Right-sided exponential tail (τ nm) to mimic afterglow skew
- Evaluates estimators: small-window parabolic, wide centroid, physics-aware centroid, left 50% edge, parametric exGaussian fit, and a simple asymmetry-corrected centroid.
- Saves a JSON summary and plots (e.g., bias vs. σ in width-only cases).

Quick run (PowerShell):

```powershell
# Synthetic baseline (quick smoke test)
.\.venv312\Scripts\python.exe .\analyze_width_vs_shift_model.py --output-dir analysis_results\width_vs_shift_model

# With your own CSV (two columns: wavelength_nm, transmission)
.\.venv312\Scripts\python.exe .\analyze_width_vs_shift_model.py `
  --input-csv path\to\transmission.csv `
  --shift-nm -0.5 0 0.5 `
  --gauss-sigma 0 0.5 1.0 2.0 `
  --asym-tau 0 0.5 1.0 `
  --center-estimators parabolic centroid physics-aware left-edge fit-exgauss `
  --output-dir analysis_results\width_vs_shift_model
```

Outputs:

- `analysis_results/width_vs_shift_model/summary.json` — estimator errors over the (Δ, σ, τ) grid
- `analysis_results/width_vs_shift_model/bias_vs_sigma.png` — quick view of width-only bias per method

Useful interpretation:

- exGaussian fit (`fit_exgauss`) should show near-zero bias across σ/τ since it separates μ (true center) from σ/τ.
- Physics-aware centroid reduces bias vs. plain wide centroid.
- Asymmetry-corrected centroid (centroid − k·asymmetry) can approach exGaussian accuracy with negligible compute if k is tuned on width-only cases.

---

## 4) Two robust solutions

1) Parametric fit (accurate)

- Fit an exGaussian “dip” around the minimum to estimate:
  - μ (true resonance center → your shift)
  - σ (symmetric width)
  - τ (right tail, often afterglow/timing)
- Optionally track [μ, σ, τ] with a small Kalman filter for temporal stability.
- Use as primary estimate; fall back to parabolic if the fit fails.

2) Fast physics-aware centroid + asymmetry correction (lightweight)

* Compute a wide-window centroid (e.g., 100 nm) with a right-side exponential decay (gamma ≈ 0.02) to downweight tail.
* Compute asymmetry from left/right half-depth edges (e.g., at 50% depth).
* Correct centroid: μ̂ = centroid − k · asymmetry, with k learned on width-only synthetic variants to minimize bias.
* Runtime is similar to our current centroid; very robust when combined with a properly tuned `LED_DELAY`.

---

## 5) What’s already wired and how to use it

- Physics-aware centroid in the collector (`collect_training_data.py`):
  - Preset flag: `--physics-aware-centroid` (sets window=100 nm, right-decay-gamma=0.02, bias correction baseline 8 nm)
  - Shows low P–P/STD with unbiased mean on your dataset.

- Live cycling uses `LED_DELAY` for inter-LED settle:
  - Default in `settings/settings.py` is 0.020 s (tune or adopt calibrated values).
  - If afterglow calibration is present, live mode logs “Using LED delay from calibration: … ms”.

---

## 6) Recommended path

1) Characterize afterglow and set LED_DELAY for ≤1–2% residual at your integration time (minimizes tail growth).
2) Choose an estimator for live use:
   - Highest accuracy: exGaussian fit (±60 nm window), fallback to parabolic.
   - Lowest latency: physics-aware centroid + asymmetry correction with a tuned k.
3) (Optional) Add a tiny “k-calibration” that runs the simulator around the current spectrum and writes k to device config.

---

## 7) File map

- `collect_training_data.py` — single-LED collection; physics-aware centroid preset available; conservative timing
- `settings/settings.py` — `LED_DELAY` for live cycling
- `utils/spr_data_acquisition.py` — enforces per-channel LED delay before acquisition
- `utils/spr_calibrator.py` — loads afterglow calibration and can set optimized live LED delay
- `led_afterglow_model.py` — measure τ per channel; recommend delays
- `analyze_width_vs_shift_model.py` — simulator and bias analysis

---

## 8) Appendix: quick commands (PowerShell)

```powershell
# Single-LED collector with physics-aware centroid preset
.\.venv312\Scripts\python.exe .\collect_training_data.py --device "demo P4SPR 2.0" --label used_current `
  --channels A --no-prompt --physics-aware-centroid

# Run width vs shift simulator on synthetic baseline
.\.venv312\Scripts\python.exe .\analyze_width_vs_shift_model.py --output-dir analysis_results\width_vs_shift_model
```
