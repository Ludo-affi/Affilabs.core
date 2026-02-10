"""Pipeline initialization and registration

This module registers all available processing pipelines and provides
convenience functions for pipeline management.
"""

from affilabs.utils.logger import logger
from affilabs.utils.pipelines.fourier_pipeline import FourierPipeline
from affilabs.utils.processing_pipeline import get_pipeline_registry


def initialize_pipelines():
    """Register all available processing pipelines

    This should be called once at application startup.
    """
    import json
    from pathlib import Path

    from affilabs.settings import (
        TRANSMISSION_BASELINE_METHOD,
        TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE,
    )

    registry = get_pipeline_registry()

    # Register only Fourier pipeline
    registry.register(
        "fourier",
        FourierPipeline,
    )

    # Load saved pipeline preference or default to fourier
    from affilabs.utils.resource_path import get_resource_path

    config_file = get_resource_path("settings/pipeline_config.json")
    saved_pipeline = "fourier"  # Default

    try:
        if config_file.exists():
            with open(config_file) as f:
                config_data = json.load(f)
                saved_pipeline = config_data.get("active_pipeline", "fourier")
                logger.info(f"Loaded saved pipeline preference: {saved_pipeline}")
    except Exception as e:
        logger.warning(f"Could not load pipeline config, using default: {e}")

    # Set pipeline with config
    pipeline_config = {
        "baseline_method": TRANSMISSION_BASELINE_METHOD,
        "baseline_degree": TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE,
    }
    registry.set_active_pipeline(saved_pipeline, config=pipeline_config)

    logger.debug(f"Initialized {len(registry.list_pipelines())} processing pipelines")
    logger.debug(f"Active pipeline: {registry.active_pipeline_id}")
    if TRANSMISSION_BASELINE_METHOD != "none":
        logger.debug(f"  Baseline method: {TRANSMISSION_BASELINE_METHOD}")
