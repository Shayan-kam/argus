import { useEffect, useRef, useState } from "react";
import { buildAudioCsv } from "./audioCsv";
import AudioResults from "./AudioResults";

const FORMATS = "audio/*,.wav,.mp3,.m4a,.aac,.flac,.ogg,.opus,.aiff,.aif,.wma,.webm";
const percent = (value) => Number.isFinite(value) ? value.toFixed(1) + "%" : "Unavailable";
const seconds = (value) => Number.isFinite(value) ? value.toFixed(2) + "s" : "Unavailable";

function fileLabel(result, file) {
    if (!result) return (file.size / 1024).toFixed(0) + " KB";
    if (result.error) return "Could not analyze";
    const score = Number(result.synthetic_likelihood);
    if (!Number.isFinite(score)) return "Unavailable";
    if (result.scoring_method === "experimental_baseline") return score.toFixed(1) + " / 100";
    return percent(score);
}

export default function AudioForensics({ apiBaseUrl }) {
    const [files, setFiles] = useState([]);
    const [urls, setUrls] = useState([]);
    const [results, setResults] = useState([]);
    const [active, setActive] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [status, setStatus] = useState(null);
    const [runtime, setRuntime] = useState(null);
    const [dragging, setDragging] = useState(false);
    const audioRef = useRef(null);
    const fileInputRef = useRef(null);
    const busyRef = useRef(false);

    useEffect(() => {
        const controller = new AbortController();
        const loadStatus = (attempt) => {
            fetch(apiBaseUrl + "/api/audio/status", { signal: controller.signal })
                .then(async (response) => {
                    if (!response.ok) throw new Error("Could not load audio service status.");
                    return response.json();
                })
                .then(setStatus)
                .catch((err) => {
                    if (err.name === "AbortError") return;
                    if (attempt < 3) {
                        window.setTimeout(() => loadStatus(attempt + 1), 800);
                        return;
                    }
                    setStatus({ available: false, notice: "Cannot reach the audio service. Start the backend and try again." });
                });
        };
        loadStatus(0);
        return () => controller.abort();
    }, [apiBaseUrl]);

    useEffect(() => {
        const nextUrls = files.map((file) => URL.createObjectURL(file));
        setUrls(nextUrls);
        return () => nextUrls.forEach((url) => URL.revokeObjectURL(url));
    }, [files]);

    useEffect(() => {
        const input = fileInputRef.current;
        if (!input) return;
        const transfer = new DataTransfer();
        files.forEach((file) => transfer.items.add(file));
        input.files = transfer.files;
    }, [files]);

    function validateFiles(nextFiles) {
        if (nextFiles.length === 0) return "Choose at least one audio file.";
        if (nextFiles.length > 20) return "Choose up to 20 audio files at a time.";
        if (nextFiles.some((file) => file.size > 50 * 1024 * 1024)) return "Each file must be 50 MB or smaller.";
        if (nextFiles.some((file) => file.size === 0)) return "One of the selected files is empty.";
        return "";
    }

    function selectFiles(nextFiles) {
        if (busyRef.current) return;
        const message = validateFiles(nextFiles);
        setError(message);
        if (message) return;
        setFiles(nextFiles);
        setResults([]);
        setRuntime(null);
        setActive(0);
    }

    async function runAnalysis(nextFiles) {
        const message = validateFiles(nextFiles);
        if (message) { setError(message); return; }
        setError("");
        setResults([]);
        setRuntime(null);
        setActive(0);
        const body = new FormData();
        nextFiles.forEach((file) => body.append("files", file));
        const response = await fetch(apiBaseUrl + "/api/audio/analyze", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Audio analysis failed.");
        setResults(data.results || []);
        setRuntime(data.total_seconds);
    }

    async function analyzeSelected() {
        if (busyRef.current) return;
        busyRef.current = true;
        setLoading(true);
        try { await runAnalysis(files); }
        catch (err) { setError(err.message || "Could not analyze audio."); }
        finally { busyRef.current = false; setLoading(false); }
    }

    async function tryDemo() {
        if (busyRef.current) return;
        busyRef.current = true;
        setLoading(true);
        setError("");
        try {
            const response = await fetch(apiBaseUrl + "/api/audio/sample");
            if (!response.ok) throw new Error("Could not load the demo recording.");
            const file = new File([await response.blob()], "argus-demo.wav", { type: "audio/wav" });
            setFiles([file]);
            await runAnalysis([file]);
        } catch (err) { setError(err.message || "Could not analyze the demo."); }
        finally { busyRef.current = false; setLoading(false); }
    }

    function downloadCsv() {
        const url = URL.createObjectURL(new Blob([buildAudioCsv(results)], { type: "text/csv;charset=utf-8;" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = "argus-audio-predictions.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function seekTo(time) {
        if (audioRef.current) {
            audioRef.current.currentTime = time;
            audioRef.current.focus();
        }
    }

    const result = results[active];
    const completed = results.filter((item) => !item.error).length;
    const notice = result?.notice || status?.notice;
    const scoringMethod = result?.scoring_method || status?.scoring_method;
    const statusLabel = scoringMethod === "trained_model" ? "Trained model" :
        scoringMethod === "experimental_baseline" ? "Preview mode" :
        status?.available === false ? "Service unavailable" : "Checking service...";

    return (
        <section className="audio-workspace" aria-labelledby="audio-heading">
            <div className="results-header" data-reveal>
                <div>
                    <p className="section-eyebrow">HEARSAY / AUDIO AUTHENTICATION</p>
                    <h2 id="audio-heading">Audio Forensics</h2>
                    <p className="results-subtitle">Understand your recording, explore possible changes, and review the evidence.</p>
                </div>
                <span className="chip chip-info">{statusLabel}</span>
            </div>

            <div className={"audio-upload insight-panel" + (dragging ? " is-dragging" : "")} data-reveal
                onDragOver={(event) => { event.preventDefault(); if (!loading) setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => { event.preventDefault(); setDragging(false); selectFiles(Array.from(event.dataTransfer.files)); }}>
                <label htmlFor="audio-files" className="audio-upload-label">Choose or drop audio files</label>
                <p id="audio-upload-help" className="muted">WAV, MP3, M4A, FLAC, OGG, and other decodable audio. Up to 20 files, 50 MB and 10 minutes each.</p>
                <div className="audio-file-picker">
                    <input id="audio-files" ref={fileInputRef} type="file" accept={FORMATS} multiple disabled={loading}
                        aria-describedby="audio-upload-help"
                        onChange={(event) => selectFiles(Array.from(event.target.files))} />
                    <span className="audio-file-picker-name">
                        {files.length === 0 ? "No file selected" : files.map((file) => file.name).join(", ")}
                    </span>
                </div>
                <div className="audio-actions">
                    <button className="primary-button" onClick={analyzeSelected} disabled={loading || !files.length}>
                        {loading ? "Analyzing audio..." : "Analyze Audio"}
                    </button>
                    <button className="secondary-button" onClick={tryDemo} disabled={loading}>Try demo recording</button>
                </div>
                <p className="audio-demo-note muted">No file handy? Try the demo: eight seconds of computer-generated tones.</p>
            </div>

            {!loading && results.length > 0 && (
                <p className="audio-complete" role="status">
                    Analysis complete. Scroll down for the results.
                </p>
            )}

            {notice && results.length === 0 && <p className="audio-notice" data-reveal role="status">{notice}</p>}
            {error && <div className="error" data-reveal role="alert">{error}</div>}

            {files.length > 0 && (
                <div className="audio-file-list" data-reveal aria-label="Selected audio files">
                    {files.map((file, index) => (
                        <button className={"audio-file secondary-button" + (active === index ? " is-active" : "")}
                            key={index} onClick={() => setActive(index)} aria-pressed={active === index} disabled={loading}>
                            <span>{file.name}</span>
                            <small>{fileLabel(results[index], file)}</small>
                        </button>
                    ))}
                </div>
            )}

            {files[active] && !loading && (
                <div className="audio-player insight-panel" data-reveal>
                    <label htmlFor="audio-preview">{files[active].name}</label>
                    <audio id="audio-preview" key={urls[active]} ref={audioRef} controls preload="metadata" src={urls[active]}>
                        Your browser does not support audio playback.
                    </audio>
                    <p className="muted">Listen to the original recording. If your browser cannot play this format, you can still analyze it.</p>
                </div>
            )}

            {loading && (
                <div className="loading-panel" data-reveal role="status" aria-live="polite">
                    <div className="loading-visual"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="core" /></div>
                    <div className="loading-copy"><h3>Examining your audio</h3><p>Checking sound patterns and comparing sections of the recording. The first analysis may take longer.</p></div>
                    <div className="loading-steps"><span className="step active">Read audio</span><span className="step active">Check patterns</span><span className="step active">Explain results</span></div>
                </div>
            )}

            {!loading && results.length > 0 && (
                <section className="results-section" aria-label="Audio analysis results">
                    <div className="results-header" data-reveal>
                        <div><p className="section-eyebrow">ANALYSIS COMPLETE</p><h2>Your audio, explained</h2>
                            <p className="results-subtitle">{completed} of {results.length} recordings checked in {seconds(runtime)}.</p></div>
                        <button className="primary-button" onClick={downloadCsv}>Download CSV Results</button>
                    </div>

                    {result?.error ? <div className="error" data-reveal role="alert">{result.filename}: {result.error}</div> : result && (
                        <AudioResults result={result} onSeek={seekTo} />
                    )}
                </section>
            )}
        </section>
    );
}
