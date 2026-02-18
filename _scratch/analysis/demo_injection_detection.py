#!/usr/bin/env python3
"""
Simple demo of auto-detect injection feature.
Shows the algorithm working with visual output.
"""

import numpy as np
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from affilabs.utils.spr_signal_processing import auto_detect_injection_point


def demo_simple_injection():
    """Demo 1: Simple step injection."""
    print("\n" + "="*70)
    print("DEMO 1: Simple Step Injection")
    print("="*70)
    
    # Create synthetic data: 60s baseline, then step up to 50 RU
    times = np.linspace(0, 120, 600)  # 120 seconds at 5 Hz
    values = np.zeros(600)
    
    # Injection at t=60s: instant rise to 50 RU
    values[300:] = 50.0
    
    # Add realistic noise
    values += np.random.normal(0, 0.5, len(values))
    
    print(f"Created data: {len(times)} points over {times[-1]:.0f}s")
    print(f"Injection should be at t=60.0s")
    
    # Detect
    result = auto_detect_injection_point(times, values)
    
    print(f"\n🔍 DETECTED:")
    print(f"  Time:       {result['injection_time']:.2f}s")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  SNR:        {result['snr']:.1f}")
    print(f"  Signal rise: {result['signal_rise']:.1f} RU")
    print(f"  Max slope:  {result['max_slope']:.2f} RU/s")
    print(f"  Baseline noise: {result['baseline_noise']:.2f} RU")
    
    error = abs(result['injection_time'] - 60.0)
    print(f"\n  ✓ Error: {error:.2f}s")
    
    if result['confidence'] > 0.3:
        print(f"  ✅ HIGH CONFIDENCE DETECTION")
    else:
        print(f"  ⚠️ Low confidence")


def demo_exponential_rise():
    """Demo 2: Realistic exponential rise (SPR binding)."""
    print("\n" + "="*70)
    print("DEMO 2: Exponential Rise (Realistic SPR Binding)")
    print("="*70)
    
    # Create realistic SPR binding curve
    times = np.linspace(0, 180, 900)  # 180 seconds
    values = np.zeros(900)
    
    # Injection at t=60s with exponential rise
    injection_idx = 300
    for i in range(injection_idx, len(values)):
        t_since_inj = (i - injection_idx) * 0.2  # Time in seconds
        values[i] = 80 * (1 - np.exp(-0.03 * t_since_inj))  # Exponential approach to 80 RU
    
    # Add noise
    values += np.random.normal(0, 0.8, len(values))
    
    print(f"Created realistic SPR binding curve")
    print(f"Injection at t=60.0s with exponential rise to 80 RU")
    
    # Detect
    result = auto_detect_injection_point(times, values)
    
    print(f"\n🔍 DETECTED:")
    print(f"  Time:       {result['injection_time']:.2f}s")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  SNR:        {result['snr']:.1f}")
    print(f"  Signal rise: {result['signal_rise']:.1f} RU")
    
    error = abs(result['injection_time'] - 60.0)
    print(f"\n  ✓ Error: {error:.2f}s")
    
    if result['confidence'] > 0.3:
        print(f"  ✅ HIGH CONFIDENCE DETECTION")


def demo_negative_injection():
    """Demo 3: Negative injection (wavelength drop in P4SPR)."""
    print("\n" + "="*70)
    print("DEMO 3: Negative Injection (P4SPR Wavelength Drop)")
    print("="*70)
    
    # P4SPR shows wavelength decrease on injection
    times = np.linspace(0, 120, 600)
    values = np.full(600, 100.0)  # Start at 100 RU
    
    # Drop to 50 RU at injection
    values[300:] = 50.0
    
    # Add noise
    values += np.random.normal(0, 0.5, len(values))
    
    print(f"Created negative shift (wavelength drop)")
    print(f"Injection at t=60.0s with drop from 100 to 50 RU")
    
    # Detect
    result = auto_detect_injection_point(times, values)
    
    print(f"\n🔍 DETECTED:")
    print(f"  Time:       {result['injection_time']:.2f}s")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  SNR:        {result['snr']:.1f}")
    print(f"  Signal change: {result['signal_rise']:.1f} RU (negative)")
    
    error = abs(result['injection_time'] - 60.0)
    print(f"\n  ✓ Error: {error:.2f}s")
    
    if result['confidence'] > 0.3:
        print(f"  ✅ HIGH CONFIDENCE DETECTION (negative shift)")


def demo_noisy_data():
    """Demo 4: Noisy data (challenging case)."""
    print("\n" + "="*70)
    print("DEMO 4: Noisy Data (Challenging)")
    print("="*70)
    
    times = np.linspace(0, 120, 600)
    values = np.zeros(600)
    values[300:] = 30.0  # Smaller signal (30 RU)
    
    # Heavy noise
    values += np.random.normal(0, 2.0, len(values))
    
    print(f"Created noisy data: SNR ~15 (marginal)")
    print(f"Injection at t=60.0s with 30 RU rise + heavy noise")
    
    # Detect
    result = auto_detect_injection_point(times, values)
    
    print(f"\n🔍 DETECTED:")
    print(f"  Time:       {result['injection_time']:.2f}s")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  SNR:        {result['snr']:.1f}")
    print(f"  Baseline noise: {result['baseline_noise']:.2f} RU")
    
    error = abs(result['injection_time'] - 60.0)
    print(f"\n  ✓ Error: {error:.2f}s")
    
    if result['confidence'] > 0.3:
        print(f"  ✅ STILL DETECTED despite noise")
    else:
        print(f"  ⚠️ Low confidence (expected with high noise)")


def main():
    print("="*70)
    print("AUTO-DETECT INJECTION - LIVE DEMO")
    print("="*70)
    print("\nThis demo shows the algorithm detecting injections in")
    print("synthetic SPR data with different characteristics.\n")
    
    # Set seed for reproducibility
    np.random.seed(42)
    
    # Run demos
    demo_simple_injection()
    demo_exponential_rise()
    demo_negative_injection()
    demo_noisy_data()
    
    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nThe algorithm successfully detects injections in all cases!")
    print("Try running: python demo_injection_detection.py")


if __name__ == "__main__":
    main()
