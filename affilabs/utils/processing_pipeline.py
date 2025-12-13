"""Data Processing Pipeline Architecture.

Provides a flexible, pluggable architecture for SPR data processing pipelines.
Allows switching between different processing algorithms while maintaining
a consistent interface.

Architecture:
- Pipeline interface defines processing steps
- Concrete implementations provide different algorithms
- Pipeline registry manages available pipelines
- UI can switch between pipelines dynamically
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from affilabs.utils.logger import logger


@dataclass
class PipelineMetadata:
    """Metadata describing a processing pipeline."""

    name: str
    description: str
    version: str
    author: str
    parameters: dict[str, Any]  # Pipeline-specific configuration


@dataclass
class ProcessingResult:
    """Result from pipeline processing."""

    transmission: np.ndarray
    resonance_wavelength: float
    metadata: dict[str, Any]  # Additional pipeline-specific data
    success: bool = True
    error_message: str | None = None


class ProcessingPipeline(ABC):
    """Abstract base class for data processing pipelines."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize pipeline with optional configuration.

        Args:
            config: Pipeline-specific configuration parameters

        """
        self.config = config or {}
        self._metadata: PipelineMetadata | None = None

    @abstractmethod
    def get_metadata(self) -> PipelineMetadata:
        """Return pipeline metadata for UI display."""

    @abstractmethod
    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """Calculate transmission spectrum.

        Args:
            intensity: Measured intensity (after dark subtraction)
            reference: Reference spectrum

        Returns:
            Transmission spectrum

        """

    @abstractmethod
    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs,
    ) -> float:
        """Find resonance wavelength from transmission spectrum.

        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            **kwargs: Pipeline-specific parameters

        Returns:
            Resonance wavelength in nm, or np.nan if not found

        """

    def process(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs,
    ) -> ProcessingResult:
        """Complete processing pipeline: transmission + resonance finding.

        This is the main entry point for processing a spectrum.

        Args:
            intensity: Measured intensity spectrum
            reference: Reference spectrum
            wavelengths: Wavelength array
            **kwargs: Pipeline-specific parameters

        Returns:
            ProcessingResult with transmission and resonance wavelength

        """
        try:
            # Step 1: Calculate transmission
            transmission = self.calculate_transmission(intensity, reference)

            # Step 2: Find resonance wavelength
            resonance = self.find_resonance_wavelength(
                transmission,
                wavelengths,
                **kwargs,
            )

            # Collect metadata
            metadata = {
                "pipeline": self.get_metadata().name,
                "transmission_mean": float(np.nanmean(transmission)),
                "transmission_std": float(np.nanstd(transmission)),
            }

            return ProcessingResult(
                transmission=transmission,
                resonance_wavelength=resonance,
                metadata=metadata,
                success=True,
            )

        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            return ProcessingResult(
                transmission=np.zeros_like(intensity),
                resonance_wavelength=np.nan,
                metadata={},
                success=False,
                error_message=str(e),
            )


class PipelineRegistry:
    """Registry for managing available processing pipelines."""

    def __init__(self) -> None:
        self._pipelines: dict[str, type[ProcessingPipeline]] = {}
        self._active_pipeline: str | None = None
        self._instances: dict[str, ProcessingPipeline] = {}

    def register(
        self, pipeline_id: str, pipeline_class: type[ProcessingPipeline],
    ) -> None:
        """Register a pipeline class.

        Args:
            pipeline_id: Unique identifier for the pipeline
            pipeline_class: Pipeline class (not instance)

        """
        self._pipelines[pipeline_id] = pipeline_class
        logger.info(f"Registered pipeline: {pipeline_id}")

    def get_pipeline(
        self, pipeline_id: str, config: dict[str, Any] | None = None,
    ) -> ProcessingPipeline:
        """Get or create pipeline instance.

        Args:
            pipeline_id: Pipeline identifier
            config: Configuration for pipeline instance

        Returns:
            Pipeline instance

        """
        if pipeline_id not in self._pipelines:
            msg = f"Unknown pipeline: {pipeline_id}"
            raise ValueError(msg)

        # Create new instance if config is provided or instance doesn't exist
        if config or pipeline_id not in self._instances:
            self._instances[pipeline_id] = self._pipelines[pipeline_id](config)

        return self._instances[pipeline_id]

    def set_active_pipeline(
        self, pipeline_id: str, config: dict[str, Any] | None = None,
    ) -> None:
        """Set the active pipeline.

        Args:
            pipeline_id: Pipeline to activate
            config: Optional configuration

        """
        if pipeline_id not in self._pipelines:
            msg = f"Unknown pipeline: {pipeline_id}"
            raise ValueError(msg)

        self._active_pipeline = pipeline_id

        # Ensure instance exists with current config
        if config:
            self._instances[pipeline_id] = self._pipelines[pipeline_id](config)

        logger.info(f"Active pipeline: {pipeline_id}")

    def get_active_pipeline(self) -> ProcessingPipeline:
        """Get the currently active pipeline instance.

        Returns:
            Active pipeline instance

        """
        if not self._active_pipeline:
            msg = "No active pipeline set"
            raise RuntimeError(msg)

        return self.get_pipeline(self._active_pipeline)

    def list_pipelines(self) -> list[PipelineMetadata]:
        """List all registered pipelines with metadata.

        Returns:
            List of pipeline metadata

        """
        metadata_list = []
        for pipeline_id, pipeline_class in self._pipelines.items():
            try:
                # Create temporary instance to get metadata
                temp_instance = pipeline_class()
                metadata_list.append(temp_instance.get_metadata())
            except Exception as e:
                logger.error(f"Failed to get metadata for {pipeline_id}: {e}")

        return metadata_list

    @property
    def active_pipeline_id(self) -> str | None:
        """Get ID of currently active pipeline."""
        return self._active_pipeline


# Global registry instance
_global_registry = PipelineRegistry()


def get_pipeline_registry() -> PipelineRegistry:
    """Get the global pipeline registry."""
    return _global_registry
