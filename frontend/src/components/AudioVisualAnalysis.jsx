import { useEffect, useMemo, useRef, useState } from "react";
import AudioTerrain3D from "./AudioTerrain3D";

const timeLabel = (value) => {
    const seconds = Number(value) || 0;
    return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
};

const hzLabel = (value) => {
    const hz = Number(value) || 0;
    if (hz >= 1000) return `${(hz / 1000).toFixed(hz >= 10000 ? 0 : 1)} kHz`;
    return `${Math.round(hz)} Hz`;
};

function lerp(a, b, t) {
    return a + (b - a) * t;
}

function mixColor(a, b, t) {
    return [
        Math.round(lerp(a[0], b[0], t)),
        Math.round(lerp(a[1], b[1], t)),
        Math.round(lerp(a[2], b[2], t)),
    ];
}

// Quiet → strong: deep navy, cyan, lime, amber, white
const HEAT_STOPS = [
    [8, 18, 36],
    [18, 68, 120],
    [40, 170, 190],
    [120, 220, 120],
    [255, 196, 64],
    [255, 245, 220],
];

function heatRgb(value) {
    const t = Math.max(0, Math.min(1, Number(value) || 0));
    const scaled = t * (HEAT_STOPS.length - 1);
    const index = Math.floor(scaled);
    const next = Math.min(HEAT_STOPS.length - 1, index + 1);
    const local = scaled - index;
    return mixColor(HEAT_STOPS[index], HEAT_STOPS[next], local);
}

function percentile(sorted, p) {
    if (!sorted.length) return 0;
    const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * p)));
    return sorted[index];
}

function contrastStretch(grid, lowP = 0.05, highP = 0.98) {
    if (!grid.length || !grid[0]?.length) return [];

    const values = [];
    for (const row of grid) {
        for (const cell of row) {
            const value = Number(cell);
            if (Number.isFinite(value) && value > 0) values.push(value);
        }
    }

    if (!values.length) {
        return grid.map((row) => row.map(() => 0));
    }

    values.sort((a, b) => a - b);
    const low = percentile(values, lowP);
    const high = Math.max(low + 1e-9, percentile(values, highP));
    const span = high - low;

    return grid.map((row) => row.map((cell) => {
        const value = Number(cell) || 0;
        if (value <= 0) return 0;
        return Math.max(0, Math.min(1, (value - low) / span));
    }));
}

function activeFrequencyEnd(profile, keep = 0.995) {
    const total = profile.reduce((sum, value) => sum + value, 0);
    if (total <= 0) return profile.length;

    let cumulative = 0;
    let end = 0;
    for (let index = 0; index < profile.length; index += 1) {
        cumulative += profile[index];
        end = index + 1;
        if (cumulative / total >= keep) break;
    }

    // Keep a little headroom above the active band so the map does not look clipped.
    return Math.min(profile.length, Math.max(8, Math.ceil(end * 1.25)));
}

function cropSpectrogramRows(grid) {
    if (!grid.length) return grid;
    const profile = grid.map((row) => row.reduce((sum, value) => sum + (Number(value) || 0), 0));
    const end = activeFrequencyEnd(profile);
    return grid.slice(0, end);
}

function cropWaterfallCols(grid) {
    if (!grid.length || !grid[0]?.length) return grid;
    const cols = grid[0].length;
    const profile = Array.from({ length: cols }, (_, col) => (
        grid.reduce((sum, row) => sum + (Number(row[col]) || 0), 0)
    ));
    const end = activeFrequencyEnd(profile);
    return grid.map((row) => row.slice(0, end));
}

function cropTerrainRows(grid) {
    return cropSpectrogramRows(grid);
}

function downsampleGrid(grid, maxRows = 120, maxCols = 220) {
    if (!Array.isArray(grid) || !grid.length || !Array.isArray(grid[0])) {
        return [];
    }

    const rows = grid.length;
    const cols = grid[0].length;
    const outRows = Math.min(rows, maxRows);
    const outCols = Math.min(cols, maxCols);
    const next = [];

    for (let outRow = 0; outRow < outRows; outRow += 1) {
        const rowStart = Math.floor((outRow / outRows) * rows);
        const rowEnd = Math.max(rowStart + 1, Math.floor(((outRow + 1) / outRows) * rows));
        const line = [];
        for (let outCol = 0; outCol < outCols; outCol += 1) {
            const colStart = Math.floor((outCol / outCols) * cols);
            const colEnd = Math.max(colStart + 1, Math.floor(((outCol + 1) / outCols) * cols));
            let peak = 0;
            for (let row = rowStart; row < rowEnd; row += 1) {
                for (let col = colStart; col < colEnd; col += 1) {
                    peak = Math.max(peak, Number(grid[row][col]) || 0);
                }
            }
            line.push(peak);
        }
        next.push(line);
    }

    return next;
}

