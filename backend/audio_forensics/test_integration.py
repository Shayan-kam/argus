"""Integration checks using actual audio decoding and HTTP multipart uploads."""

from pathlib import Path
import subprocess

import imageio_ffmpeg
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from main import app
from audio_forensics import api
from audio_forensics.inference import analyze_audio

SAMPLE = Path(__file__).with_name("sample.wav")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "configured_models", lambda: (None, None))
    return TestClient(app)


def test_demo_and_repository_health(client):
    assert client.get("/api/health").json()["status"] == "healthy"
    assert client.get("/api/audio/sample").content == SAMPLE.read_bytes()
    assert client.get("/api/audio/status").json()["scoring_method"] == "experimental_baseline"
    response = client.post("/api/analyze", json={
        "repository_url": "https://github.com/example/repository", "scan_profile": "invalid",
    })
    assert response.status_code == 400
    assert "Invalid scan profile" in response.json()["detail"]


def test_upload_result_and_partial_failure(client):
    response = client.post("/api/audio/analyze", files=[
        ("files", ("sample.wav", SAMPLE.read_bytes(), "audio/wav")),
        ("files", ("broken.mp3", b"not audio", "audio/mpeg")),
    ])
    assert response.status_code == 200
    good, bad = response.json()["results"]
    assert good["filename"] == "sample.wav"
    assert good["metadata"]["sample_rate"] == 16000
    assert good["metadata"]["duration"] == 8
    assert len(good["techniques"]) == 4
    assert len(good["segments"]) == 3
    assert good["segments"][-1]["end"] == 8
    assert 0 <= good["synthetic_likelihood"] <= 100
    assert good["synthetic_likelihood"] == round(good["synthetic_probability"] * 100, 2)
    assert good["scoring_method"] == "experimental_baseline"
    assert good["manipulation_type"] == "generated_test_audio"
    assert good["manipulation_assessment"]["status"] == "known_source"
    assert len(good["waveform"]) == 160
    assert bad["classification"] == "error"
    assert bad["synthetic_probability"] is None
    assert bad["synthetic_likelihood"] is None


@pytest.mark.parametrize("extension,codec", [("mp3", "libmp3lame"), ("m4a", "aac"), ("flac", "flac")])
def test_compressed_audio(client, tmp_path, extension, codec):
    target = tmp_path / ("encoded." + extension)
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(SAMPLE),
        "-c:a", codec, "-y", str(target),
    ], check=True, capture_output=True)
    response = client.post("/api/audio/analyze", files=[
        ("files", (target.name, target.read_bytes(), "application/octet-stream")),
    ])
    result = response.json()["results"][0]
    assert "error" not in result, result
    assert result["metadata"]["duration"] == pytest.approx(8, abs=0.2)
    assert result["metadata"]["sample_rate"] == 16000


@pytest.mark.parametrize("contents", [np.zeros(16000), np.ones(16000), np.array([])])
def test_silent_or_empty_audio_has_no_prediction(tmp_path, contents):
    path = tmp_path / "empty.wav"
    sf.write(path, contents, 16000)
    result = analyze_audio(str(path))
    assert result["classification"] == "error"
    assert result["synthetic_probability"] is None


def test_stereo_resampling(tmp_path):
    waveform, rate = sf.read(SAMPLE)
    path = tmp_path / "stereo.wav"
    sf.write(path, np.column_stack([waveform, waveform]), 32000)
    result = analyze_audio(str(path))
    assert "error" not in result
    assert result["metadata"]["duration"] == 4
    assert result["metadata"]["sample_rate"] == 16000


def test_visual_analysis_includes_terrain_and_waterfall_data():
    result = analyze_audio(str(SAMPLE))
    terrain = result["visual_analysis"]["terrain"]
    waterfall = result["visual_analysis"]["waterfall"]
    assert 100 <= terrain["n_time_bins"] <= 250
    assert 64 <= terrain["n_frequency_bins"] <= 128
    assert len(terrain["surface"]) == terrain["n_frequency_bins"]
    assert len(terrain["surface"][0]) == terrain["n_time_bins"]
    assert len(waterfall["frames"]) == terrain["n_time_bins"]
    assert "time_seconds" in terrain and "frequency_hz" in terrain
    assert result["visual_analysis"]["suspicious_regions"]


def test_model_result_and_model_failure(tmp_path):
    waveform, sample_rate = sf.read(SAMPLE)
    recording = tmp_path / "recording.wav"
    sf.write(recording, waveform * 0.7, sample_rate)
    class Detector:
        def predict_synthetic_probability(self, features):
            return 0.8

    class Manipulation:
        def predict_manipulation_type(self, features):
            return "voice_conversion"

    result = analyze_audio(str(recording), model=Detector(), manipulation_model=Manipulation())
    assert result["synthetic_likelihood"] == 80
    assert result["scoring_method"] == "trained_model"
    assert result["manipulation_type"] == "voice_conversion"

    class BrokenDetector:
        def predict_synthetic_probability(self, features):
            raise ValueError("Model is not fitted.")

    failed = analyze_audio(str(recording), model=BrokenDetector())
    assert failed["classification"] == "error"
    assert failed["synthetic_probability"] is None
    assert failed["error"] == "Model is not fitted."


def test_upload_limits_and_cleanup(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_FILE_BYTES", 4)
    response = client.post("/api/audio/analyze", files=[("files", ("large.wav", b"12345"))])
    result = response.json()["results"][0]
    assert result["classification"] == "error"
    assert result["synthetic_likelihood"] is None
    response = client.post("/api/audio/analyze", files=[("files", ("x.wav", b"1"))] * 21)
    assert response.status_code == 400
    assert client.post("/api/audio/analyze").status_code == 422


def test_upload_filename_is_not_a_server_path(client, monkeypatch):
    from audio_forensics import inference
    observed = []

    def inspect(path, **kwargs):
        observed.append(Path(path))
        assert Path(path).name == "0.wav"
        return inference.error_result("test")

    monkeypatch.setattr(inference, "analyze_audio", inspect)
    response = client.post("/api/audio/analyze", files=[("files", ("../../outside.wav", b"x"))])
    assert response.json()["results"][0]["filename"] == "outside.wav"
    assert not observed[0].exists()


def test_missing_file_and_invalid_parameters():
    assert analyze_audio("missing.wav")["synthetic_probability"] is None
    assert analyze_audio(str(SAMPLE), threshold=float("nan"))["classification"] == "error"
    assert analyze_audio(str(SAMPLE), hop_seconds=0)["classification"] == "error"
