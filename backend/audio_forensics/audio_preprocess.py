"""Low-level audio preprocessing and signal-feature extraction for Argus.

This module is responsible for loading, standardizing, segmenting, and
measuring audio signals. It does not decide whether audio is synthetic or real.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import librosa
import numpy as np
import soundfile as sf

TARGET_SAMPLE_RATE = 16000
MAX_DURATION_SECONDS = 600

__all__ = [
    "TARGET_SAMPLE_RATE",
    "MAX_DURATION_SECONDS",
    "load_audio",
    "normalize_audio",
    "preprocess_audio",
    "segment_audio",
    "compute_rms",
    "zero_crossing_rate",
    "crest_factor",
    "compute_fft",
    "compute_spectrogram",
    "compute_log_mel_spectrogram",
    "compute_mfcc_features",
    "spectral_centroid",
    "spectral_bandwidth",
    "spectral_rolloff",
    "spectral_flatness",
    "spectral_flux",
    "dominant_frequency",
    "compute_frequency_band_energy",
    "extract_signal_features",
    "extract_forensic_features",
]


def _as_1d_float32(waveform: Any) -> np.ndarray:
    """Convert waveform-like input into a 1D float32 NumPy array."""
    signal = np.asarray(waveform, dtype=np.float32)
    if signal.ndim == 0:
        return signal.reshape(1).astype(np.float32)
    if signal.ndim > 1:
        signal = np.mean(signal, axis=-1)
    return np.asarray(signal, dtype=np.float32).reshape(-1)


def load_audio(file_path: str):
    """Decode common audio formats to mono 16 kHz, with a bounded FFmpeg fallback."""
    if file_path is None or not os.path.isfile(file_path):
        raise FileNotFoundError("Audio file not found.")

    def read_bounded(path):
        with sf.SoundFile(path) as audio:
            if audio.samplerate <= 0 or audio.channels > 32:
                raise ValueError("Unsupported audio stream.")
            if len(audio) > MAX_DURATION_SECONDS * audio.samplerate:
                raise ValueError(f"Audio must be {MAX_DURATION_SECONDS // 60} minutes or shorter.")
            return audio.read(dtype="float32", always_2d=True), audio.samplerate

    try:
        waveform, sample_rate = read_bounded(file_path)
    except (sf.LibsndfileError, sf.SoundFileRuntimeError):
        import imageio_ffmpeg

        with tempfile.TemporaryDirectory(prefix="argus_decode_") as folder:
            decoded_path = Path(folder) / "decoded.wav"
            try:
                completed = subprocess.run(
                    [
                        imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error",
                        "-protocol_whitelist", "file,pipe", "-i", str(Path(file_path).resolve()),
                        "-map", "0:a:0", "-vn", "-t", str(MAX_DURATION_SECONDS + 1),
                        "-ac", "1", "-ar", str(TARGET_SAMPLE_RATE),
                        "-c:a", "pcm_f32le", "-y", str(decoded_path),
                    ],
                    capture_output=True, timeout=90, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Audio decoding timed out.") from exc
            if completed.returncode:
                raise ValueError("Could not decode this file. Upload a valid audio recording.")
            waveform, sample_rate = read_bounded(decoded_path)

    if waveform.size == 0 or not np.all(np.isfinite(waveform)):
        raise ValueError("Audio is empty or contains invalid samples.")
    waveform = np.mean(waveform, axis=1)
    if sample_rate != TARGET_SAMPLE_RATE:
        waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=TARGET_SAMPLE_RATE)
    return waveform.astype(np.float32), float(TARGET_SAMPLE_RATE)


def normalize_audio(waveform: Any) -> np.ndarray:
    """Remove DC offset and peak-normalize the waveform safely."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0:
        return signal.copy()

    signal = signal - np.mean(signal)
    peak = float(np.max(np.abs(signal)))
    if peak > 0.0:
        signal = signal / peak
    return signal.astype(np.float32)


def preprocess_audio(file_path: str) -> Dict[str, Any]:
    """Load and standardize audio, then return the basic waveform metadata."""
    waveform, sample_rate = load_audio(file_path)
    if waveform.size < int(0.1 * sample_rate):
        raise ValueError("Audio must contain at least 0.1 seconds of sound.")
    if float(np.std(waveform)) < 1e-7:
        raise ValueError("Audio contains no measurable sound.")
    waveform = normalize_audio(waveform)
    duration = float(len(waveform)) / float(sample_rate)

    return {
        "waveform": waveform.astype(np.float32),
        "sample_rate": int(sample_rate),
        "duration": duration,
        "num_samples": int(len(waveform)),
    }


