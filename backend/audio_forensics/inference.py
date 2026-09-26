"""Orchestrate audio measurements and optional trained-model predictions."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Sequence

import numpy as np

try:
    from .audio_preprocess import extract_forensic_features, preprocess_audio, segment_audio
    from .model import feature_vector_from_dict
    from .interpretation import assess_manipulation, explain_result
    from .visualization import build_visual_analysis
except ImportError:  # Direct script execution or optional summary backend.
    from audio_preprocess import extract_forensic_features, preprocess_audio, segment_audio
    from model import feature_vector_from_dict
    from interpretation import assess_manipulation, explain_result
    from visualization import build_visual_analysis

try:
    from gemini_client import generate_json
except ImportError:
    try:
        from backend.gemini_client import generate_json
    except ImportError:  # pragma: no cover - optional summary layer
        try:
            from ..gemini_client import generate_json
        except ImportError:
            generate_json = None

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


def _fallback_ai_summary(feature_summary: Dict[str, Any], manipulation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    summary = feature_summary or {}
    rms = float(summary.get("rms", 0.0) or 0.0)
    dominant = float(summary.get("dominant_frequency", 0.0) or 0.0)
    flux = float(summary.get("spectral_flux", 0.0) or 0.0)
    flatness = float(summary.get("spectral_flatness", 0.0) or 0.0)
    quiet = float(summary.get("quiet_frame_ratio", 0.0) or 0.0)

    signal_text = (
        "The waveform is strong and well above the quiet baseline, which means the signal is cleanly present throughout the clip."
        if rms > 0.6 else
        "The amplitude is moderate and consistent, without extremely loud spikes or long quiet dropouts."
        if rms > 0.25 else
        "The waveform is soft and quieter than a loud capture, so the signal is less forceful overall."
    )
    pitch_text = (
        "The dominant energy sits higher in the spectrum, which gives the sound a brighter or sharper character."
        if dominant > 3000 else
        "The dominant energy sits in the mid-band, which is consistent with a typical spoken or tonal profile."
        if dominant > 800 else
        "The dominant energy is lower in the spectrum, which makes the recording sound darker or more resonant."
    )
    time_text = (
        "The signal changes noticeably from window to window, which can indicate motion, modulation, or an uneven pattern across the clip."
        if flux > 0.18 else
        "The timing remains fairly steady, with moderate natural variation rather than sharp jumps."
        if flux > 0.08 else
        "The timing is very stable and consistent, with little evidence of abrupt or erratic motion."
    )
    texture_text = (
        "The spectrum skews more noise-like than tone-like, suggesting a more textured or less pure harmonic profile."
        if flatness > 0.4 else
        "The sound blends a mix of tone-like and noise-like features, which is common in real-world recordings."
        if flatness > 0.2 else
        "The spectrum is more tone-like and stable, which usually points to a cleaner, more structured sound."
    )
    quiet_text = (
        "A small share of short windows are very quiet, which is normal and not by itself evidence of editing or fakery."
        if quiet > 0.05 else
        "The clip keeps a fairly steady loudness profile with very little time spent in silence."
    )

    notes = [
        {"label": "Signal analysis", "summary": signal_text},
        {"label": "Frequency analysis", "summary": pitch_text},
        {"label": "Timing analysis", "summary": time_text},
        {"label": "Texture and noise", "summary": texture_text + " " + quiet_text},
    ]
    if manipulation and manipulation.get("type"):
        notes.append({"label": "Manipulation note", "summary": f"The recorded pattern is consistent with the current manipulation assessment: {manipulation.get('label', manipulation.get('type'))}. This remains a model-based interpretation, not a verified claim."})

    return {
        "headline": "The audio looks consistent with the measured signal profile, and the score should be interpreted alongside the visual time-frequency maps rather than alone.",
        "notes": notes,
    }


def _generate_ai_summary(feature_summary: Dict[str, Any], manipulation: Optional[Dict[str, Any]]=None, visual_analysis: Optional[Dict[str, Any]]=None) -> tuple[Dict[str, Any], str]:
    if not feature_summary:
        return _fallback_ai_summary({}, manipulation), "fallback"

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or generate_json is None:
        return _fallback_ai_summary(feature_summary, manipulation), "fallback"

    payload = {
        "feature_summary": feature_summary,
        "manipulation": manipulation,
        "visual_analysis": {
            "terrain_bins": visual_analysis.get("terrain", {}).get("n_time_bins") if isinstance(visual_analysis, dict) else None,
            "waterfall_bins": visual_analysis.get("waterfall", {}).get("n_time_bins") if isinstance(visual_analysis, dict) else None,
            "suspicious_regions": visual_analysis.get("suspicious_regions", []) if isinstance(visual_analysis, dict) else [],
        },
    }
    prompt = (
        "You are a forensic audio analyst. Explain these metrics in plain English for a non-expert but technically aware audience. "
        "Keep the explanation grounded in the actual numbers and describe how the visual spectrogram/terrain/waterfall data supports the conclusion. "
        "Do not claim certainty. Output valid JSON with a single key 'headline' and a list of objects with keys 'label' and 'summary'.\n"
        f"Metrics: {json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = generate_json(prompt)
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("notes"), list):
            return parsed, "gemini"
        if isinstance(parsed, dict) and isinstance(parsed.get("headline"), str):
            notes = parsed.get("notes") or []
            if isinstance(notes, list):
                return parsed, "gemini"
    except Exception:
        pass
    return _fallback_ai_summary(feature_summary, manipulation), "fallback"


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
            {
                "start_time": float(segment["start"]),
                "end_time": float(segment["end"]),
                "score": float(segment["score"]),
            }
            for segment in segment_results
            if segment["score"] >= threshold
        ]
        visual_analysis["waterfall"]["highlighted_regions"] = [
            {
                "start_time": region["start_time"],
                "end_time": region["end_time"],
            }
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
        ai_summary, ai_summary_source = _generate_ai_summary(summary, manipulation, visual_analysis)
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
        "feature_summary": summary,
        "ai_summary": ai_summary,
        "ai_summary_source": ai_summary_source,
        "runtime_config": {
            "gemini_api_key_present": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
            "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        },
        "visual_analysis": visual_analysis,
        "metadata": {
            "duration": processed["duration"],
            "sample_rate": sample_rate,
            "num_segments": len(segment_results),
            "segment_window_seconds": segment_window_seconds,
            "segment_hop_seconds": hop_seconds,
            "feature_summary_method": "Unweighted mean of overlapping section measurements",
        },
    }


__all__ = [
    "DEFAULT_THRESHOLD", "DEFAULT_SEGMENT_WINDOW_SECONDS", "DEFAULT_SEGMENT_HOP_SECONDS",
    "aggregate_segment_scores", "analyze_audio",
]
