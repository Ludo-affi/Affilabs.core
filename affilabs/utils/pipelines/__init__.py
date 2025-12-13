"""Pipeline initialization and registration

This module registers all available processing pipelines and provides
convenience functions for pipeline management.
"""

from affilabs.utils.processing_pipeline import get_pipeline_registry
from affilabs.utils.pipelines.fourier_pipeline import FourierPipeline
from affilabs.utils.pipelines.hybrid_original_pipeline import HybridOriginalPipeline  # First attempt - 8.82 RU (51% improvement)
from affilabs.utils.pipelines.hybrid_pipeline import HybridPipeline  # OPTIMIZED - 1.81 RU (90% improvement)
from affilabs.utils.logger import logger


def initialize_pipelines():
    """Register all available processing pipelines

    This should be called once at application startup.
    """
    from affilabs.settings import TRANSMISSION_BASELINE_METHOD, TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE

    registry = get_pipeline_registry()

    # Register pipeline classes in order
    registry.register('fourier', FourierPipeline)  # Position 1: Standard production (17.98 RU)
    registry.register('hybrid_original', HybridOriginalPipeline)  # Position 2: First attempt (8.82 RU)
    registry.register('hybrid', HybridPipeline)  # Position 3: OPTIMIZED (1.81 RU)

    # Set default pipeline with config
    fourier_config = {
        'baseline_method': TRANSMISSION_BASELINE_METHOD,
        'baseline_degree': TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE
    }
    registry.set_active_pipeline('fourier', config=fourier_config)

    logger.info(f"Initialized {len(registry.list_pipelines())} processing pipelines")
    logger.info(f"Active pipeline: {registry.active_pipeline_id}")
    if TRANSMISSION_BASELINE_METHOD != 'none':
        logger.info(f"  Baseline method: {TRANSMISSION_BASELINE_METHOD}")
