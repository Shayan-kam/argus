"""Bounded chart data computed from the analyzed waveform, with no inferred labels."""

import numpy as np
import librosa

WAVEFORM_POINTS = 480
SPECTROGRAM_COLUMNS = 256
SPECTROGRAM_ROWS = 64
N_FFT = 1024
HOP_LENGTH = 256


def _downsample_surface(matrix, target_time_bins=180, target_frequency_bins=96):
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.size == 0:
        return np.zeros((max(1, target_frequency_bins), max(1, target_time_bins)), dtype=np.float32)
    time_bins = max(1, min(target_time_bins, matrix.shape[1]))
    frequency_bins = max(1, min(target_frequency_bins, matrix.shape[0]))
    time_index = np.linspace(0, matrix.shape[1] - 1, time_bins, dtype=int)
    frequency_index = np.linspace(0, matrix.shape[0] - 1, frequency_bins, dtype=int)
    return matrix[np.ix_(frequency_index, time_index)].astype(np.float32)


def _normalize_surface(matrix):
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.size == 0:
        return matrix
    max_value = float(np.nanmax(matrix))
    if not np.isfinite(max_value) or max_value <= 0:
        return np.zeros_like(matrix, dtype=np.float32)
    normalized = matrix / max_value
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def build_visual_analysis(waveform, sample_rate):
    signal = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if not signal.size or sample_rate <= 0 or not np.all(np.isfinite(signal)):
        raise ValueError("Visual analysis requires finite audio samples and a positive sample rate.")
    duration = len(signal) / sample_rate

    edges = np.linspace(0, len(signal), min(WAVEFORM_POINTS, len(signal)) + 1, dtype=int)
    envelope = []
    for start, end in zip(edges[:-1], edges[1:]):
        chunk = signal[start:end]
        envelope.append({
            "start": float(start / sample_rate), "end": float(end / sample_rate),
            "min": round(float(chunk.min()), 6), "max": round(float(chunk.max()), 6),
            "rms": round(float(np.sqrt(np.mean(chunk ** 2))), 6),
        })

    stft = librosa.stft(signal, n_fft=N_FFT, hop_length=HOP_LENGTH)
    magnitude = np.abs(stft)
    power = magnitude ** 2
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=N_FFT)
    positive = frequencies <= sample_rate / 2
    frequencies = frequencies[positive]
    power = power[positive]
    target_time_bins = min(220, max(100, min(SPECTROGRAM_COLUMNS, power.shape[1])))
    target_frequency_bins = min(128, max(64, min(SPECTROGRAM_ROWS, power.shape[0])))
    downsampled_power = _downsample_surface(power, target_time_bins=target_time_bins, target_frequency_bins=target_frequency_bins)
    normalized_surface = _normalize_surface(downsampled_power)
    dB_surface = librosa.amplitude_to_db(normalized_surface, ref=np.max)
    dB_surface = np.clip(dB_surface, -80, 0)
    time_bins = np.linspace(0, duration, downsampled_power.shape[1])
    frequency_bins = np.linspace(0, sample_rate / 2, downsampled_power.shape[0])
    time_axis = np.round(time_bins, 6).tolist()
    frequency_axis = np.round(frequency_bins, 3).tolist()

    display_power = []
    accumulated_power = np.zeros(len(frequencies), dtype=np.float64)
    for frame in range(power.shape[1]):
        frame_power = power[:, frame]
        accumulated_power += frame_power
        display_power.append(frame_power)
    display_power = np.asarray(display_power).T if display_power else np.zeros((0, 0), dtype=np.float32)
    if display_power.size:
        reference = max(float(display_power.max()), 1e-20)
        decibels = 10 * np.log10(np.maximum(display_power, 1e-20) / reference)
        decibels = np.clip(np.rint(decibels), -80, 0).astype(int)
    else:
        decibels = np.zeros((0, 0), dtype=int)

    total_power = float(accumulated_power.sum())
    bands = []
    for label, low, high in [
        ("Low tones", 0, 500), ("Mid tones", 500, 2000),
        ("High tones", 2000, 4000), ("Very high tones", 4000, sample_rate / 2),
    ]:
        mask = (frequencies >= low) & (frequencies < high)
        if high == sample_rate / 2:
            mask |= frequencies == high
        value = float(accumulated_power[mask].sum())
        bands.append({
            "label": label, "low_hz": low, "high_hz": high,
            "energy_percent": round(100 * value / total_power, 4) if total_power else 0.0,
        })

    terrain = {
        "time_seconds": time_axis,
        "frequency_hz": frequency_axis,
        "surface": normalized_surface.tolist(),
        "n_time_bins": int(normalized_surface.shape[1]),
        "n_frequency_bins": int(normalized_surface.shape[0]),
        "alpha": 1.0,
        "z_axis_label": "Normalized spectral magnitude (z = S(t, f))",
        "reference": "Spectral power is normalized for terrain height; synthetic risk is kept as an overlay, not a height dimension.",
    }
    waterfall = {
        "time_seconds": time_axis,
        "frequency_hz": frequency_axis,
        "frames": normalized_surface.T.tolist(),
        "n_time_bins": int(normalized_surface.shape[1]),
        "n_frequency_bins": int(normalized_surface.shape[0]),
        "reference": "Real STFT power values are used; no fabricated anomalies are introduced.",
    }

    return {
        "waveform": envelope,
        "spectrogram": {
            "time_edges_seconds": np.linspace(0, duration, normalized_surface.shape[1] + 1).round(6).tolist(),
            "frequencies_hz": frequency_axis,
            "db": decibels.tolist(), "min_db": -80, "max_db": 0,
            "frequency_scale": "log",
            "reference": "Strongest displayed frequency-time cell; not microphone loudness.",
        },
        "terrain": terrain,
        "waterfall": waterfall,
        "frequency_bands": bands,
        "notes": "Charts use normalized mono audio. Brightness and amplitude describe sound, not evidence of manipulation.",
    }