function drawHeatmap(canvas, grid, options = {}) {
    const {
        flipY = true,
        regions = [],
        duration = 0,
        widthHint = 900,
        heightHint = 280,
    } = options;

    if (!canvas || !grid.length || !grid[0]?.length) {
        return;
    }

    const rows = grid.length;
    const cols = grid[0].length;
    const width = Math.max(cols, widthHint);
    const height = Math.max(rows, heightHint);
    const dpr = window.devicePixelRatio || 1;

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = "100%";
    canvas.style.height = "100%";

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const image = ctx.createImageData(canvas.width, canvas.height);
    const data = image.data;
    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    for (let row = 0; row < rows; row += 1) {
        const sourceRow = flipY ? rows - 1 - row : row;
        const y0 = Math.floor(row * cellH);
        const y1 = Math.floor((row + 1) * cellH);
        for (let col = 0; col < cols; col += 1) {
            const [r, g, b] = heatRgb(grid[sourceRow][col]);
            const x0 = Math.floor(col * cellW);
            const x1 = Math.floor((col + 1) * cellW);
            for (let y = y0; y < y1; y += 1) {
                let offset = (y * canvas.width + x0) * 4;
                for (let x = x0; x < x1; x += 1) {
                    data[offset] = r;
                    data[offset + 1] = g;
                    data[offset + 2] = b;
                    data[offset + 3] = 255;
                    offset += 4;
                }
            }
        }
    }

    ctx.putImageData(image, 0, 0);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    if (duration > 0 && Array.isArray(regions) && regions.length) {
        regions.forEach((region) => {
            const start = Math.max(0, Number(region.start_time) || 0);
            const end = Math.max(start, Number(region.end_time) || start);
            const x = (start / duration) * width;
            const w = Math.max(3, ((end - start) / duration) * width);
            ctx.fillStyle = "rgba(255, 214, 102, 0.16)";
            ctx.fillRect(x, 0, w, height);
            ctx.strokeStyle = "rgba(255, 214, 102, 0.95)";
            ctx.lineWidth = 2;
            ctx.strokeRect(x + 1, 1, w - 2, height - 2);
        });
    }
}

function ColorLegend() {
    return (
        <div className="audio-visual-legend" aria-hidden="true">
            <span>Quiet</span>
            <div className="audio-visual-legend-bar" />
            <span>Strong</span>
        </div>
    );
}

function ChartFrame({ title, howToRead, children, footer, wide = false }) {
    return (
        <article className={`audio-visual-card${wide ? " is-wide" : ""}`}>
            <div className="audio-visual-card-copy">
                <div>
                    <h4>{title}</h4>
                    <p>{howToRead}</p>
                </div>
                <ColorLegend />
            </div>
            <div className="audio-visual-canvas-wrap">{children}</div>
            {footer}
        </article>
    );
}

