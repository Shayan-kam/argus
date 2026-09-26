const decimal = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const rawNumber = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return "Unavailable";
    return Math.abs(number) > 0 && Math.abs(number) < 0.001
        ? number.toExponential(2) : number.toLocaleString(undefined, { maximumFractionDigits: 3 });
};
const timeLabel = (value) => Math.floor(value / 60) + ":" + String(Math.floor(value % 60)).padStart(2, "0");

const METRIC_HELP = {
    "RMS amplitude": "Typical signal strength after volume normalization, on a 0–1 scale.",
    "Crest factor": "How many times stronger the loudest peak is than the typical signal.",
    "Zero-crossing rate": "The share of adjacent sound samples that switch between positive and negative.",
    "Dominant frequency (Hz)": "The strongest tone in each section, averaged across sections.",
    "Spectral centroid (Hz)": "The center of the frequency range, weighted by signal strength.",
    "Spectral flatness": "Near 0 means more tone-like; near 1 means more noise-like. Neither proves manipulation.",
    "Mean first MFCC": "One number describing the sound's character. It has no standalone real/fake meaning.",
    "First MFCC variation": "How much that sound-character measurement changes across short windows.",
    "Quiet frame ratio": "The fraction of short windows below 5% of each section's loudest level.",
    "Energy variation": "How much short-window sound levels vary relative to their average.",
    "Spectral flux": "How much the balance of frequencies changes between neighboring windows.",
};

function SoundIcon({ kind = "sound" }) {
    const paths = {
        levels: <><path d="M4 10h4l5-4v12l-5-4H4z" /><path d="M17 8a6 6 0 0 1 0 8M20 5a10 10 0 0 1 0 14" /></>,
        tone: <><path d="M3 12c3-12 5 12 9 0s6 12 9 0" /></>,
        texture: <><path d="M4 7h16M4 12h16M4 17h16M8 4v6M15 9v6M11 14v6" /></>,
        timing: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
        sound: <><path d="M3 10v4M7 6v12M12 3v18M17 7v10M21 10v4" /></>,
    };
    return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[kind] || paths.sound}</svg>;
}

