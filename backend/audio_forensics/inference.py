"""Orchestrate audio measurements and optional trained-model predictions."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Sequence

import numpy as np

try:
    from .audio_preprocess import extract_forensic_features, preprocess_audio, segment_audio
    from .model import feature_vector_from_dict
    from .interpretation import assess_manipulation, explain_result
    from .visualization import build_visual_analysis
except ImportError:  # Direct script execution.
    from audio_preprocess import extract_forensic_features, preprocess_audio, segment_audio
    from model import feature_vector_from_dict
    from interpretation import assess_manipulation, explain_result
    from visualization import build_visual_analysis

DEFAULT_THRESHOLD = 0.5
DEFAULT_SEGMENT_WINDOW_SECONDS = 4.0
DEFAULT_SEGMENT_HOP_SECONDS = 2.0
BASELINE_NOTICE = (
    "Preview mode: results describe the sound and suggest where to listen. "
    "They do not verify whether a recording is authentic."
)


def _fallback_signal_probability(features: Dict[str, Any]) -> float:
    """Retain the original development baseline, explicitly identified in results."""
    score = (
        min(0.25, max(0.0, features.get("zero_crossing_rate", 0)) * 2.0)
        + min(0.15, max(0.0, features.get("spectral_flatness", 0)) * 30.0)
        + min(0.20, max(0.0, features.get("spectral_flux", 0)) * 5.0)
        + min(0.20, max(0.0, features.get("crest_factor", 0)) / 8.0)
        + min(0.10, max(0.0, features.get("dominant_frequency", 0)) / 8000.0)
        + min(0.10, max(0.0, features.get("energy_500_2000", 0)) * 3.0)
    )
    return float(np.clip(score, 0.0, 1.0))


def aggregate_segment_scores(
    segment_scores: Sequence[Dict[str, Any]], strategy: str = "mean", top_k: int = 3,
) -> float:
    if not segment_scores:
        return 0.0
    scores = np.asarray([segment["score"] for segment in segment_scores], dtype=np.float64)
    strategy = (strategy or "mean").lower()
    if strategy == "mean":
        return float(np.mean(scores))
    if strategy == "max":
        return float(np.max(scores))
    if strategy == "top_k":
        return float(np.mean(np.sort(scores)[-min(max(int(top_k), 1), len(scores)):]))
    raise ValueError(f"Unsupported aggregation strategy: {strategy!r}")


def error_result(message: str) -> Dict[str, Any]:
    """Never convert failed analysis into a real/zero-percent prediction."""
    return {
        "synthetic_probability": None, "synthetic_likelihood": None,
        "classification": "error", "manipulation_type": None,
        "scoring_method": None, "models": {"signal": None, "spectrogram": None, "ssl": None},
        "segments": [], "suspicious_segments": [], "techniques": [], "waveform": [],
        "metadata": {"duration": None, "sample_rate": None}, "error": message,
    }


def _model_score(model: Any, features: dict) -> float:
    if hasattr(model, "predict_synthetic_probability"):
        score = float(model.predict_synthetic_probability(features))
    else:
        classes = list(model.classes_)
        positive = next((label for label in (1, "synthetic", "fake", "spoof") if label in classes), None)
        if positive is None:
            raise ValueError("Model must identify its synthetic class.")
        vector = feature_vector_from_dict(features)
        score = float(model.predict_proba([vector])[0, classes.index(positive)])
    if not np.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("Model returned an invalid probability.")
    return score


def analyze_audio(
    file_path: str,
    model: Optional[Any] = None,
    threshold: float = DEFAULT_THRESHOLD,
    segment_window_seconds: float = DEFAULT_SEGMENT_WINDOW_SECONDS,
    hop_seconds: float = DEFAULT_SEGMENT_HOP_SECONDS,
    aggregation: str = "mean",
    top_k: int = 3,
    manipulation_model: Optional[Any] = None,
) -> Dict[str, Any]:
    if not file_path or not os.path.isfile(file_path):
        return error_result("Audio file not found.")
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        return error_result("Threshold must be between zero and one.")

    try:
        processed = preprocess_audio(file_path)
        waveform, sample_rate = processed["waveform"], processed["sample_rate"]
        segments = segment_audio(waveform, sample_rate, segment_window_seconds, hop_seconds)
        records, segment_results = [], []
        for segment in segments:
            features = extract_forensic_features(segment["waveform"], sample_rate)
            records.append(features)
            score = _model_score(model, features) if model is not None else _fallback_signal_probability(features)
            segment_results.append({
                "start": segment["start_time"], "end": segment["end_time"], "score": score,
                "features": features,
            })
        visual_analysis = build_visual_analysis(waveform, sample_rate)
        visual_analysis["suspicious_regions"] = [
            {"start_time": float(segment["start"]), "end_time": float(segment["end"]), "score": float(segment["score"])}
            for segment in segment_results if segment["score"] >= threshold
        ]
        if not visual_analysis["suspicious_regions"]:
            visual_analysis["suspicious_regions"] = []
        visual_analysis["waterfall"]["highlighted_regions"] = [
            {"start_time": region["start_time"], "end_time": region["end_time"]}
            for region in visual_analysis["suspicious_regions"]
        ]
        probability = aggregate_segment_scores(segment_results, aggregation, top_k)
        summary = {key: float(np.mean([record[key] for record in records])) for key in records[0]}
        manipulation = assess_manipulation(file_path, records, segment_results, manipulation_model)
        interpretation = explain_result(
            summary,
            segment_results,
            probability,
            threshold,
            manipulation,
            trained=(model is not None or manipulation_model is not None),
        )
    except Exception as exc:
        # Model errors must remain visible instead of silently using a heuristic.
        return error_result(str(exc))

    techniques = [
        {"name": "Signal analysis", "description": "Amplitude and zero-crossing measurements.",
         "metrics": {"RMS amplitude": summary["rms"], "Crest factor": summary["crest_factor"],
                     "Zero-crossing rate": summary["zero_crossing_rate"]}},
        {"name": "Frequency analysis", "description": "FFT and spectral distribution across time.",
         "metrics": {"Dominant frequency (Hz)": summary["dominant_frequency"],
                     "Spectral centroid (Hz)": summary["spectral_centroid"],
                     "Spectral flatness": summary["spectral_flatness"]}},
        {"name": "Voice features", "description": "13 MFCC coefficients describe the spectral envelope.",
         "metrics": {"Mean first MFCC": summary["mfcc_mean_0"],
                     "First MFCC variation": summary["mfcc_std_0"]}},
        {"name": "Timing analysis", "description": "Changes in energy and quiet frames.",
         "metrics": {"Quiet frame ratio": summary["quiet_frame_ratio"],
                     "Energy variation": summary["energy_variation"],
                     "Spectral flux": summary["spectral_flux"]}},
    ]
    peaks = [float(np.max(np.abs(chunk))) for chunk in np.array_split(waveform, min(160, len(waveform)))]
    return {
        "synthetic_probability": probability,
        "synthetic_likelihood": round(probability * 100, 2),
        "classification": "synthetic" if probability >= threshold else "real",
        "manipulation_type": manipulation["type"],
        "manipulation_assessment": manipulation,
        "interpretation": interpretation,
        "source": "known_demo" if manipulation["status"] == "known_source" else "uploaded_audio",
        "scoring_method": "trained_model" if model is not None else "experimental_baseline",
        "notice": "Model estimate; reliability depends on evaluation with held-out audio." if model is not None else BASELINE_NOTICE,
        "models": {"signal": probability, "spectrogram": None, "ssl": None},
        "threshold": threshold, "aggregation": aggregation,
        "segments": segment_results,
        "suspicious_segments": [segment for segment in segment_results if segment["score"] >= threshold],
        "techniques": techniques, "waveform": peaks,
        "feature_summary": summary, "visual_analysis": visual_analysis,
        "metadata": {"duration": processed["duration"], "sample_rate": sample_rate,
                     "num_segments": len(segment_results),
                     "segment_window_seconds": segment_window_seconds, "segment_hop_seconds": hop_seconds,
                     "feature_summary_method": "Unweighted mean of overlapping section measurements"},
    }


__all__ = [
    "DEFAULT_THRESHOLD", "DEFAULT_SEGMENT_WINDOW_SECONDS", "DEFAULT_SEGMENT_HOP_SECONDS",
    "aggregate_segment_scores", "analyze_audio",
]
