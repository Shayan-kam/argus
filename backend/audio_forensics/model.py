"""Machine-learning models for synthetic-audio detection.

This module contains model logic only. It intentionally does not load audio files
or implement DSP feature extraction; those responsibilities live in
`audio_preprocess.py`.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - graceful degradation when sklearn is absent
    LogisticRegression = None
    RandomForestClassifier = None
    StandardScaler = None
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    xgb = None
    XGBOOST_AVAILABLE = False


DEFAULT_FEATURE_KEYS = [
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
]


def feature_vector_from_dict(
    feature_dict: Mapping[str, Any],
    feature_keys: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Convert a feature dictionary into a fixed-length numeric vector."""
    if not isinstance(feature_dict, Mapping):
        raise TypeError("feature_dict must be a mapping of feature names to numeric values.")

    keys = list(feature_keys) if feature_keys is not None else DEFAULT_FEATURE_KEYS
    values: List[float] = []

    for key in keys:
        if key not in feature_dict:
            values.append(0.0)
            continue

        value = feature_dict[key]
        arr = np.asarray(value)
        if arr.size == 0:
            values.append(0.0)
        elif arr.size == 1:
            values.append(float(arr.reshape(-1)[0]))
        else:
            values.append(float(np.mean(arr)))

    return np.asarray(values, dtype=np.float32)


