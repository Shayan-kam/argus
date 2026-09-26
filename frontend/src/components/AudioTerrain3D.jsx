import { useEffect, useRef } from "react";
import { Camera, Geometry, Mesh, Orbit, Program, Renderer, Transform, Vec3 } from "ogl";

const HEAT_STOPS = [
    [8, 18, 36],
    [18, 68, 120],
    [40, 170, 190],
    [120, 220, 120],
    [255, 196, 64],
    [255, 245, 220],
];

function lerp(a, b, t) {
    return a + (b - a) * t;
}

function heatColor(value) {
    const t = Math.max(0, Math.min(1, Number(value) || 0));
    const scaled = t * (HEAT_STOPS.length - 1);
    const index = Math.floor(scaled);
    const next = Math.min(HEAT_STOPS.length - 1, index + 1);
    const local = scaled - index;
    return [
        lerp(HEAT_STOPS[index][0], HEAT_STOPS[next][0], local) / 255,
        lerp(HEAT_STOPS[index][1], HEAT_STOPS[next][1], local) / 255,
        lerp(HEAT_STOPS[index][2], HEAT_STOPS[next][2], local) / 255,
    ];
}

function buildTerrainGeometry(gl, surface) {
    const rows = surface.length;
    const cols = surface[0].length;
    const vertexCount = rows * cols;
    const positions = new Float32Array(vertexCount * 3);
    const colors = new Float32Array(vertexCount * 3);
    const normals = new Float32Array(vertexCount * 3);

    const width = 2.4;
    const depth = 1.8;
    const heightScale = 0.85;

    for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
            const index = row * cols + col;
            const value = Math.pow(Math.max(0, Number(surface[row][col]) || 0), 0.78);
            const x = (col / Math.max(1, cols - 1) - 0.5) * width;
            const z = (row / Math.max(1, rows - 1) - 0.5) * depth;
            const y = value * heightScale;
            positions[index * 3] = x;
            positions[index * 3 + 1] = y;
            positions[index * 3 + 2] = z;
            const [r, g, b] = heatColor(value);
            colors[index * 3] = r;
            colors[index * 3 + 1] = g;
            colors[index * 3 + 2] = b;
        }
    }

    // Smooth normals from neighboring heights.
    for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
            const index = row * cols + col;
            const left = positions[(row * cols + Math.max(0, col - 1)) * 3 + 1];
            const right = positions[(row * cols + Math.min(cols - 1, col + 1)) * 3 + 1];
            const down = positions[(Math.max(0, row - 1) * cols + col) * 3 + 1];
            const up = positions[(Math.min(rows - 1, row + 1) * cols + col) * 3 + 1];
            const dx = (right - left) * (cols / width);
            const dz = (up - down) * (rows / depth);
            let nx = -dx;
            let ny = 1.4;
            let nz = -dz;
            const length = Math.hypot(nx, ny, nz) || 1;
            normals[index * 3] = nx / length;
            normals[index * 3 + 1] = ny / length;
            normals[index * 3 + 2] = nz / length;
        }
    }

    const indices = new Uint32Array((rows - 1) * (cols - 1) * 6);
    let cursor = 0;
    for (let row = 0; row < rows - 1; row += 1) {
        for (let col = 0; col < cols - 1; col += 1) {
            const a = row * cols + col;
            const b = a + 1;
            const c = a + cols;
            const d = c + 1;
            indices[cursor++] = a;
            indices[cursor++] = c;
            indices[cursor++] = b;
            indices[cursor++] = b;
            indices[cursor++] = c;
            indices[cursor++] = d;
        }
    }

    return new Geometry(gl, {
        position: { size: 3, data: positions },
        normal: { size: 3, data: normals },
        color: { size: 3, data: colors },
        index: { data: indices },
    });
}

function buildGridGeometry(gl) {
    const lines = [];
    const halfW = 1.25;
    const halfD = 0.95;
    const steps = 8;

    for (let i = 0; i <= steps; i += 1) {
        const t = i / steps;
        const x = -halfW + t * halfW * 2;
        const z = -halfD + t * halfD * 2;
        lines.push(x, 0, -halfD, x, 0, halfD);
        lines.push(-halfW, 0, z, halfW, 0, z);
    }

    return new Geometry(gl, {
        position: { size: 3, data: new Float32Array(lines) },
    });
}

const terrainVertex = /* glsl */ `
attribute vec3 position;
attribute vec3 normal;
attribute vec3 color;
uniform mat4 modelViewMatrix;
uniform mat4 projectionMatrix;
uniform mat3 normalMatrix;
varying vec3 vColor;
varying vec3 vNormal;
varying float vHeight;

void main() {
  vColor = color;
  vNormal = normalize(normalMatrix * normal);
  vHeight = position.y;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const terrainFragment = /* glsl */ `