def segment_audio(
    waveform: Any,
    sample_rate: float,
    window_seconds: float = 4.0,
    hop_seconds: float = 2.0,
) -> List[Dict[str, Any]]:
    """Split a waveform into overlapping analysis windows."""
    signal = _as_1d_float32(waveform)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")
    if signal.size == 0:
        return []

    if not np.isfinite(window_seconds) or not np.isfinite(hop_seconds) or min(window_seconds, hop_seconds) <= 0:
        raise ValueError("Window and hop durations must be positive and finite.")
    window_samples = max(1, int(round(window_seconds * sample_rate)))
    hop_samples = max(1, int(round(hop_seconds * sample_rate)))

    segments: List[Dict[str, Any]] = []
    start_index = 0

    while start_index < signal.size:
        end_index = min(start_index + window_samples, signal.size)
        segment = signal[start_index:end_index]
        segments.append(
            {
                "waveform": segment.astype(np.float32),
                "start_time": float(start_index) / float(sample_rate),
                "end_time": float(end_index) / float(sample_rate),
            }
        )

        if end_index >= signal.size:
            break
        start_index += hop_samples

    return segments


def compute_rms(waveform: Any) -> float:
    """Compute the RMS energy of a waveform."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(signal))))


def zero_crossing_rate(waveform: Any) -> float:
    """Measure how often the signal changes sign."""
    signal = _as_1d_float32(waveform)
    if signal.size < 2:
        return 0.0

    signs = np.signbit(signal)
    crossings = np.count_nonzero(signs[:-1] != signs[1:])
    return float(crossings / max(signal.size - 1, 1))


def crest_factor(waveform: Any) -> float:
    """Compute peak amplitude divided by RMS amplitude."""
    signal = _as_1d_float32(waveform)
    rms = compute_rms(signal)
    if rms <= 1e-12 or signal.size == 0:
        return 0.0
    peak = float(np.max(np.abs(signal)))
    return float(peak / rms)


def compute_fft(waveform: Any, sample_rate: float):
    """Return FFT frequencies, magnitude spectrum, and power spectrum."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32), np.array([], dtype=np.float32)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")

    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate)
    magnitude = np.abs(spectrum).astype(np.float32)
    power = (magnitude ** 2).astype(np.float32)
    return frequencies.astype(np.float32), magnitude, power


def compute_spectrogram(
    waveform: Any,
    sample_rate: float,
    n_fft: int = 1024,
    hop_length: int = 256,
):
    """Compute STFT, magnitude, power, and decibel spectrograms."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0:
        empty = np.empty((0, 0), dtype=np.float32)
        return empty, empty, empty, empty, np.array([], dtype=np.float32)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")

    stft = librosa.stft(signal, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(stft).astype(np.float32)
    power = (magnitude ** 2).astype(np.float32)
    db = librosa.amplitude_to_db(magnitude, ref=np.max).astype(np.float32)
    times = librosa.frames_to_time(np.arange(stft.shape[1]), sr=sample_rate, hop_length=hop_length)
    return stft.astype(np.complex64), magnitude, power, db, times.astype(np.float32)


def compute_log_mel_spectrogram(
    waveform: Any,
    sample_rate: float,
    n_fft: int = 1024,
    hop_length: int = 256,
    n_mels: int = 128,
) -> np.ndarray:
    """Compute a log-Mel spectrogram suitable for speech and forensic analysis."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0:
        return np.empty((n_mels, 0), dtype=np.float32)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")

    mel = librosa.feature.melspectrogram(
        y=signal,
        sr=sample_rate,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        power=2.0,
    )
    return librosa.power_to_db(mel, ref=np.max).astype(np.float32)


def compute_mfcc_features(
    waveform: Any,
    sample_rate: float,
    n_mfcc: int = 20,
    n_fft: int = 1024,
    hop_length: int = 256,
) -> Dict[str, Any]:
    """Compute MFCCs and basic per-coefficient summary statistics."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0:
        return {
            "mfcc": np.empty((n_mfcc, 0), dtype=np.float32),
            "mean": np.zeros(n_mfcc, dtype=np.float32),
            "std": np.zeros(n_mfcc, dtype=np.float32),
        }
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")

    mfcc = librosa.feature.mfcc(
        y=signal,
        sr=sample_rate,
        n_mfcc=n_mfcc,
        n_fft=n_fft,
        hop_length=hop_length,
    ).astype(np.float32)
    return {
        "mfcc": mfcc,
        "mean": np.mean(mfcc, axis=1).astype(np.float32),
        "std": np.std(mfcc, axis=1).astype(np.float32),
    }


def spectral_centroid(waveform: Any, sample_rate: float) -> float:
    """Compute the mean spectral centroid."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return 0.0
    return float(np.mean(librosa.feature.spectral_centroid(y=signal, sr=sample_rate)))


def spectral_bandwidth(waveform: Any, sample_rate: float) -> float:
    """Compute the mean spectral bandwidth."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return 0.0
    return float(np.mean(librosa.feature.spectral_bandwidth(y=signal, sr=sample_rate)))


def spectral_rolloff(waveform: Any, sample_rate: float, roll_percent: float = 0.85) -> float:
    """Compute the spectral rolloff frequency."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return 0.0
    return float(np.mean(librosa.feature.spectral_rolloff(y=signal, sr=sample_rate, roll_percent=roll_percent)))


