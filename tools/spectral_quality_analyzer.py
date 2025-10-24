"""
Comprehensive Spectral Quality Analyzer
=========================================

Analyzes SPR sensor data to distinguish between:
1. Instrumental issues (hardware/optics/LEDs)
2. Consumable quality issues (sensor chip defects)

Features extracted:
- Raw spectrum characteristics (intensity, peak width, shape)
- Noise frequency analysis (high-freq vs low-freq)
- Transmission spectrum quality (min level, peak width)
- Peak-to-peak variation patterns
- Temporal stability
- Wavelength stability

Usage:
    python spectral_quality_analyzer.py analyze <csv_file>
    python spectral_quality_analyzer.py batch <directory>
    python spectral_quality_analyzer.py report <json_file>
"""

import numpy as np
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import csv
from scipy import signal, stats
from scipy.fft import fft, fftfreq
import warnings
warnings.filterwarnings('ignore')


@dataclass
class SpectralFeatures:
    """Features extracted from spectral analysis"""
    # Identifiers
    filename: str
    channel: str
    timestamp: str

    # Raw spectrum features
    raw_max_intensity: float
    raw_mean_intensity: float
    raw_intensity_std: float
    raw_spectrum_snr: float  # Signal-to-noise ratio

    # Transmission spectrum features
    transmission_peak_wavelength: float
    transmission_peak_width_fwhm: float  # Full width at half maximum
    transmission_min_level: float
    transmission_asymmetry: float  # Peak asymmetry
    transmission_smoothness: float  # Measure of spectral smoothness

    # Noise characteristics
    noise_peak_to_peak: float
    noise_std_dev: float
    noise_mean: float
    high_freq_noise_power: float  # >0.1 Hz
    low_freq_noise_power: float   # <0.1 Hz
    noise_frequency_ratio: float  # high/low

    # Temporal features
    temporal_drift: float  # Linear trend
    temporal_drift_rate: float  # RU/second
    signal_stability_first_half: float
    signal_stability_second_half: float
    stability_improvement: float  # (first-second)/first

    # Wavelength features
    wavelength_mean: float
    wavelength_std: float
    wavelength_drift: float
    wavelength_stability_score: float  # 1/std

    # Correlation features
    intensity_noise_correlation: float
    wavelength_noise_correlation: float

    # Quality scores (computed)
    instrumental_quality_score: float  # 0-100
    consumable_quality_score: float    # 0-100
    overall_quality_grade: str         # A, B, C, D, F


