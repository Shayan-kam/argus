"""Bounded chart data computed from the analyzed waveform, with no inferred labels."""

import numpy as np

WAVEFORM_POINTS = 480
SPECTROGRAM_COLUMNS = 256
SPECTROGRAM_ROWS = 64
N_FFT = 1024
HOP_LENGTH = 256


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

    # Centered, overlapping FFT windows. Process small groups so a 10-minute
    # recording does not allocate an entire high-resolution spectrogram.
    padded = np.pad(signal, (N_FFT // 2, N_FFT // 2))
    frame_count = 1 + len(signal) // HOP_LENGTH
    columns = min(SPECTROGRAM_COLUMNS, frame_count)
    frame_edges = np.linspace(0, frame_count, columns + 1, dtype=int)
    frequencies = np.fft.rfftfreq(N_FFT, d=1 / sample_rate)
    display_frequencies = np.geomspace(max(sample_rate / N_FFT, 62.5), sample_rate / 2, SPECTROGRAM_ROWS)
    window = np.hanning(N_FFT).astype(np.float32)
    display_power = []
    accumulated_power = np.zeros(len(frequencies), dtype=np.float64)
    for first, stop in zip(frame_edges[:-1], frame_edges[1:]):
        block = padded[first * HOP_LENGTH:(stop - 1) * HOP_LENGTH + N_FFT]
        frames = np.lib.stride_tricks.sliding_window_view(block, N_FFT)[::HOP_LENGTH]
        power = np.abs(np.fft.rfft(frames * window, axis=1)) ** 2
        power[:, 1:-1] *= 2  # Account for the omitted negative frequencies.
        averaged = power.mean(axis=0)
        accumulated_power += power.sum(axis=0)
        display_power.append(np.interp(display_frequencies, frequencies, averaged))
    display_power = np.asarray(display_power).T
    reference = max(float(display_power.max()), 1e-20)
    decibels = 10 * np.log10(np.maximum(display_power, 1e-20) / reference)
    decibels = np.clip(np.rint(decibels), -80, 0).astype(int)
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

    return {
        "waveform": envelope,
        "spectrogram": {
            "time_edges_seconds": np.linspace(0, duration, columns + 1).round(6).tolist(),
            "frequencies_hz": display_frequencies.round(3).tolist(),
            "db": decibels.tolist(), "min_db": -80, "max_db": 0,
            "frequency_scale": "log",
            "reference": "Strongest displayed frequency-time cell; not microphone loudness.",
        },
        "frequency_bands": bands,
        "notes": "Charts use normalized mono audio. Brightness and amplitude describe sound, not evidence of manipulation.",
    }
