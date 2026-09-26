import { useEffect, useRef } from "react";
import { Renderer, Program, Mesh, Triangle } from "ogl";
import "./MoltenMetal.css";

const hexToRgb = (hex) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!result) return [1, 1, 1];
    return [
        parseInt(result[1], 16) / 255,
        parseInt(result[2], 16) / 255,
        parseInt(result[3], 16) / 255
    ];
};

const colorModeToFloat = (mode) => (mode === "ember" ? 1 : mode === "frost" ? 2 : 0);

const vertex = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragment = `#version 300 es
precision highp float;
uniform vec2 iResolution;
uniform float iTime;
uniform float uSpeed;
uniform float uScale;
uniform float uDetail;
uniform float uGlow;
uniform float uCoreSize;
uniform float uSwirl;
uniform float uFold;
uniform float uBlackPoint;
uniform float uBrightness;
uniform float uColorMode;
uniform float uGrain;
uniform float uGrainIntensity;
uniform float uOpacity;
uniform vec2 uMouse;
uniform float uMouseStrength;
uniform bool uEnableMouse;
uniform vec3 uColor1;
uniform vec3 uColor2;
uniform vec3 uColor3;
uniform vec3 uBackgroundColor;
uniform bool uLightMode;
out vec4 fragColor;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
  float time = iTime * uSpeed;
  vec2 p = uScale * ((gl_FragCoord.xy - 0.5 * iResolution.xy) / iResolution.y) - 0.5;

  vec2 drift = vec2(0.0);
  if (uEnableMouse) {
    drift = (uMouse - 0.5) * uMouseStrength * 2.0;
  }
  p += drift;

  vec2 i = p;
  float c = 0.0;
  float r = length(p + vec2(sin(time), sin(time * 0.3 + 5.0)) * 0.5);
  float d = length(p);
  float rot = d + time + p.x * uSwirl;

  float cosRot = cos(rot);
  mat2 warp = mat2(cos(rot - sin(time / 5.0)), sin(rot), -sin(cosRot - time), cosRot) * uFold;
  float glowCore = uGlow * uCoreSize;

  for (float n = 0.0; n < 8.0; n++) {
    if (n >= uDetail) break;
    p *= warp;
    float t = r - time / (n + 3.0);
    i -= p + vec2(cos(t - i.x - r) + sin(t + i.y), sin(t - i.y) + cos(t + i.x) + r);
    c += glowCore / length(vec2(sin(i.x + t), cos(i.y + t)));
  }

  c /= 6.0;

  float intensity = max(c - uBlackPoint, 0.0) * uBrightness;
  float g = clamp(intensity, 0.0, 1.0);

  float mid = 0.5;
  if (uColorMode > 1.5) {
    mid = 0.65;
  } else if (uColorMode > 0.5) {
    mid = 0.35;
  }

  vec3 col = mix(uColor1, uColor2, smoothstep(0.0, mid, g));
  col = mix(col, uColor3, smoothstep(mid, 1.0, g));

  float a = g;
  if (uGrain > 0.5) {
    float gr = hash(gl_FragCoord.xy + iTime);
    a += (gr - 0.5) * uGrainIntensity;
  }
  a = clamp(a, 0.0, 1.0) * uOpacity;
  if (uLightMode) {
    float signal = 1.0 - exp(-max(c, 0.0) * 6.5);
    float body = smoothstep(0.075, 0.68, signal);
    float ridge = smoothstep(0.42, 0.92, signal);

    vec3 lightCol = mix(uColor1, uColor2, smoothstep(0.08, 0.52, signal));
    lightCol = mix(lightCol, uColor3, smoothstep(0.52, 0.96, signal));
    lightCol = mix(lightCol, lightCol * 0.72, ridge * 0.24);

    float coverage = body * mix(0.2, 0.86, signal) * uOpacity;
    if (uGrain > 0.5) {
      float gr = hash(gl_FragCoord.xy + iTime);
      coverage += (gr - 0.5) * uGrainIntensity * body * 0.16;
    }
    fragColor = vec4(mix(uBackgroundColor, lightCol, clamp(coverage, 0.0, 0.92)), 1.0);
  } else {
    fragColor = vec4(col * a, a);
  }
}
`;