export default function AudioVisualAnalysis({ visual, duration = 0, onSeek }) {
    const spectrogramRef = useRef(null);
    const waterfallRef = useRef(null);
    const [activeBand, setActiveBand] = useState(null);

    const regions = visual?.suspicious_regions || [];
    const bands = visual?.frequency_bands || [];
    const totalDuration = duration || (visual?.terrain?.time_seconds?.at?.(-1) ?? 0);

    const spectrogramGrid = useMemo(() => {
        let source = [];
        if (Array.isArray(visual?.terrain?.surface) && visual.terrain.surface.length) {
            source = downsampleGrid(visual.terrain.surface, 140, 280);
        } else if (Array.isArray(visual?.spectrogram?.db) && visual.spectrogram.db.length) {
            const db = downsampleGrid(visual.spectrogram.db, 110, 240);
            const minDb = Number(visual.spectrogram.min_db) || -80;
            const maxDb = Number(visual.spectrogram.max_db) || 0;
            const span = Math.max(1, maxDb - minDb);
            source = db.map((row) => row.map((value) => (Number(value) - minDb) / span));
        }
        return contrastStretch(cropSpectrogramRows(source));
    }, [visual]);

    const waterfallGrid = useMemo(() => {
        let source = [];
        if (Array.isArray(visual?.waterfall?.frames) && visual.waterfall.frames.length) {
            source = downsampleGrid(visual.waterfall.frames, 240, 140);
        } else if (spectrogramGrid.length) {
            source = spectrogramGrid[0].map((_, col) => spectrogramGrid.map((row) => row[col]));
            return contrastStretch(source);
        }
        return contrastStretch(cropWaterfallCols(source));
    }, [visual, spectrogramGrid]);

    const terrainSurface = useMemo(() => {
        if (!Array.isArray(visual?.terrain?.surface) || !visual.terrain.surface.length) {
            return [];
        }
        return contrastStretch(cropTerrainRows(downsampleGrid(visual.terrain.surface, 72, 140)));
    }, [visual]);

    const displayFreqMax = useMemo(() => {
        const freqs = visual?.terrain?.frequency_hz || visual?.spectrogram?.frequencies_hz || [];
        const fullMax = freqs.at?.(-1) ?? 0;
        const sourceRows = visual?.terrain?.surface?.length || freqs.length || 1;
        if (!Array.isArray(freqs) || !freqs.length || !spectrogramGrid.length) {
            return fullMax;
        }
        const croppedIndex = Math.min(
            freqs.length - 1,
            Math.max(0, Math.round(((spectrogramGrid.length - 1) / Math.max(1, sourceRows - 1)) * (freqs.length - 1)))
        );
        return Number(freqs[croppedIndex]) || fullMax;
    }, [visual, spectrogramGrid]);

    useEffect(() => {
        drawHeatmap(spectrogramRef.current, spectrogramGrid, {
            flipY: true,
            regions,
            duration: totalDuration,
            widthHint: 960,
            heightHint: 300,
        });
    }, [spectrogramGrid, regions, totalDuration]);

    useEffect(() => {
        drawHeatmap(waterfallRef.current, waterfallGrid, {
            flipY: false,
            regions: [],
            duration: 0,
            widthHint: 720,
            heightHint: 340,
        });
    }, [waterfallGrid]);

    if (!visual || (!spectrogramGrid.length && !waterfallGrid.length && !terrainSurface.length)) {
        return null;
    }

    const freqMax = displayFreqMax;

    return (
        <section className="insight-panel audio-visual-panel" data-reveal aria-labelledby="audio-visual-heading">
            <div className="audio-panel-heading">
                <div>
                    <p className="section-eyebrow">FREQUENCY VIEWS</p>
                    <h3 id="audio-visual-heading">See the sound across time and pitch</h3>
                </div>
                <span className="audio-status-pill">
                    {regions.length ? `${regions.length} review overlays` : "Sound maps"}
                </span>
            </div>
            <p className="muted">
                Bright colors mean stronger sound. Dark areas are quieter. Yellow outlines mark sections worth a closer listen. These maps describe the recording; they do not prove it was altered.
            </p>

            {bands.length > 0 && (
                <div className="audio-band-bars" aria-label="Energy by frequency band">
                    {bands.map((band) => {
                        const percent = Math.max(0, Math.min(100, Number(band.energy_percent) || 0));
                        const selected = activeBand === band.label;
                        return (
                            <button
                                key={band.label}
                                type="button"
                                className={`audio-band-bar${selected ? " is-active" : ""}`}
                                onClick={() => setActiveBand(selected ? null : band.label)}
                                aria-pressed={selected}
                            >
                                <span className="audio-band-label">{band.label}</span>
                                <span className="audio-band-track" aria-hidden="true">
                                    <span style={{ width: `${percent}%` }} />
                                </span>
                                <strong>{percent.toFixed(1)}%</strong>
                                <small>{hzLabel(band.low_hz)} – {hzLabel(band.high_hz)}</small>
                            </button>
                        );
                    })}
                </div>
            )}

            <div className="audio-visual-stack">
                <ChartFrame
                    wide
                    title="Spectrogram"
                    howToRead="Read left to right through the recording. The view zooms into the pitch range where most sound energy sits, so tones are easier to see. Hot colors are louder."
                    footer={(
                        <div className="audio-visual-scale">
                            <span>Start {timeLabel(0)}</span>
                            <span>Time →</span>
                            <span>End {timeLabel(totalDuration)}</span>
                        </div>
                    )}
                >
                    <canvas ref={spectrogramRef} role="img" aria-label="Spectrogram of the recording" />
                    <div className="audio-visual-axis audio-visual-axis-y">
                        <span>{hzLabel(freqMax)}</span>
                        <span>Low pitch</span>
                        <span>0 Hz</span>
                    </div>
                </ChartFrame>

                <ChartFrame
                    title="Waterfall"
                    howToRead="Time moves downward. Each row is one moment. Bright streaks show tones that continue or change."
                    footer={(
                        <div className="audio-visual-scale">
                            <span>Low pitch</span>
                            <span>Time ↓</span>
                            <span>High pitch</span>
                        </div>
                    )}
                >
                    <canvas ref={waterfallRef} role="img" aria-label="Waterfall frequency view" />
                </ChartFrame>

                {terrainSurface.length > 0 && (
                    <ChartFrame
                        wide
                        title="Terrain"
                        howToRead="Grab and drag to spin the 3D surface. Scroll to zoom. Taller ridges mean stronger sound at that pitch and time."
                        footer={(
                            <div className="audio-visual-scale">
                                <span>Time →</span>
                                <span>Height = strength</span>
                                <span>Pitch ↗</span>
                            </div>
                        )}
                    >
                        <AudioTerrain3D surface={terrainSurface} />
                    </ChartFrame>
                )}
            </div>

            {regions.length > 0 && (
                <div className="audio-visual-regions">
                    <p className="audio-visual-regions-label">Jump to a highlighted review section</p>
                    <div className="audio-visual-region-list">
                        {regions.map((region, index) => (
                            <button
                                key={`${region.start_time}-${region.end_time}-${index}`}
                                type="button"
                                className="secondary-button audio-visual-region"
                                onClick={() => onSeek?.(region.start_time)}
                            >
                                <span>{timeLabel(region.start_time)} – {timeLabel(region.end_time)}</span>
                                {Number.isFinite(Number(region.score)) && (
                                    <strong>{Math.round(Number(region.score) * 100)} / 100</strong>
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </section>
    );
}
