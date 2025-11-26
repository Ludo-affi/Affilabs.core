"""Demo Data Generator for Promotional UI Images

Generates realistic SPR binding curves for demonstration purposes.
Simulates typical kinetics with:
- Baseline stabilization
- Association phase (analyte binding)
- Dissociation phase (analyte washout)
- Realistic noise characteristics

Author: AI Assistant
Date: November 24, 2025
"""

import numpy as np
from typing import Dict, Tuple, Optional


def generate_demo_spr_data(
    duration_seconds: float = 600,
    sampling_rate: float = 2.0,
    num_channels: int = 4,
    baseline_ru: float = 0.0,
    max_response_ru: Dict[str, float] = None,
    association_start: float = 120,
    association_duration: float = 240,
    dissociation_start: float = 360,
    ka: float = 1e5,  # Association rate constant (M^-1 s^-1)
    kd: float = 1e-3,  # Dissociation rate constant (s^-1)
    noise_level: float = 0.5,  # RU noise level
    seed: Optional[int] = 42,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Generate realistic SPR binding curves for demo purposes.

    Args:
        duration_seconds: Total recording duration (s)
        sampling_rate: Data points per second (Hz)
        num_channels: Number of channels to generate (1-4)
        baseline_ru: Starting baseline value (RU)
        max_response_ru: Dict of max response for each channel {'a': 50, 'b': 45, ...}
        association_start: When analyte injection starts (s)
        association_duration: How long analyte flows (s)
        dissociation_start: When dissociation/washout starts (s)
        ka: Association rate constant
        kd: Dissociation rate constant
        noise_level: Standard deviation of noise (RU)
        seed: Random seed for reproducibility

    Returns:
        time_array: Time points (seconds)
        channel_data: Dict with keys 'a', 'b', 'c', 'd' containing RU values
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate time array
    num_points = int(duration_seconds * sampling_rate)
    time_array = np.linspace(0, duration_seconds, num_points)

    # Default max responses if not provided
    if max_response_ru is None:
        max_response_ru = {
            'a': 55.0,
            'b': 48.0,
            'c': 52.0,
            'd': 45.0,
        }

    channel_names = ['a', 'b', 'c', 'd'][:num_channels]
    channel_data = {}

    for ch in channel_names:
        # Initialize baseline with slight drift
        baseline_drift = np.linspace(0, 0.5, num_points)  # Slight upward drift
        signal = baseline_ru + baseline_drift

        # Get max response for this channel
        rmax = max_response_ru.get(ch, 50.0)

        # Association phase (binding)
        association_mask = (time_array >= association_start) & (time_array < dissociation_start)
        t_assoc = time_array[association_mask] - association_start

        # Langmuir binding model for association
        # R = Rmax * (1 - exp(-kobs*t)) where kobs = ka*C + kd
        # For demo, assume constant analyte concentration
        C = 10e-9  # 10 nM analyte concentration
        kobs = ka * C + kd

        association_response = rmax * (1 - np.exp(-kobs * t_assoc))
        signal[association_mask] += association_response

        # Dissociation phase (washout)
        dissociation_mask = time_array >= dissociation_start
        t_dissoc = time_array[dissociation_mask] - dissociation_start

        # At dissociation start, we have the steady-state response
        steady_state = rmax * (1 - np.exp(-kobs * (dissociation_start - association_start)))

        # Exponential decay: R = R0 * exp(-kd*t)
        dissociation_response = steady_state * np.exp(-kd * t_dissoc)
        signal[dissociation_mask] += dissociation_response

        # Add realistic noise
        noise = np.random.normal(0, noise_level, num_points)

        # Add low-frequency noise (drift)
        low_freq_noise = 0.2 * np.sin(2 * np.pi * 0.01 * time_array)

        # Combine all components
        final_signal = signal + noise + low_freq_noise

        channel_data[ch] = final_signal

    return time_array, channel_data


def generate_demo_cycle_data(
    num_cycles: int = 5,
    cycle_duration: float = 600,
    sampling_rate: float = 2.0,
    responses: Optional[list] = None,
    seed: Optional[int] = 42,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], list]:
    """Generate multi-cycle demo data with varying responses.

    Args:
        num_cycles: Number of injection cycles
        cycle_duration: Duration of each cycle (s)
        sampling_rate: Data points per second
        responses: List of max responses for each cycle (RU)
        seed: Random seed

    Returns:
        time_array: Full time array
        channel_data: Channel data dict
        cycle_boundaries: List of (start_time, end_time) for each cycle
    """
    if responses is None:
        # Default: increasing concentration series
        responses = [10, 25, 40, 55, 70][:num_cycles]

    total_duration = num_cycles * cycle_duration
    total_points = int(total_duration * sampling_rate)
    time_array = np.linspace(0, total_duration, total_points)

    # Initialize channel data
    channel_data = {ch: np.zeros(total_points) for ch in ['a', 'b', 'c', 'd']}
    cycle_boundaries = []

    for cycle_idx in range(num_cycles):
        cycle_start_time = cycle_idx * cycle_duration
        cycle_end_time = (cycle_idx + 1) * cycle_duration
        cycle_boundaries.append((cycle_start_time, cycle_end_time))

        # Generate data for this cycle
        max_responses = {
            'a': responses[cycle_idx] * 1.0,
            'b': responses[cycle_idx] * 0.87,
            'c': responses[cycle_idx] * 0.95,
            'd': responses[cycle_idx] * 0.82,
        }

        cycle_time, cycle_data = generate_demo_spr_data(
            duration_seconds=cycle_duration,
            sampling_rate=sampling_rate,
            max_response_ru=max_responses,
            association_start=60,
            association_duration=240,
            dissociation_start=300,
            seed=seed + cycle_idx if seed else None,
        )

        # Insert into full array
        start_idx = int(cycle_idx * cycle_duration * sampling_rate)
        end_idx = int((cycle_idx + 1) * cycle_duration * sampling_rate)

        for ch in ['a', 'b', 'c', 'd']:
            channel_data[ch][start_idx:end_idx] = cycle_data[ch]

    return time_array, channel_data, cycle_boundaries


