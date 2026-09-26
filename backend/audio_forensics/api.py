"""HTTP integration for the audio pipeline; repository routes remain independent."""

import logging
import math
import os
import tempfile
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/audio", tags=["Audio forensics"])
PACKAGE_DIR = Path(__file__).resolve().parent
MAX_FILES = 20
MAX_FILE_BYTES = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


def _json_ready(value):
    """Keep browser JSON.parse from rejecting NaN or Infinity in a 200 response."""
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


@lru_cache(maxsize=1)
def _read_model(path: str, modified: int):
    # Only operator-configured local artifacts are loaded, never uploaded models.
    import joblib

    artifact = joblib.load(path)
    if isinstance(artifact, dict):
        detector = artifact["detector"]
        manipulation = artifact.get("manipulation")
    else:
        detector, manipulation = artifact, None
    if not hasattr(detector, "predict_synthetic_probability") and not hasattr(detector, "predict_proba"):
        raise ValueError("Unsupported audio model.")
    return detector, manipulation


def configured_models():
    configured = os.getenv("ARGUS_AUDIO_MODEL")
    path = Path(configured) if configured else PACKAGE_DIR / "trained_model.joblib"
    if not path.is_file():
        if configured:
            raise ValueError("The configured audio model was not found.")
        return None, None
    return _read_model(str(path.resolve()), path.stat().st_mtime_ns)


@router.get("/status")
def audio_status():
    try:
        from .inference import BASELINE_NOTICE
        from .interpretation import MANIPULATION_CATEGORIES
        model, manipulation = configured_models()
        return {
            "available": True, "scoring_method": "trained_model" if model is not None else "experimental_baseline",
            "notice": "A trained model is loaded." if model is not None else BASELINE_NOTICE,
            "max_files": MAX_FILES, "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
            "max_duration_seconds": 600,
            "type_detector_available": manipulation is not None,
            "manipulation_categories": MANIPULATION_CATEGORIES,
        }
    except Exception:
        logger.exception("Audio analysis is unavailable")
        return {"available": False, "notice": "Audio analysis is unavailable. Check the backend dependencies and model configuration."}


@router.get("/sample")
def sample_audio():
    path = PACKAGE_DIR / "sample.wav"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Demo recording is not installed.")
    return FileResponse(path, media_type="audio/wav", filename="argus-demo.wav")


@router.post("/analyze")
def analyze_uploads(files: list[UploadFile] = File(...)):
    started = time.perf_counter()
    try:
        if not 1 <= len(files) <= MAX_FILES:
            raise HTTPException(status_code=400, detail=f"Choose between 1 and {MAX_FILES} audio files.")
        try:
            from .inference import analyze_audio, error_result
            model, manipulation = configured_models()
        except Exception as exc:
            logger.exception("Audio analysis is unavailable")
            raise HTTPException(status_code=503, detail="Audio analysis is unavailable. Check the backend dependencies and model configuration.") from exc

        results = []
        with tempfile.TemporaryDirectory(prefix="argus_audio_") as folder:
            for index, upload in enumerate(files):
                filename = (upload.filename or f"audio-{index + 1}").replace("\\", "/").split("/")[-1]
                # Client filenames are metadata only, never server paths.
                suffix = Path(filename).suffix.lower()
                if len(suffix) > 12 or not suffix[1:].isalnum():
                    suffix = ".audio"
                destination = Path(folder) / f"{index}{suffix}"
                total = 0
                try:
                    with destination.open("wb") as output:
                        while chunk := upload.file.read(1024 * 1024):
                            total += len(chunk)
                            if total > MAX_FILE_BYTES:
                                raise ValueError("File exceeds the 50 MB upload limit.")
                            output.write(chunk)
                    result = analyze_audio(str(destination), model=model, manipulation_model=manipulation)
                except Exception as exc:
                    logger.exception("Audio analysis failed for %s", filename)
                    result = error_result(str(exc))
                finally:
                    destination.unlink(missing_ok=True)
                if result.get("error"):
                    logger.warning("Audio analysis error for %s: %s", filename, result["error"])
                results.append(_json_ready({"filename": filename, **result}))
        return {"results": results, "total_seconds": round(time.perf_counter() - started, 3)}
    finally:
        for upload in files:
            upload.file.close()