const ctxMap = new WeakMap();

const MoltenMetal = ({
    color1 = "#5227FF",
    color2 = "#FF9FFC",
    color3 = "#FFFFFF",
    speed = 0.35,
    scale = 4,
    detail = 3,
    glow = 1.6,
    coreSize = 0.1,
    swirl = 1,
    fold = -0.2,
    blackPoint = 0.05,
    brightness = 1.3,
    colorMode = "molten",
    grain = true,
    grainIntensity = 0.05,
    mouseInteraction = true,
    mouseStrength = 0.3,
    opacity = 1.0,
    backgroundColor = "#FFFFFF",
    lightMode = false,
    className = ""
}) => {
    const containerRef = useRef(null);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return undefined;

        const renderer = new Renderer({
            webgl: 2,
            alpha: true,
            premultipliedAlpha: true,
            antialias: false,
            dpr: Math.min(window.devicePixelRatio || 1, 2)
        });

        const gl = renderer.gl;
        gl.clearColor(0, 0, 0, 0);
        const canvas = gl.canvas;
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        canvas.style.display = "block";
        container.appendChild(canvas);

        const geometry = new Triangle(gl);
        const program = new Program(gl, {
            vertex,
            fragment,
            uniforms: {
                iTime: { value: 0 },
                iResolution: { value: new Float32Array([1, 1]) },
                uSpeed: { value: 0.35 },
                uScale: { value: 4 },
                uDetail: { value: 3 },
                uGlow: { value: 1.6 },
                uCoreSize: { value: 0.1 },
                uSwirl: { value: 1 },
                uFold: { value: -0.2 },
                uBlackPoint: { value: 0.05 },
                uBrightness: { value: 1.3 },
                uColorMode: { value: 0 },
                uGrain: { value: 1 },
                uGrainIntensity: { value: 0.05 },
                uOpacity: { value: 1.0 },
                uMouse: { value: new Float32Array([0.5, 0.5]) },
                uMouseStrength: { value: 0.3 },
                uEnableMouse: { value: true },
                uColor1: { value: new Float32Array([1, 1, 1]) },
                uColor2: { value: new Float32Array([1, 1, 1]) },
                uColor3: { value: new Float32Array([1, 1, 1]) },
                uBackgroundColor: { value: new Float32Array([1, 1, 1]) },
                uLightMode: { value: false }
            }
        });

        const mesh = new Mesh(gl, { geometry, program });
        ctxMap.set(container, { renderer, program, mesh });

        const setSize = () => {
            const rect = container.getBoundingClientRect();
            const width = Math.max(1, Math.floor(rect.width));
            const height = Math.max(1, Math.floor(rect.height));
            renderer.setSize(width, height);
            const resolution = program.uniforms.iResolution.value;
            resolution[0] = gl.drawingBufferWidth;
            resolution[1] = gl.drawingBufferHeight;
            renderer.render({ scene: mesh });
        };

        const resizeObserver = new ResizeObserver(setSize);
        resizeObserver.observe(container);
        setSize();

        const targetMouse = [0.5, 0.5];
        const currentMouse = [0.5, 0.5];

        const handleMouseMove = (event) => {
            const rect = canvas.getBoundingClientRect();
            targetMouse[0] = (event.clientX - rect.left) / rect.width;
            targetMouse[1] = 1.0 - (event.clientY - rect.top) / rect.height;
        };
        const handleMouseLeave = () => {
            targetMouse[0] = 0.5;
            targetMouse[1] = 0.5;
        };
        canvas.addEventListener("mousemove", handleMouseMove);
        canvas.addEventListener("mouseleave", handleMouseLeave);

        let frameId = 0;
        let isVisible = true;
        let isPageVisible = !document.hidden;
        const startTime = performance.now();

        const loop = (time) => {
            program.uniforms.iTime.value = (time - startTime) * 0.001;
            currentMouse[0] += 0.05 * (targetMouse[0] - currentMouse[0]);
            currentMouse[1] += 0.05 * (targetMouse[1] - currentMouse[1]);
            program.uniforms.uMouse.value[0] = currentMouse[0];
            program.uniforms.uMouse.value[1] = currentMouse[1];
            renderer.render({ scene: mesh });
            frameId = requestAnimationFrame(loop);
        };

        const tryStart = () => {
            if (isVisible && isPageVisible && frameId === 0) {
                frameId = requestAnimationFrame(loop);
            }
        };
        const tryStop = () => {
            if (frameId !== 0) {
                cancelAnimationFrame(frameId);
                frameId = 0;
            }
        };

        const intersectionObserver = new IntersectionObserver(([entry]) => {
            isVisible = entry.isIntersecting;
            isVisible ? tryStart() : tryStop();
        }, { threshold: 0 });
        intersectionObserver.observe(container);

        const handleVisibilityChange = () => {
            isPageVisible = !document.hidden;
            isPageVisible ? tryStart() : tryStop();
        };
        document.addEventListener("visibilitychange", handleVisibilityChange);
        tryStart();

        return () => {
            tryStop();
            resizeObserver.disconnect();
            intersectionObserver.disconnect();
            document.removeEventListener("visibilitychange", handleVisibilityChange);
            canvas.removeEventListener("mousemove", handleMouseMove);
            canvas.removeEventListener("mouseleave", handleMouseLeave);
            ctxMap.delete(container);
            if (canvas.parentNode === container) container.removeChild(canvas);
            gl.getExtension("WEBGL_lose_context")?.loseContext();
        };
    }, []);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        const context = ctxMap.get(container);
        if (!context) return;
        const uniforms = context.program.uniforms;

        uniforms.uSpeed.value = speed;
        uniforms.uScale.value = scale;
        uniforms.uDetail.value = detail;
        uniforms.uGlow.value = glow;
        uniforms.uCoreSize.value = Math.max(coreSize, 0.001);
        uniforms.uSwirl.value = swirl;
        uniforms.uFold.value = fold;
        uniforms.uBlackPoint.value = blackPoint;
        uniforms.uBrightness.value = brightness;
        uniforms.uColorMode.value = colorModeToFloat(colorMode);
        uniforms.uGrain.value = grain ? 1 : 0;
        uniforms.uGrainIntensity.value = grainIntensity;
        uniforms.uOpacity.value = opacity;
        uniforms.uMouseStrength.value = mouseStrength;
        uniforms.uEnableMouse.value = mouseInteraction;
        uniforms.uLightMode.value = lightMode;

        const firstColor = hexToRgb(color1);
        const secondColor = hexToRgb(color2);
        const thirdColor = hexToRgb(color3);
        const background = hexToRgb(backgroundColor);
        const uniformColor1 = uniforms.uColor1.value;
        const uniformColor2 = uniforms.uColor2.value;
        const uniformColor3 = uniforms.uColor3.value;
        uniformColor1[0] = firstColor[0];
        uniformColor1[1] = firstColor[1];
        uniformColor1[2] = firstColor[2];
        uniformColor2[0] = secondColor[0];
        uniformColor2[1] = secondColor[1];
        uniformColor2[2] = secondColor[2];
        uniformColor3[0] = thirdColor[0];
        uniformColor3[1] = thirdColor[1];
        uniformColor3[2] = thirdColor[2];
        uniforms.uBackgroundColor.value[0] = background[0];
        uniforms.uBackgroundColor.value[1] = background[1];
        uniforms.uBackgroundColor.value[2] = background[2];
    }, [
        color1,
        color2,
        color3,
        speed,
        scale,
        detail,
        glow,
        coreSize,
        swirl,
        fold,
        blackPoint,
        brightness,
        colorMode,
        grain,
        grainIntensity,
        mouseInteraction,
        mouseStrength,
        opacity,
        backgroundColor,
        lightMode
    ]);

    return <div ref={containerRef} className={`molten-metal-container ${className}`.trim()} />;
};

export default MoltenMetal;
