"""Pipeline initialization and registration

This module registers all available processing pipelines and provides
convenience functions for pipeline management.
"""

from utils.processing_pipeline import get_pipeline_registry
from utils.pipelines.fourier_pipeline import FourierPipeline
from utils.pipelines.centroid_pipeline import CentroidPipeline
from utils.pipelines.polynomial_pipeline import PolynomialPipeline
from utils.pipelines.adaptive_multifeature_pipeline import AdaptiveMultiFeaturePipeline
from utils.pipelines.consensus_pipeline import ConsensusPipeline
from utils.logger import logger


def initialize_pipelines():
    """Register all available processing pipelines

    This should be called once at application startup.
    """
    from settings import TRANSMISSION_BASELINE_CORRECTION, TRANSMISSION_BASELINE_DEGREE
    
    registry = get_pipeline_registry()

    # Register pipeline classes
    registry.register('fourier', FourierPipeline)
    registry.register('centroid', CentroidPipeline)
    registry.register('polynomial', PolynomialPipeline)
    registry.register('adaptive', AdaptiveMultiFeaturePipeline)
    registry.register('consensus', ConsensusPipeline)

    # Set default pipeline with config
    fourier_config = {
        'baseline_correction': TRANSMISSION_BASELINE_CORRECTION,
        'baseline_degree': TRANSMISSION_BASELINE_DEGREE
    }
    registry.set_active_pipeline('fourier', config=fourier_config)

    logger.info(f"Initialized {len(registry.list_pipelines())} processing pipelines")
    logger.info(f"Active pipeline: {registry.active_pipeline_id}")
    if TRANSMISSION_BASELINE_CORRECTION:
        logger.info(f"  Baseline correction: ENABLED (degree={TRANSMISSION_BASELINE_DEGREE})")


# Initialize on import
initialize_pipelines()
