"""HTTP integration for the audio pipeline; repository routes remain independent."""

import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/audio", tags=["Audio forensics"])
PACKAGE_DIR = Path(__file__).resolve().parent
MAX_FILES = 20
MAX_FILE_BYTES = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


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
    analysis_id = str(uuid.uuid4())
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
                file_started = time.perf_counter()
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
                    result = error_result(str(exc))
                finally:
                    destination.unlink(missing_ok=True)
                result["metadata"].update({
                    "input_size_bytes": upload.size if upload.size is not None else total,
                    "filename_extension": Path(filename).suffix.lower(),
                    "analysis_seconds": round(time.perf_counter() - file_started, 4),
                })
                results.append({
                    "filename": filename, "file_id": f"{analysis_id}:{index + 1}",
                    "analysis_id": analysis_id,
                    "analyzed_at_utc": datetime.now(timezone.utc).isoformat(),
                    **result,
                })
        return {"results": results, "total_seconds": round(time.perf_counter() - started, 3)}
    finally:
        for upload in files:
            upload.file.close()