def load_demo_data_into_ui(ui_instance, num_cycles: int = 3):
    """Load demo data into the UI for promotional screenshots.

    Args:
        ui_instance: The main UI instance (AffilabsCoreUI)
        num_cycles: Number of cycles to generate
    """
    # Generate demo data
    time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
        num_cycles=num_cycles,
        cycle_duration=600,
        sampling_rate=2.0,
        responses=[15, 35, 55] if num_cycles == 3 else None,
    )

    # Inject data into UI buffers
    try:
        # Update time buffer
        if hasattr(ui_instance, 'time_buffer'):
            ui_instance.time_buffer = list(time_array)

        # Update channel buffers
        for ch in ['a', 'b', 'c', 'd']:
            buffer_name = f'wavelength_buffer_{ch}'
            if hasattr(ui_instance, buffer_name):
                setattr(ui_instance, buffer_name, list(channel_data[ch]))

        # Set cycle boundaries for region markers
        if hasattr(ui_instance, '_cycle_regions'):
            ui_instance._cycle_regions = cycle_boundaries

        # Update graphs
        if hasattr(ui_instance, '_update_plots'):
            ui_instance._update_plots()

        print(f"✅ Demo data loaded: {len(time_array)} points, {num_cycles} cycles")
        return True

    except Exception as e:
        print(f"❌ Error loading demo data: {e}")
        return False


if __name__ == "__main__":
    # Test generation
    import matplotlib.pyplot as plt

    time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
        num_cycles=3,
        responses=[20, 40, 60]
    )

    plt.figure(figsize=(12, 6))
    colors = {'a': 'red', 'b': 'green', 'c': 'blue', 'd': 'orange'}

    for ch, data in channel_data.items():
        plt.plot(time_array, data, label=f'Channel {ch.upper()}', color=colors[ch], alpha=0.8)

    # Mark cycle boundaries
    for start, end in cycle_boundaries:
        plt.axvline(start, color='gray', linestyle='--', alpha=0.3)
        plt.axvline(end, color='gray', linestyle='--', alpha=0.3)

    plt.xlabel('Time (s)')
    plt.ylabel('Response (RU)')
    plt.title('Demo SPR Kinetics Data')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    print(f"Generated {len(time_array)} data points across {len(cycle_boundaries)} cycles")