precision highp float;
varying vec3 vColor;
varying vec3 vNormal;
varying float vHeight;

void main() {
  vec3 lightDir = normalize(vec3(0.45, 1.0, 0.35));
  float diffuse = max(dot(normalize(vNormal), lightDir), 0.0);
  float ambient = 0.32;
  float rim = pow(1.0 - max(dot(normalize(vNormal), vec3(0.0, 0.0, 1.0)), 0.0), 2.0) * 0.12;
  vec3 lit = vColor * (ambient + diffuse * 0.78 + rim);
  lit += vec3(0.08, 0.07, 0.04) * smoothstep(0.35, 0.85, vHeight);
  gl_FragColor = vec4(lit, 1.0);
}
`;

const gridVertex = /* glsl */ `
attribute vec3 position;
uniform mat4 modelViewMatrix;
uniform mat4 projectionMatrix;
void main() {
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const gridFragment = /* glsl */ `
precision highp float;
void main() {
  gl_FragColor = vec4(0.42, 0.56, 0.72, 0.35);
}
`;

export default function AudioTerrain3D({ surface }) {
    const hostRef = useRef(null);

    useEffect(() => {
        const host = hostRef.current;
        if (!host || !surface?.length || !surface[0]?.length) {
            return undefined;
        }

        let disposed = false;
        let frame = 0;
        let renderer;
        let orbit;

        try {
            renderer = new Renderer({
                dpr: Math.min(window.devicePixelRatio || 1, 2),
                alpha: true,
                antialias: true,
                webgl: 1,
            });
        } catch {
            return undefined;
        }

        const { gl } = renderer;
        const canvas = gl.canvas;
        canvas.className = "audio-terrain-canvas";
        canvas.setAttribute("aria-label", "Interactive 3D terrain. Drag to rotate, scroll to zoom.");
        host.appendChild(canvas);

        const camera = new Camera(gl, { fov: 38, near: 0.1, far: 40 });
        camera.position.set(1.8, 1.35, 2.35);

        const scene = new Transform();
        orbit = new Orbit(camera, {
            element: canvas,
            target: new Vec3(0, 0.18, 0),
            ease: 0.2,
            inertia: 0.88,
            enablePan: true,
            enableZoom: true,
            zoomSpeed: 0.7,
            rotateSpeed: 0.45,
            minDistance: 1.1,
            maxDistance: 6.5,
            minPolarAngle: 0.18,
            maxPolarAngle: Math.PI * 0.48,
        });

        const terrainGeometry = buildTerrainGeometry(gl, surface);
        const terrainProgram = new Program(gl, {
            vertex: terrainVertex,
            fragment: terrainFragment,
            cullFace: null,
        });
        const terrain = new Mesh(gl, { geometry: terrainGeometry, program: terrainProgram });
        terrain.setParent(scene);

        const gridGeometry = buildGridGeometry(gl);
        const gridProgram = new Program(gl, {
            vertex: gridVertex,
            fragment: gridFragment,
            transparent: true,
            depthTest: true,
            cullFace: null,
        });
        const grid = new Mesh(gl, {
            geometry: gridGeometry,
            program: gridProgram,
            mode: gl.LINES,
        });
        grid.setParent(scene);

        const resize = () => {
            const width = host.clientWidth || 640;
            const height = host.clientHeight || 320;
            renderer.setSize(width, height);
            camera.perspective({ aspect: width / Math.max(height, 1) });
        };

        resize();
        const observer = new ResizeObserver(resize);
        observer.observe(host);

        const update = () => {
            if (disposed) return;
            frame = requestAnimationFrame(update);
            orbit.update();
            renderer.render({ scene, camera });
        };
        update();

        return () => {
            disposed = true;
            cancelAnimationFrame(frame);
            observer.disconnect();
            if (typeof orbit.remove === "function") {
                orbit.remove();
            }
            if (canvas.parentNode === host) {
                host.removeChild(canvas);
            }
            gl.getExtension("WEBGL_lose_context")?.loseContext();
        };
    }, [surface]);

    if (!surface?.length || !surface[0]?.length) {
        return null;
    }

    return (
        <div className="audio-terrain-3d">
            <div
                ref={hostRef}
                className="audio-terrain-stage"
                role="img"
                aria-label="Interactive 3D terrain of spectral magnitude"
            />
            <div className="audio-terrain-help">
                <span>Drag to rotate</span>
                <span>Scroll to zoom</span>
                <span>Right-drag or two-finger drag to pan</span>
            </div>
        </div>
    );
}
