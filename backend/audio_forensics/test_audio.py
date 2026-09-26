"""Development-time test script for the audio-forensics preprocessing pipeline.

This file is intentionally simple and readable. It is not part of the production
API, and it is used to manually inspect the audio pipeline while the subsystem is
being built.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from audio_preprocess import (
    compute_fft,
    extract_signal_features,
    preprocess_audio,
    segment_audio,
)


TEST_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "sample.wav")


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _assert_close(value, expected, tolerance=1e-6, label="value"):
    if not np.isclose(value, expected, atol=tolerance):
        raise AssertionError(f"{label} expected approximately {expected}, got {value}")


def validate_preprocessing(file_path: str = TEST_AUDIO_PATH) -> dict:
    """Load and validate a local audio file through the preprocessing pipeline."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Audio test file not found: '{file_path}'. Place a sample WAV file there to run this script."
        )

    print_section("Audio preprocessing")
    result = preprocess_audio(file_path)
    waveform = result["waveform"]
    sample_rate = result["sample_rate"]
    duration = result["duration"]
    num_samples = result["num_samples"]

    print(f"sample_rate: {sample_rate}")
    print(f"duration: {duration}")
    print(f"num_samples: {num_samples}")
    print(f"waveform shape: {waveform.shape}")
    print(f"waveform dtype: {waveform.dtype}")
    print(f"min amplitude: {np.min(waveform)}")
    print(f"max amplitude: {np.max(waveform)}")
    print(f"mean amplitude: {np.mean(waveform)}")

    assert result["sample_rate"] == 16000
    assert waveform.dtype == np.float32
    assert result["num_samples"] > 0
    assert result["duration"] > 0
    assert np.all(waveform >= -1.0)
    assert np.all(waveform <= 1.0)
    assert np.isclose(np.mean(waveform), 0.0, atol=1e-2)

    print("Preprocessing checks: passed")
    return result


def inspect_fft(waveform: np.ndarray, sample_rate: int) -> None:
    print_section("FFT analysis")
    frequencies, magnitude, power = compute_fft(waveform, sample_rate)

    print(f"FFT bins: {len(frequencies)}")
    print(f"dominant frequency: {frequencies[np.argmax(magnitude)]} Hz")
    print(f"total spectral power: {np.sum(power)}")

    assert len(frequencies) == len(magnitude) == len(power)
    assert len(frequencies) > 0
    assert np.isfinite(np.sum(power))

    print("FFT checks: passed")


def inspect_segmentation(waveform: np.ndarray, sample_rate: int) -> None:
    print_section("Segmentation")
    segments = segment_audio(waveform, sample_rate, window_seconds=4.0, hop_seconds=2.0)
    print(f"number of segments: {len(segments)}")

    if segments:
        for idx, segment in enumerate(segments[:5]):
            print(
                f"segment {idx}: start={segment['start_time']:.2f}s, "
                f"end={segment['end_time']:.2f}s, samples={len(segment['waveform'])}"
            )

    assert isinstance(segments, list)
    assert len(segments) > 0
    assert all("waveform" in seg for seg in segments)
    assert all("start_time" in seg for seg in segments)
    assert all("end_time" in seg for seg in segments)

    print("Segmentation checks: passed")


def inspect_feature_summary(waveform: np.ndarray, sample_rate: int) -> None:
    print_section("Signal feature summary")
    features = extract_signal_features(waveform, sample_rate)
    for key, value in features.items():
        print(f"{key}: {value}")

    assert set(features).issuperset(
        {
            "rms",
            "zero_crossing_rate",
            "crest_factor",
            "dominant_frequency",
            "spectral_centroid",
            "spectral_bandwidth",
            "spectral_rolloff",
            "spectral_flatness",
            "spectral_flux",
            "energy_0_500",
            "energy_500_2000",
            "energy_2000_4000",
            "energy_4000_8000",
        }
    )
    print("Feature summary checks: passed")


def main() -> None:
    """Run the manual preprocessing validation script."""
    result = validate_preprocessing(TEST_AUDIO_PATH)
    waveform = result["waveform"]
    sample_rate = result["sample_rate"]

    inspect_fft(waveform, sample_rate)
    inspect_segmentation(waveform, sample_rate)
    inspect_feature_summary(waveform, sample_rate)

    print_section("Status")
    print("Audio preprocessing pipeline checks completed successfully.")


if __name__ == "__main__":
    main()