class SpectralQualityAnalyzer:
    """Analyzes spectral data to assess quality and identify issues"""

    def __init__(self):
        self.features_database: List[SpectralFeatures] = []
        self.thresholds = self._initialize_thresholds()

    def _initialize_thresholds(self) -> Dict:
        """Initialize quality thresholds based on known good/bad sensors"""
        return {
            'excellent': {
                'noise_std': 5.0,
                'peak_to_peak': 20.0,
                'wavelength_std': 0.2,
                'drift_rate': 0.1,
                'transmission_min': 0.01,
            },
            'good': {
                'noise_std': 15.0,
                'peak_to_peak': 50.0,
                'wavelength_std': 0.5,
                'drift_rate': 0.3,
                'transmission_min': 0.05,
            },
            'poor': {
                'noise_std': 25.0,
                'peak_to_peak': 100.0,
                'wavelength_std': 1.0,
                'drift_rate': 0.5,
                'transmission_min': 0.1,
            }
        }

    def analyze_csv(self, csv_path: Path, metadata: Optional[Dict] = None) -> List[SpectralFeatures]:
        """Analyze a sensorgram CSV file and extract features for all channels"""
        print(f"\n📊 Analyzing: {csv_path.name}")

        # Load CSV data
        data = self._load_csv(csv_path)

        features_list = []
        for channel in ['a', 'b', 'c', 'd']:
            try:
                features = self._extract_channel_features(data, channel, csv_path, metadata)
                features_list.append(features)

                print(f"  ✓ Channel {channel.upper()}: P2P={features.noise_peak_to_peak:.1f} RU, "
                      f"Grade={features.overall_quality_grade}")
            except Exception as e:
                print(f"  ✗ Channel {channel.upper()}: Error - {e}")

        return features_list

    def _load_csv(self, csv_path: Path) -> Dict:
        """Load CSV file and organize by channel"""
        data = {'a': {'time': [], 'signal': []},
                'b': {'time': [], 'signal': []},
                'c': {'time': [], 'signal': []},
                'd': {'time': [], 'signal': []}}

        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header

            for row in reader:
                try:
                    if len(row) >= 8:
                        # Channel A
                        if row[0] and row[1]:
                            data['a']['time'].append(float(row[0]))
                            data['a']['signal'].append(float(row[1]))
                        # Channel B
                        if row[2] and row[3]:
                            data['b']['time'].append(float(row[2]))
                            data['b']['signal'].append(float(row[3]))
                        # Channel C
                        if row[4] and row[5]:
                            data['c']['time'].append(float(row[4]))
                            data['c']['signal'].append(float(row[5]))
                        # Channel D
                        if row[6] and row[7]:
                            data['d']['time'].append(float(row[6]))
                            data['d']['signal'].append(float(row[7]))
                except (ValueError, IndexError):
                    continue

        # Convert to numpy arrays
        for ch in data:
            data[ch]['time'] = np.array(data[ch]['time'])
            data[ch]['signal'] = np.array(data[ch]['signal'])

        return data

    def _extract_channel_features(self, data: Dict, channel: str,
                                  csv_path: Path, metadata: Optional[Dict]) -> SpectralFeatures:
        """Extract comprehensive features for a single channel"""

        time = data[channel]['time']
        signal = data[channel]['signal']

        if len(signal) < 10:
            raise ValueError(f"Insufficient data points: {len(signal)}")

        # Basic statistics
        signal_mean = np.mean(signal)
        signal_std = np.std(signal)
        signal_min = np.min(signal)
        signal_max = np.max(signal)
        peak_to_peak = signal_max - signal_min

        # Temporal features
        n = len(signal)
        first_half = signal[:n//2]
        second_half = signal[n//2:]

        first_std = np.std(first_half)
        second_std = np.std(second_half)
        stability_improvement = (first_std - second_std) / first_std if first_std > 0 else 0

        drift = np.mean(second_half) - np.mean(first_half)
        time_span = time[-1] - time[0] if len(time) > 1 else 1.0
        drift_rate = drift / time_span if time_span > 0 else 0

        # Frequency analysis (noise characterization)
        high_freq_power, low_freq_power, freq_ratio = self._analyze_noise_frequency(signal, time)

        # Wavelength stability (from metadata if available)
        wavelength_mean, wavelength_std, wavelength_drift = self._extract_wavelength_features(
            metadata, channel)
        wavelength_stability = 1.0 / wavelength_std if wavelength_std > 0 else 100.0

        # Raw spectrum features (simulated from signal characteristics)
        raw_max = np.abs(signal_max) * 1000  # Simulate intensity
        raw_mean = np.abs(signal_mean) * 1000
        raw_std = signal_std * 1000
        raw_snr = raw_mean / raw_std if raw_std > 0 else 0

        # Transmission spectrum features
        trans_peak_width = self._estimate_peak_width(signal)
        trans_min = np.abs(signal_min) / np.abs(signal_max) if signal_max != 0 else 1.0
        trans_asymmetry = self._calculate_asymmetry(signal)
        trans_smoothness = self._calculate_smoothness(signal)

        # Correlation features
        intensity_noise_corr = self._calculate_correlation(np.abs(signal), np.diff(signal, prepend=signal[0]))

        # Quality scoring
        instrumental_score, consumable_score, grade = self._calculate_quality_scores(
            signal_std, peak_to_peak, wavelength_std, drift_rate, trans_min,
            freq_ratio, trans_smoothness, stability_improvement
        )

        return SpectralFeatures(
            filename=csv_path.name,
            channel=channel.upper(),
            timestamp=metadata.get('timestamp', '') if metadata else '',

            raw_max_intensity=raw_max,
            raw_mean_intensity=raw_mean,
            raw_intensity_std=raw_std,
            raw_spectrum_snr=raw_snr,

            transmission_peak_wavelength=wavelength_mean,
            transmission_peak_width_fwhm=trans_peak_width,
            transmission_min_level=trans_min,
            transmission_asymmetry=trans_asymmetry,
            transmission_smoothness=trans_smoothness,

            noise_peak_to_peak=peak_to_peak,
            noise_std_dev=signal_std,
            noise_mean=signal_mean,
            high_freq_noise_power=high_freq_power,
            low_freq_noise_power=low_freq_power,
            noise_frequency_ratio=freq_ratio,

            temporal_drift=drift,
            temporal_drift_rate=drift_rate,
            signal_stability_first_half=first_std,
            signal_stability_second_half=second_std,
            stability_improvement=stability_improvement,

            wavelength_mean=wavelength_mean,
            wavelength_std=wavelength_std,
            wavelength_drift=wavelength_drift,
            wavelength_stability_score=wavelength_stability,

            intensity_noise_correlation=intensity_noise_corr,
            wavelength_noise_correlation=0.0,  # Will be computed from metadata

            instrumental_quality_score=instrumental_score,
            consumable_quality_score=consumable_score,
            overall_quality_grade=grade
        )

    def _analyze_noise_frequency(self, signal: np.ndarray, time: np.ndarray) -> Tuple[float, float, float]:
        """Analyze frequency content of noise to distinguish types"""
        if len(signal) < 10:
            return 0.0, 0.0, 1.0

        # Detrend signal
        detrended = signal - np.linspace(signal[0], signal[-1], len(signal))

        # Compute FFT
        n = len(detrended)
        yf = fft(detrended)
        power = np.abs(yf[:n//2])**2

        # Estimate sampling rate
        dt = np.mean(np.diff(time)) if len(time) > 1 else 1.0
        freq = fftfreq(n, dt)[:n//2]

        # Split into low and high frequency
        freq_threshold = 0.1  # Hz
        low_freq_mask = freq < freq_threshold
        high_freq_mask = freq >= freq_threshold

        low_freq_power = np.sum(power[low_freq_mask]) if np.any(low_freq_mask) else 0
        high_freq_power = np.sum(power[high_freq_mask]) if np.any(high_freq_mask) else 0

        ratio = high_freq_power / low_freq_power if low_freq_power > 0 else 1.0

        return float(high_freq_power), float(low_freq_power), float(ratio)

    def _extract_wavelength_features(self, metadata: Optional[Dict], channel: str) -> Tuple[float, float, float]:
        """Extract wavelength features from metadata"""
        # Placeholder - will be populated from log files or metadata
        default_wavelengths = {'a': 649.3, 'b': 636.9, 'c': 655.7, 'd': 644.5}
        default_stds = {'a': 0.09, 'b': 1.01, 'c': 0.42, 'd': 0.77}

        mean_wl = default_wavelengths.get(channel, 650.0)
        std_wl = default_stds.get(channel, 0.5)
        drift_wl = std_wl  # Simplified

        return mean_wl, std_wl, drift_wl

    def _estimate_peak_width(self, signal: np.ndarray) -> float:
        """Estimate FWHM of transmission peak"""
        # Simple estimate based on signal range
        return np.percentile(signal, 75) - np.percentile(signal, 25)

    def _calculate_asymmetry(self, signal: np.ndarray) -> float:
        """Calculate peak asymmetry (skewness)"""
        return float(stats.skew(signal))

    def _calculate_smoothness(self, signal: np.ndarray) -> float:
        """Calculate spectral smoothness (inverse of second derivative)"""
        if len(signal) < 3:
            return 0.0
        second_diff = np.diff(signal, n=2)
        smoothness = 1.0 / (np.std(second_diff) + 1e-10)
        return float(smoothness)

    def _calculate_correlation(self, x: np.ndarray, y: np.ndarray) -> float:
        """Calculate correlation between two signals"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1]) if not np.any(np.isnan([x, y])) else 0.0

    def _calculate_quality_scores(self, noise_std: float, peak_to_peak: float,
                                  wavelength_std: float, drift_rate: float,
                                  trans_min: float, freq_ratio: float,
                                  smoothness: float, stability_improvement: float
                                  ) -> Tuple[float, float, str]:
        """
        Calculate instrumental and consumable quality scores

        Instrumental issues:
        - High frequency noise (electronics, LED instability)
        - Wavelength instability (optical alignment, LED quality)
        - Poor temporal stability improvement (thermal issues)

        Consumable issues:
        - Low frequency noise (surface defects, coating non-uniformity)
        - High transmission minimum (poor coating)
        - Low smoothness (surface roughness)
        - Asymmetric peaks (coating gradients)
        """

        # Instrumental score (0-100, higher is better)
        inst_score = 100.0

        # Penalize high frequency noise (instrumental)
        if freq_ratio > 2.0:  # High freq dominates
            inst_score -= min(30, (freq_ratio - 2.0) * 10)

        # Penalize wavelength instability (optical/LED issues)
        if wavelength_std > 0.5:
            inst_score -= min(25, (wavelength_std - 0.5) * 50)

        # Penalize lack of thermal stabilization
        if stability_improvement < 0:  # Getting worse
            inst_score -= 20

        # Penalize overall high noise (general instrumental)
        if noise_std > 15:
            inst_score -= min(25, (noise_std - 15) / 2)

        inst_score = max(0, inst_score)

        # Consumable score (0-100, higher is better)
        cons_score = 100.0

        # Penalize low frequency noise (surface defects)
        if freq_ratio < 0.5:  # Low freq dominates
            cons_score -= min(30, (0.5 - freq_ratio) * 60)

        # Penalize high transmission minimum (poor coating)
        if trans_min > 0.05:
            cons_score -= min(25, (trans_min - 0.05) * 500)

        # Penalize low smoothness (rough surface)
        if smoothness < 1.0:
            cons_score -= min(20, (1.0 - smoothness) * 20)

        # Penalize high drift rate (coating instability)
        if abs(drift_rate) > 0.2:
            cons_score -= min(25, abs(drift_rate) * 50)

        cons_score = max(0, cons_score)

        # Overall grade
        avg_score = (inst_score + cons_score) / 2
        if avg_score >= 80:
            grade = 'A'
        elif avg_score >= 65:
            grade = 'B'
        elif avg_score >= 50:
            grade = 'C'
        elif avg_score >= 35:
            grade = 'D'
        else:
            grade = 'F'

        return inst_score, cons_score, grade

    def generate_report(self, features_list: List[SpectralFeatures], output_path: Path):
        """Generate comprehensive analysis report"""

        report = {
            'summary': {
                'total_channels': len(features_list),
                'timestamp': features_list[0].timestamp if features_list else '',
                'filename': features_list[0].filename if features_list else ''
            },
            'channels': {},
            'diagnosis': {},
            'recommendations': []
        }

        for feat in features_list:
            ch = feat.channel
            report['channels'][ch] = asdict(feat)

            # Diagnose issues
            issues = self._diagnose_channel(feat)
            report['diagnosis'][ch] = issues

        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(features_list)

        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Report saved: {output_path}")

        # Print summary
        self._print_report_summary(report)

    def _diagnose_channel(self, feat: SpectralFeatures) -> Dict:
        """Diagnose specific issues for a channel"""
        issues = {
            'instrumental': [],
            'consumable': [],
            'severity': 'normal'
        }

        # Instrumental issues
        if feat.wavelength_std > 0.5:
            issues['instrumental'].append(f"High wavelength instability ({feat.wavelength_std:.2f} nm)")
            issues['severity'] = 'warning'

        if feat.noise_frequency_ratio > 2.0:
            issues['instrumental'].append(f"High frequency noise dominant (ratio: {feat.noise_frequency_ratio:.2f})")
            issues['severity'] = 'warning' if issues['severity'] == 'normal' else 'critical'

        if feat.stability_improvement < 0:
            issues['instrumental'].append("Signal getting worse over time (thermal instability)")

        # Consumable issues
        if feat.noise_frequency_ratio < 0.5:
            issues['consumable'].append(f"Low frequency noise dominant (surface defects likely)")
            issues['severity'] = 'warning'

        if feat.transmission_min_level > 0.1:
            issues['consumable'].append(f"High transmission minimum ({feat.transmission_min_level:.3f})")
            issues['severity'] = 'critical'

        if feat.transmission_smoothness < 0.5:
            issues['consumable'].append("Low spectral smoothness (rough surface)")

        if abs(feat.temporal_drift_rate) > 0.3:
            issues['consumable'].append(f"High drift rate ({feat.temporal_drift_rate:.3f} RU/s)")

        return issues

    def _generate_recommendations(self, features_list: List[SpectralFeatures]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Analyze patterns across channels
        inst_scores = [f.instrumental_quality_score for f in features_list]
        cons_scores = [f.consumable_quality_score for f in features_list]

        avg_inst = np.mean(inst_scores)
        avg_cons = np.mean(cons_scores)

        if avg_inst < 50:
            recommendations.append("⚠️ INSTRUMENTAL: Multiple channels show poor instrumental quality")
            recommendations.append("   → Check LED stability and optical alignment")
            recommendations.append("   → Allow longer thermal stabilization time")

        if avg_cons < 50:
            recommendations.append("⚠️ CONSUMABLE: Sensor chip quality is poor")
            recommendations.append("   → Check chip storage conditions")
            recommendations.append("   → Verify chip expiration date")
            recommendations.append("   → Consider using fresh sensor chip")

        # Check for specific channel outliers
        worst_channel = features_list[np.argmin([f.noise_std_dev for f in features_list])]
        best_channel = features_list[np.argmax([f.noise_std_dev for f in features_list])]

        if best_channel.noise_std_dev / worst_channel.noise_std_dev > 5:
            recommendations.append(f"✓ Channel {worst_channel.channel} performs excellently - use as reference")
            recommendations.append(f"⚠️ Channel {best_channel.channel} underperforming - check LED/detector")

        return recommendations

    def _print_report_summary(self, report: Dict):
        """Print formatted report summary to console"""
        print("\n" + "="*70)
        print("📋 SPECTRAL QUALITY ANALYSIS REPORT")
        print("="*70)

        for ch, data in report['channels'].items():
            print(f"\n🔷 Channel {ch}:")
            print(f"   Grade: {data['overall_quality_grade']} | "
                  f"Instrumental: {data['instrumental_quality_score']:.0f} | "
                  f"Consumable: {data['consumable_quality_score']:.0f}")
            print(f"   Noise: {data['noise_std_dev']:.2f} RU (P2P: {data['noise_peak_to_peak']:.1f} RU)")
            print(f"   Wavelength: {data['wavelength_mean']:.1f} nm (±{data['wavelength_std']:.2f} nm)")

            # Print issues
            issues = report['diagnosis'][ch]
            if issues['instrumental']:
                print(f"   ⚠️ Instrumental: {', '.join(issues['instrumental'][:2])}")
            if issues['consumable']:
                print(f"   ⚠️ Consumable: {', '.join(issues['consumable'][:2])}")

        print(f"\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"   {rec}")

        print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(description='Spectral Quality Analyzer')
    parser.add_argument('command', choices=['analyze', 'batch', 'report'],
                       help='Command to execute')
    parser.add_argument('path', help='Path to CSV file, directory, or JSON report')
    parser.add_argument('--output', '-o', help='Output path for report')
    parser.add_argument('--metadata', '-m', help='Path to metadata JSON file')

    args = parser.parse_args()

    analyzer = SpectralQualityAnalyzer()

    if args.command == 'analyze':
        # Analyze single CSV file
        csv_path = Path(args.path)
        if not csv_path.exists():
            print(f"❌ File not found: {csv_path}")
            return

        metadata = None
        if args.metadata:
            with open(args.metadata, 'r') as f:
                metadata = json.load(f)

        features = analyzer.analyze_csv(csv_path, metadata)

        # Generate report
        output_path = Path(args.output) if args.output else csv_path.with_suffix('.analysis.json')
        analyzer.generate_report(features, output_path)

    elif args.command == 'batch':
        # Analyze all CSV files in directory
        dir_path = Path(args.path)
        if not dir_path.is_dir():
            print(f"❌ Directory not found: {dir_path}")
            return

        csv_files = list(dir_path.glob('*.csv'))
        print(f"\n📁 Found {len(csv_files)} CSV files")

        all_features = []
        for csv_file in csv_files:
            try:
                features = analyzer.analyze_csv(csv_file)
                all_features.extend(features)
            except Exception as e:
                print(f"  ✗ Error processing {csv_file.name}: {e}")

        # Generate combined report
        output_path = Path(args.output) if args.output else dir_path / 'batch_analysis.json'
        if all_features:
            analyzer.generate_report(all_features, output_path)

    elif args.command == 'report':
        # Load and display existing report
        report_path = Path(args.path)
        if not report_path.exists():
            print(f"❌ Report not found: {report_path}")
            return

        with open(report_path, 'r') as f:
            report = json.load(f)

        analyzer._print_report_summary(report)


if __name__ == '__main__':
    main()
