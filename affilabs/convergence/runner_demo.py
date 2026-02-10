from __future__ import annotations

import logging
from .config import ConvergenceRecipe, DetectorParams
from .engine import ConvergenceEngine
from .scheduler import ThreadScheduler
from .simulators import LinearSpectrometerSim, SimpleROISum


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("conv-demo")

    # Simulated device
    spect = LinearSpectrometerSim(
        base_per_led={"a": 850.0, "b": 820.0, "c": 840.0, "d": 780.0},
        noise_sigma=0.5,
        params_max_counts=65535.0,
        saturation_threshold=63000.0,
    )
    roi = SimpleROISum()

    engine = ConvergenceEngine(spectrometer=spect, roi_extractor=roi, scheduler=ThreadScheduler(1), logger=logger)

    # Config
    recipe = ConvergenceRecipe(
        channels=["a", "b", "c", "d"],
        initial_leds={"a": 65, "b": 68, "c": 66, "d": 74},
        initial_integration_ms=10.0,
        target_percent=0.90,
        tolerance_percent=0.05,
        near_window_percent=0.10,
        max_iterations=12,
        prefer_est_after_iters=1,
        max_led_change=50,
        led_small_step=5,
        boundary_margin=5,
        near_boundary_scale=0.5,
        measurement_timeout_s=2.0,
        parallel_workers=1,
        use_batch_command=True,
        min_signal_for_model=0.2,
        accept_above_extra_percent=0.0,
    )

    params = DetectorParams(
        max_counts=65535.0,
        saturation_threshold=63000.0,
        min_integration_time=3.0,
        max_integration_time=100.0,
    )

    result = engine.run(
        recipe=recipe,
        params=params,
        wave_min_index=400,
        wave_max_index=500,
        model_slopes_at_10ms={"a": 855.0, "b": 819.0, "c": 839.0, "d": 749.0},
    )

    logger.info("")
    logger.info(f"Done: converged={result.converged}, itime={result.integration_ms:.1f}ms, leds={result.final_leds}")


if __name__ == "__main__":
    main()
