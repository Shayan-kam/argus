# Audio Forensics

The Audio Forensics tab adds HEARSAY-style audio uploads, batch results, a 0–100
synthetic likelihood score, technique summaries, section playback, and CSV export.
The existing repository security scanner is preserved.

## Run

From the project root, install backend dependencies:

    python -m pip install -r backend/requirements.txt

Start the API from the backend directory:

    python -m uvicorn main:app --reload

In a second terminal, from the frontend directory:

    npm install
    npm run dev

Open the website, select **Audio Forensics**, then **Try demo recording** or choose
your own recordings. The first analysis can take longer while audio libraries
initialize.

## Sample and formats

sample.wav is an eight-second generated, modulated tone. It is a pipeline fixture,
not a real/fake speech benchmark or training data. The original manual check runs
from the project root:

    python backend/audio_forensics/test_audio.py

The server decodes WAV, MP3, M4A/AAC, FLAC, OGG, and other formats supported by
SoundFile or the bundled FFmpeg binary from imageio-ffmpeg. No separate FFmpeg
installation is required. Browser playback support varies by codec.

Limits are 20 files per request, 50 MB per file, and 10 minutes per recording.
Invalid, empty, silent, and oversized recordings return individual errors.
Uploads and intermediate decoded files are deleted after analysis.

## Scoring

The original development scoring formula is retained and clearly labeled
experimental. Its 0–100 output is **not a calibrated probability**. Signal,
frequency, MFCC, and temporal measurements run automatically; the baseline score
uses the original signal features. No pretrained speech model is included.

A trained local model can be supplied through ARGUS_AUDIO_MODEL or saved as
audio_forensics/trained_model.joblib. It must expose
predict_synthetic_probability(features), as DSPBaselineModel does. A joblib
dictionary with detector and optional manipulation entries supports a separate
ManipulationClassifier. Only load trusted, locally produced model artifacts.
Model failures are reported rather than silently falling back to the baseline.

The results lead with a plain-language summary, a review score out of 100 for the
experimental baseline, and a prominent manipulation assessment. The original
metrics and their definitions are available under Technical details.

The manipulation guide uses TTS, voice cloning/conversion, splicing/partial
synthesis, audio editing, fully synthetic speech, and real/unmodified. These
categories can overlap. All sections are assessed when a type model is supplied,
even when the overall synthetic score is low. A supported majority label is
reported as a prediction; mixed or unsupported labels remain inconclusive.
Real/unmodified and fully synthetic require agreement across every checked section;
conflicts with the overall detector are explained in the result summary.
A low synthetic score alone does not establish real/unmodified audio.

The exact built-in tone sample is identified by its fixed SHA-256 digest and
labeled Generated test audio with Known demo as its basis. Filename matching is
never used. Re-encoded or altered copies do not inherit that known-source label.
This source identity is separate from the experimental score; it is not a
detector finding or a claim that the tones are synthetic speech.

For other uploads without a type detector, the page explains why the type cannot
be established. Training and held-out evaluation on the challenge data are still
needed before making detection-accuracy claims.

## CSV

Download CSV Results exports all files, including failures, with these columns:

    filename,synthetic_likelihood,classification,manipulation_type,scoring_method,error,manipulation_label,manipulation_status,manipulation_basis

synthetic_likelihood is a percentage from 0 to 100. Failed files have a blank score,
classification error, and an error message. The challenge's exact submission
schema has not been provided; adapt these columns when it becomes available.
Potential spreadsheet formulas in text fields are escaped with a leading apostrophe.

## Tests

From the project root:

    python -m pip install -r backend/requirements-dev.txt
    python -m pytest backend/audio_forensics

These checks exercise real WAV, MP3, M4A, and FLAC decoding, multipart uploads,
partial failures, resampling, model errors, and the existing health endpoint.
They verify software behavior, not model accuracy.