def spectral_flatness(waveform: Any, sample_rate: float) -> float:
    """Compute the average spectral flatness."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return 0.0
    return float(np.mean(librosa.feature.spectral_flatness(y=signal)))


def spectral_flux(waveform: Any, sample_rate: float, n_fft: int = 1024, hop_length: int = 256) -> float:
    """Compute average frame-to-frame spectral change."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return 0.0

    stft = librosa.stft(signal, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(stft)
    if magnitude.shape[1] < 2:
        return 0.0
    return float(np.mean(np.abs(np.diff(magnitude, axis=1))))


def dominant_frequency(waveform: Any, sample_rate: float) -> float:
    """Return the dominant frequency using the FFT magnitude spectrum."""
    frequencies, magnitude, _ = compute_fft(waveform, sample_rate)
    if frequencies.size == 0 or magnitude.size == 0:
        return 0.0
    return float(frequencies[np.argmax(magnitude)])


def compute_frequency_band_energy(waveform: Any, sample_rate: float) -> Dict[str, float]:
    """Compute normalized energy ratios for common speech-analysis bands."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return {
            "energy_0_500": 0.0,
            "energy_500_2000": 0.0,
            "energy_2000_4000": 0.0,
            "energy_4000_8000": 0.0,
        }

    frequencies, _, power = compute_fft(signal, sample_rate)
    total_energy = float(np.sum(power))
    band_ranges = {
        "energy_0_500": (0.0, 500.0),
        "energy_500_2000": (500.0, 2000.0),
        "energy_2000_4000": (2000.0, 4000.0),
        "energy_4000_8000": (4000.0, 8000.0),
    }

    results: Dict[str, float] = {}
    for name, (low, high) in band_ranges.items():
        mask = (frequencies >= low) & (frequencies < high)
        band_energy = float(np.sum(power[mask])) if np.any(mask) else 0.0
        results[name] = float(band_energy / total_energy) if total_energy > 0.0 else 0.0
    return results


def extract_signal_features(waveform: Any, sample_rate: float) -> Dict[str, float]:
    """Extract a compact set of scalar forensic signal features."""
    signal = _as_1d_float32(waveform)
    if signal.size == 0 or sample_rate <= 0:
        return {
            "rms": 0.0,
            "zero_crossing_rate": 0.0,
            "crest_factor": 0.0,
            "dominant_frequency": 0.0,
            "spectral_centroid": 0.0,
            "spectral_bandwidth": 0.0,
            "spectral_rolloff": 0.0,
            "spectral_flatness": 0.0,
            "spectral_flux": 0.0,
            "energy_0_500": 0.0,
            "energy_500_2000": 0.0,
            "energy_2000_4000": 0.0,
            "energy_4000_8000": 0.0,
        }

    band_energy = compute_frequency_band_energy(signal, sample_rate)
    return {
        "rms": compute_rms(signal),
        "zero_crossing_rate": zero_crossing_rate(signal),
        "crest_factor": crest_factor(signal),
        "dominant_frequency": dominant_frequency(signal, sample_rate),
        "spectral_centroid": spectral_centroid(signal, sample_rate),
        "spectral_bandwidth": spectral_bandwidth(signal, sample_rate),
        "spectral_rolloff": spectral_rolloff(signal, sample_rate),
        "spectral_flatness": spectral_flatness(signal, sample_rate),
        "spectral_flux": spectral_flux(signal, sample_rate),
        "energy_0_500": band_energy["energy_0_500"],
        "energy_500_2000": band_energy["energy_500_2000"],
        "energy_2000_4000": band_energy["energy_2000_4000"],
        "energy_4000_8000": band_energy["energy_4000_8000"],
    }


def extract_forensic_features(waveform: Any, sample_rate: float) -> Dict[str, float]:
    """Combine signal, spectral, cepstral, and temporal measurements."""
    signal = _as_1d_float32(waveform)
    # Pad only the feature input; timestamps retain the actual segment duration.
    padded = np.pad(signal, (0, max(0, 2048 - len(signal))))
    features = extract_signal_features(padded, sample_rate)
    mfcc = compute_mfcc_features(padded, sample_rate, n_mfcc=13)
    for index in range(13):
        features[f"mfcc_mean_{index}"] = float(mfcc["mean"][index])
        features[f"mfcc_std_{index}"] = float(mfcc["std"][index])
    frame_rms = librosa.feature.rms(y=padded, frame_length=1024, hop_length=256)[0]
    peak_rms = float(np.max(frame_rms))
    features["quiet_frame_ratio"] = float(np.mean(frame_rms < peak_rms * 0.05))
    features["energy_variation"] = float(np.std(frame_rms) / (np.mean(frame_rms) + 1e-8))
    return features