export default function AudioResults({ result, onSeek }) {
    const baseline = result.scoring_method === "experimental_baseline";
    const demo = result.source === "known_demo";
    const interpretation = result.interpretation;
    const manipulation = result.manipulation_assessment;
    const score = Number.isFinite(Number(result.synthetic_likelihood)) ? Number(result.synthetic_likelihood) : 0;
    const threshold = Number.isFinite(Number(result.threshold)) ? Number(result.threshold) * 100 : 50;
    const flagged = (result.suspicious_segments || []).length;

    return (
        <div className="audio-report">
            <section className="audio-verdict" data-reveal aria-labelledby="audio-verdict-title">
                <div className="audio-verdict-copy">
                    <div className="audio-kicker-row">
                        <p className="section-eyebrow">THE TAKEAWAY</p>
                        <span className="audio-status-pill">{demo ? "Known demo" : baseline ? "Preliminary check" : "Model estimate"}</span>
                    </div>
                    <h3 id="audio-verdict-title">{interpretation?.headline || "Review the audio results"}</h3>
                    <p>{interpretation?.explanation || result.notice}</p>
                    <div className="audio-facts">
                        <span><SoundIcon kind="timing" />{decimal.format(result.metadata?.duration || 0)} seconds</span>
                        <span><SoundIcon />{result.metadata?.num_segments || 0} sections checked</span>
                    </div>
                </div>
                <div className="audio-score-panel">
                    <span className="audio-score-label">{interpretation?.score_label || "Review score"}</span>
                    <div className="audio-score-ring" style={{ "--score-angle": (score * 3.6) + "deg" }}
                        role="img" aria-label={(baseline ? "Review score " : "Estimated synthetic likelihood ") + score + (baseline ? " out of 100, not a probability" : " percent")}>
                        <div><strong className="audio-score">{decimal.format(score)}{baseline ? "" : "%"}</strong><span>{baseline ? "out of 100" : "model estimate"}</span></div>
                    </div>
                    <span className="audio-score-caption">{baseline ? "A review aid, not a verdict" : "An estimate, not proof"}</span>
                </div>
                <details className="audio-score-help">
                    <summary>How to read this score</summary>
                    <p>{interpretation?.score_explanation || result.notice}</p>
                </details>
            </section>

            <section className="audio-type-panel insight-panel" data-reveal aria-labelledby="audio-type-heading">
                <div className="audio-panel-heading">
                    <div><p className="section-eyebrow">TYPE OF MANIPULATION</p>
                        <h3 id="audio-type-heading">{manipulation?.label || "Type not established"}</h3></div>
                    <span className={"audio-status-pill" + (manipulation?.status === "predicted" ? " is-predicted" : "")}>
                        {manipulation?.basis || "More evidence needed"}
                    </span>
                </div>
                <p className="audio-type-description">{manipulation?.description || "The current sound measurements do not identify how the recording was made."}</p>
                <p className="audio-type-reason">{manipulation?.explanation || "A synthetic score alone cannot distinguish TTS, voice cloning, or editing."}</p>
                {manipulation?.predicted_types?.length > 1 && (
                    <div className="audio-type-votes" aria-label="Type predictions by section">
                        {manipulation.predicted_types.map((type) => <span className="chip chip-muted" key={type.type}>{type.label}: {type.sections} sections</span>)}
                    </div>
                )}
                {manipulation?.categories && (
                    <details className="audio-type-guide">
                        <summary>What each manipulation type means <span>6 categories</span></summary>
                        <p className="muted">These definitions can overlap. TTS describes how speech is made; fully synthetic describes how much is generated. This guide does not mean each type was detected.</p>
                        <div className="audio-category-grid">
                            {manipulation.categories.map((category, index) => (
                                <div key={category.id} className={"audio-category" + (manipulation.type === category.id ? " is-selected" : "")}>
                                    <span className="audio-category-number">{String(index + 1).padStart(2, "0")}</span>
                                    <div><h4>{category.label}</h4><p>{category.description}</p>
                                        {manipulation.type === category.id && <span className="audio-category-match">Predicted type</span>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </details>
                )}
            </section>

            <section className="audio-observations" aria-labelledby="audio-observations-heading">
                <div className="audio-section-heading" data-reveal><p className="section-eyebrow">IN PLAIN LANGUAGE</p>
                    <h3 id="audio-observations-heading">What the sound tells us</h3>
                    <p>These observations describe the recording. They don't prove how it was made.</p></div>
                <div className="audio-observation-grid">
                    {(interpretation?.insights || []).map((insight) => (
                        <article className="audio-observation" data-reveal key={insight.id}>
                            <span className="audio-observation-icon"><SoundIcon kind={insight.id} /></span>
                            <div><p className="audio-observation-label">{insight.title}</p>
                                <h4>{insight.finding}</h4><p className="audio-observation-explanation">{insight.explanation}</p>
                            </div>
                        </article>
                    ))}
                </div>
            </section>

            <section className="insight-panel audio-timeline" data-reveal aria-labelledby="audio-timeline-heading">
                <div className="audio-panel-heading">
                    <div><p className="section-eyebrow">LISTEN FOR YOURSELF</p><h3 id="audio-timeline-heading">A closer look at the recording</h3></div>
                    <span className="audio-status-pill">{demo ? "Example review points" : flagged + " sections to review"}</span>
                </div>
                <p className="muted">Highlighted sections scored at least {decimal.format(threshold)} out of 100. Select a section to jump there. The sections overlap; they are not separate edits.</p>
                <div className="audio-waveform">
                    <svg viewBox="0 0 640 90" preserveAspectRatio="none" role="img" aria-label="Sound levels over the recording; taller bars mean louder peaks">
                        <line x1="0" y1="45" x2="640" y2="45" stroke="currentColor" opacity="0.16" />
                        {(result.waveform || []).map((peak, index) => <line key={index} x1={index * 4 + 2} x2={index * 4 + 2} y1={45 - peak * 36} y2={45 + peak * 36} stroke="currentColor" strokeWidth="2" />)}
                    </svg>
                    <div className="audio-waveform-scale"><span>0:00</span><span>Taller bars = louder sound</span><span>{timeLabel(result.metadata.duration)}</span></div>
                </div>
                <div className="audio-segments">
                    {(result.segments || []).map((segment, index) => (
                        <button key={index} className={"secondary-button audio-segment" + (segment.score >= result.threshold ? " is-suspicious" : "")}
                            onClick={() => onSeek(segment.start)}
                            aria-label={"Seek to " + segment.start + " seconds, score " + decimal.format(segment.score * 100) + " out of 100"}>
                            <span className="audio-segment-time">{timeLabel(segment.start)} – {timeLabel(segment.end)}</span>
                            <strong>{decimal.format(segment.score * 100)} <small>/ 100</small></strong>
                            <span className="audio-segment-action">{segment.score >= result.threshold ? "Review this section" : "Listen to this section"} <span aria-hidden="true">↗</span></span>
                        </button>
                    ))}
                </div>
            </section>

            <details className="audio-technical-details insight-panel" data-reveal>
                <summary><span>Technical details <small>Measurements and what they mean</small></span></summary>
                <p className="muted">Measured after converting to mono, adjusting volume, and using {(result.metadata?.sample_rate || 0).toLocaleString()} samples per second. These values describe the processed sound, not the original microphone volume.</p>
                <div className="insight-grid audio-technical-grid">
                    {(result.techniques || []).map((technique) => (
                        <section key={technique.name}>
                            <h4>{technique.name}</h4>
                            <dl className="audio-metrics">{Object.entries(technique.metrics || {}).map(([label, value]) => (
                                <div key={label}><dt>{label}<small>{METRIC_HELP[label]}</small></dt><dd>{rawNumber(value)}</dd></div>
                            ))}</dl>
                        </section>
                    ))}
                </div>
            </details>
        </div>
    );
}