def feature_matrix_from_records(
    records: Union[np.ndarray, Sequence[Mapping[str, Any]], Mapping[str, Any]],
    feature_keys: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Normalize feature records into a 2D numeric matrix."""
    if isinstance(records, Mapping):
        return feature_vector_from_dict(records, feature_keys).reshape(1, -1)

    if isinstance(records, np.ndarray):
        arr = np.asarray(records, dtype=np.float32)
        if arr.ndim == 1:
            return arr.reshape(1, -1)
        return arr.astype(np.float32)

    if not isinstance(records, Sequence):
        raise TypeError("records must be a feature matrix or a sequence of feature dictionaries.")

    if len(records) == 0:
        return np.empty((0, 0), dtype=np.float32)

    if isinstance(records[0], Mapping):
        matrix = [feature_vector_from_dict(item, feature_keys) for item in records]
        return np.vstack(matrix).astype(np.float32)

    arr = np.asarray(records, dtype=np.float32)
    if arr.ndim == 1:
        return arr.reshape(1, -1)
    return arr.astype(np.float32)


class BaseAudioClassifier:
    """Shared interface for audio classification models."""

    def fit(self, X: Any, y: Any):
        raise NotImplementedError("Subclasses must implement fit().")

    def predict_proba(self, X: Any) -> np.ndarray:
        raise NotImplementedError("Subclasses must implement predict_proba().")

    def predict(self, X: Any):
        raise NotImplementedError("Subclasses must implement predict().")

    def predict_synthetic_probability(self, features: Any) -> float:
        raise NotImplementedError("Subclasses must implement predict_synthetic_probability().")


class DSPBaselineModel(BaseAudioClassifier):
    """Simple feature-based synthetic-audio baseline.

    This is designed for handcrafted features from `audio_preprocess.py` and can
    be swapped for a stronger model later without changing the API.
    """

    def __init__(
        self,
        model_type: str = "logistic_regression",
        random_state: int = 42,
        feature_keys: Optional[Sequence[str]] = None,
        **kwargs,
    ):
        self.model_type = model_type.lower()
        self.random_state = random_state
        self.feature_keys = list(feature_keys) if feature_keys is not None else DEFAULT_FEATURE_KEYS
        self.kwargs = kwargs
        self.model = self._build_model()
        self.synthetic_label_ = None
        self.positive_class_index_ = 0

    def _build_model(self):
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for the DSP baseline model. Install it to train or evaluate the feature-based classifier."
            )

        if self.model_type == "logistic_regression":
            return LogisticRegression(max_iter=1000, random_state=self.random_state, **self.kwargs)

        if self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=self.kwargs.get("n_estimators", 300),
                random_state=self.random_state,
                **{k: v for k, v in self.kwargs.items() if k != "n_estimators"},
            )

        if self.model_type == "xgboost":
            if not XGBOOST_AVAILABLE:
                raise ImportError("xgboost is not installed. Install it to use the XGBoost option.")
            return xgb.XGBClassifier(
                n_estimators=self.kwargs.get("n_estimators", 300),
                learning_rate=self.kwargs.get("learning_rate", 0.05),
                max_depth=self.kwargs.get("max_depth", 6),
                random_state=self.random_state,
                objective="binary:logistic",
                eval_metric="logloss",
            )

        raise ValueError(
            "Unsupported model_type. Choose 'logistic_regression', 'random_forest', or 'xgboost'."
        )

    @staticmethod
    def _normalize_label(label: Any) -> str:
        return str(label).strip().lower()

    def _resolve_positive_class(self, y: np.ndarray) -> Any:
        labels = list(dict.fromkeys(y.tolist()))
        if len(labels) == 1:
            return labels[0]

        normalized = [self._normalize_label(label) for label in labels]

        for label, normalized_label in zip(labels, normalized):
            if any(token in normalized_label for token in ("synthetic", "fake", "spoof", "tts", "voice", "splicing")):
                return label

        try:
            numeric_labels = [float(label) for label in labels]
            if len(numeric_labels) == 2 and all(np.isfinite(numeric_labels)):
                return max(labels, key=lambda value: float(value))
        except (TypeError, ValueError):
            pass

        return labels[-1]

    def fit(self, X: Any, y: Any):
        X_mat = feature_matrix_from_records(X, self.feature_keys)
        y_arr = np.asarray(y)

        if X_mat.shape[0] != y_arr.shape[0]:
            raise ValueError("Feature rows and labels must have the same number of samples.")

        self.synthetic_label_ = self._resolve_positive_class(y_arr)
        self.model.fit(X_mat, y_arr)
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        X_mat = feature_matrix_from_records(X, self.feature_keys)
        return np.asarray(self.model.predict_proba(X_mat), dtype=np.float32)

    def predict(self, X: Any):
        X_mat = feature_matrix_from_records(X, self.feature_keys)
        return self.model.predict(X_mat)

    def predict_synthetic_probability(self, features: Any) -> float:
        probabilities = self.predict_proba(features)

        if probabilities.ndim == 1:
            return float(probabilities[0])

        if len(self.model.classes_) == 0:
            return 0.0

        target_class = self.synthetic_label_
        if target_class is None:
            target_class = self._resolve_positive_class(self.model.classes_)

        if target_class in self.model.classes_:
            index = np.where(self.model.classes_ == target_class)[0][0]
            return float(probabilities[0, index])

        positive_index = np.argmax(probabilities[0])
        return float(probabilities[0, positive_index])


class ManipulationClassifier(DSPBaselineModel):
    """Generic multi-class classifier for labels like real/tts/voice_conversion/splicing.

    The labels are not hardcoded here. This can be trained on the dataset's actual
    manipulation taxonomy and used later in the same model interface.
    """

    def __init__(self, model_type: str = "logistic_regression", random_state: int = 42, feature_keys=None, **kwargs):
        super().__init__(model_type=model_type, random_state=random_state, feature_keys=feature_keys, **kwargs)

    def predict_manipulation_type(self, features: Any):
        probs = self.predict_proba(features)
        label_index = int(np.argmax(probs[0])) if probs.ndim > 1 else int(np.argmax(probs))
        return self.model.classes_[label_index]


class SyntheticAudioModel(DSPBaselineModel):
    """Alias for the feature-based baseline model used by broader inference code."""

    pass


def predict_synthetic_probability(model: BaseAudioClassifier, features: Any) -> float:
    """Convenience function for inference code to call a single probability."""
    return float(model.predict_synthetic_probability(features))


__all__ = [
    "DEFAULT_FEATURE_KEYS",
    "feature_vector_from_dict",
    "feature_matrix_from_records",
    "BaseAudioClassifier",
    "DSPBaselineModel",
    "ManipulationClassifier",
    "SyntheticAudioModel",
    "predict_synthetic_probability",
]
