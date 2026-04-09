import { useRef, useState, useMemo, useCallback, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import { animated, useSpring } from "@react-spring/three";
import type { Group, Mesh, CanvasTexture as ThreeCanvasTexture } from "three";
import { CanvasTexture } from "three";

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

interface SpatialKeyboardProps {
  /** Position in 3D space — typically below a text editor panel */
  position?: [number, number, number];
  /** Called on every keypress with the full accumulated text */
  onType: (text: string) => void;
  /** Called when the user dismisses the keyboard */
  onDismiss?: () => void;
  /** Whether the keyboard is visible */
  visible?: boolean;
}

interface KeyDef {
  label: string;
  /** Width multiplier relative to standard key width */
  width: number;
  /** Action type — character inserts the label, others are special */
  action: "char" | "space" | "backspace" | "enter" | "shift";
}

// ─────────────────────────────────────────────
// Layout
// ─────────────────────────────────────────────

const QWERTY_ROWS: KeyDef[][] = [
  // Row 0 — number row
  [
    { label: "1", width: 1, action: "char" },
    { label: "2", width: 1, action: "char" },
    { label: "3", width: 1, action: "char" },
    { label: "4", width: 1, action: "char" },
    { label: "5", width: 1, action: "char" },
    { label: "6", width: 1, action: "char" },
    { label: "7", width: 1, action: "char" },
    { label: "8", width: 1, action: "char" },
    { label: "9", width: 1, action: "char" },
    { label: "0", width: 1, action: "char" },
  ],
  // Row 1 — QWERTY
  [
    { label: "Q", width: 1, action: "char" },
    { label: "W", width: 1, action: "char" },
    { label: "E", width: 1, action: "char" },
    { label: "R", width: 1, action: "char" },
    { label: "T", width: 1, action: "char" },
    { label: "Y", width: 1, action: "char" },
    { label: "U", width: 1, action: "char" },
    { label: "I", width: 1, action: "char" },
    { label: "O", width: 1, action: "char" },
    { label: "P", width: 1, action: "char" },
  ],
  // Row 2 — ASDF
  [
    { label: "A", width: 1, action: "char" },
    { label: "S", width: 1, action: "char" },
    { label: "D", width: 1, action: "char" },
    { label: "F", width: 1, action: "char" },
    { label: "G", width: 1, action: "char" },
    { label: "H", width: 1, action: "char" },
    { label: "J", width: 1, action: "char" },
    { label: "K", width: 1, action: "char" },
    { label: "L", width: 1, action: "char" },
  ],
  // Row 3 — ZXCV + modifiers
  [
    { label: "Shift", width: 1.5, action: "shift" },
    { label: "Z", width: 1, action: "char" },
    { label: "X", width: 1, action: "char" },
    { label: "C", width: 1, action: "char" },
    { label: "V", width: 1, action: "char" },
    { label: "B", width: 1, action: "char" },
    { label: "N", width: 1, action: "char" },
    { label: "M", width: 1, action: "char" },
    { label: "Del", width: 1.5, action: "backspace" },
  ],
  // Row 4 — bottom row
  [
    { label: "Space", width: 5, action: "space" },
    { label: "Enter", width: 2, action: "enter" },
  ],
];

// ─────────────────────────────────────────────
// Dimensions
// ─────────────────────────────────────────────

const KEY_UNIT = 0.038; // base key width in metres
const KEY_HEIGHT = 0.034; // key height in metres
const KEY_DEPTH = 0.008; // key thickness (z)
const KEY_GAP = 0.004; // gap between keys
const KEY_RADIUS = 0.004; // visual corner radius (approximated via bevel)
const DEPRESS_Z = -0.005; // how far a pressed key sinks

/** Total keyboard width based on the widest row (row 0 = 10 keys) */
const KB_WIDTH = 10 * KEY_UNIT + 9 * KEY_GAP;
const KB_PADDING = 0.02;
const PREVIEW_HEIGHT = 0.032;

// ─────────────────────────────────────────────
// Canvas texture helper — renders text onto a 2D canvas
// for use as a material map on key meshes
// ─────────────────────────────────────────────

function createKeyTexture(
  label: string,
  width: number,
  height: number,
  options: {
    fontSize?: number;
    color?: string;
    bg?: string;
    highlighted?: boolean;
  } = {}
): CanvasTexture {
  const pxW = Math.max(64, Math.round(width * 2048));
  const pxH = Math.max(64, Math.round(height * 2048));
  const canvas = document.createElement("canvas");
  canvas.width = pxW;
  canvas.height = pxH;
  const ctx = canvas.getContext("2d")!;

  // Background — transparent so the mesh material shows through
  const bg = options.bg ?? "rgba(255,255,255,0.0)";
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, pxW, pxH);

  // Text
  const fontSize = options.fontSize ?? Math.round(pxH * 0.45);
  ctx.font = `500 ${fontSize}px -apple-system, "Helvetica Neue", sans-serif`;
  ctx.fillStyle = options.color ?? "#ffffff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, pxW / 2, pxH / 2);

  const tex = new CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

function createPreviewTexture(text: string, width: number, height: number): CanvasTexture {
  const pxW = Math.round(width * 2048);
  const pxH = Math.round(height * 2048);
  const canvas = document.createElement("canvas");
  canvas.width = pxW;
  canvas.height = pxH;
  const ctx = canvas.getContext("2d")!;

  ctx.fillStyle = "rgba(0,0,0,0)";
  ctx.fillRect(0, 0, pxW, pxH);

  const fontSize = Math.round(pxH * 0.4);
  ctx.font = `400 ${fontSize}px -apple-system, "Helvetica Neue", sans-serif`;
  ctx.fillStyle = "#e0e0ff";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";

  // Truncate from the left if too wide, showing the end of the string
  const maxW = pxW - 40;
  let display = text;
  let measured = ctx.measureText(display).width;
  while (measured > maxW && display.length > 1) {
    display = display.substring(1);
    measured = ctx.measureText(display).width;
  }
  if (display !== text) {
    display = "\u2026" + display;
  }

  ctx.fillText(display, 20, pxH / 2);

  // Blinking cursor indicator — always visible on preview
  const cursorX = 20 + ctx.measureText(display).width + 4;
  ctx.fillStyle = "#7777ff";
  ctx.fillRect(cursorX, pxH * 0.2, 2, pxH * 0.6);

  const tex = new CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

// ─────────────────────────────────────────────
// Individual Key Component
// ─────────────────────────────────────────────

function SpatialKey({
  keyDef,
  positionX,
  positionY,
  onPress,
  shifted,
}: {
  keyDef: KeyDef;
  positionX: number;
  positionY: number;
  onPress: (key: KeyDef) => void;
  shifted: boolean;
}) {
  const meshRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const [pressed, setPressed] = useState(false);

  const keyWidth = keyDef.width * KEY_UNIT + (keyDef.width - 1) * KEY_GAP;
  const isModifier = keyDef.action !== "char";

  // Determine display label
  const displayLabel = useMemo(() => {
    if (keyDef.action === "char") {
      return shifted ? keyDef.label.toUpperCase() : keyDef.label.toLowerCase();
    }
    if (keyDef.action === "backspace") return "\u232B";
    if (keyDef.action === "enter") return "\u23CE";
    if (keyDef.action === "shift") return shifted ? "\u21E7" : "\u21E7";
    if (keyDef.action === "space") return "";
    return keyDef.label;
  }, [keyDef, shifted]);

  // Canvas texture for the label
  const texture = useMemo(
    () => createKeyTexture(displayLabel, keyWidth, KEY_HEIGHT, {
      color: isModifier ? "#aaaacc" : "#ffffff",
    }),
    [displayLabel, keyWidth, isModifier]
  );

  // Spring for hover/press animation
  const { scaleVal, zOffset, emissiveIntensity } = useSpring({
    scaleVal: hovered ? 1.1 : 1.0,
    zOffset: pressed ? DEPRESS_Z : 0,
    emissiveIntensity: hovered ? 0.3 : 0.05,
    config: { mass: 0.3, tension: 400, friction: 20 },
  });

  const handlePointerDown = useCallback(
    (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      setPressed(true);
      onPress(keyDef);
    },
    [keyDef, onPress]
  );

  const handlePointerUp = useCallback(() => {
    setPressed(false);
  }, []);

  // Colour based on key type
  const baseColor = isModifier
    ? (keyDef.action === "shift" && shifted ? "#4444aa" : "#2a2a40")
    : "#222238";

  return (
    <animated.group
      position-x={positionX}
      position-y={positionY}
      position-z={zOffset}
      scale={scaleVal}
    >
      {/* Key mesh — rounded-box approximated with box + bevel */}
      <mesh
        ref={meshRef}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => {
          setHovered(false);
          setPressed(false);
        }}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
      >
        <boxGeometry args={[keyWidth, KEY_HEIGHT, KEY_DEPTH, 2, 2, 2]} />
        <animated.meshPhysicalMaterial
          color={baseColor}
          transparent
          opacity={0.85}
          metalness={0.05}
          roughness={0.35}
          transmission={0.15}
          clearcoat={0.8}
          clearcoatRoughness={0.2}
          emissive={hovered ? "#4444ff" : "#000000"}
          emissiveIntensity={emissiveIntensity}
        />
      </mesh>

      {/* Label overlay using canvas texture */}
      <mesh position={[0, 0, KEY_DEPTH / 2 + 0.0005]}>
        <planeGeometry args={[keyWidth * 0.9, KEY_HEIGHT * 0.9]} />
        <meshBasicMaterial map={texture} transparent opacity={0.95} depthWrite={false} />
      </mesh>
    </animated.group>
  );
}

// ─────────────────────────────────────────────
// Main Keyboard Component
// ─────────────────────────────────────────────

export function SpatialKeyboard({
  position = [0, 1.05, -0.9],
  onType,
  onDismiss,
  visible = true,
}: SpatialKeyboardProps) {
  const groupRef = useRef<Group>(null);
  const [text, setText] = useState("");
  const [shifted, setShifted] = useState(false);
  const [closeHovered, setCloseHovered] = useState(false);

  // Preview texture — updates when text changes
  const previewTexture = useMemo(
    () => createPreviewTexture(text || "Start typing...", KB_WIDTH, PREVIEW_HEIGHT),
    [text]
  );

  // Clean up textures on unmount
  useEffect(() => {
    return () => {
      previewTexture.dispose();
    };
  }, [previewTexture]);

  // Appearance spring
  const { kbScale, kbOpacity } = useSpring({
    kbScale: visible ? 1 : 0,
    kbOpacity: visible ? 1 : 0,
    config: { mass: 0.8, tension: 250, friction: 22 },
  });

  // Close button spring
  const { closeScale } = useSpring({
    closeScale: closeHovered ? 1.3 : 1.0,
    config: { mass: 0.4, tension: 350, friction: 15 },
  });

  const handleKeyPress = useCallback(
    (keyDef: KeyDef) => {
      let newText = text;

      switch (keyDef.action) {
        case "char": {
          const char = shifted ? keyDef.label.toUpperCase() : keyDef.label.toLowerCase();
          newText = text + char;
          if (shifted) setShifted(false); // auto-release shift after one char
          break;
        }
        case "space":
          newText = text + " ";
          break;
        case "backspace":
          newText = text.slice(0, -1);
          break;
        case "enter":
          newText = text + "\n";
          break;
        case "shift":
          setShifted((s) => !s);
          return; // don't call onType for shift toggle
      }

      setText(newText);
      onType(newText);
    },
    [text, shifted, onType]
  );

  const handleDismiss = useCallback(
    (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      onDismiss?.();
    },
    [onDismiss]
  );

  // Calculate total keyboard height for background panel
  const totalRows = QWERTY_ROWS.length;
  const kbHeight = totalRows * (KEY_HEIGHT + KEY_GAP) + PREVIEW_HEIGHT + KB_PADDING * 3;

  // Compute row positions
  const rowPositions = useMemo(() => {
    return QWERTY_ROWS.map((row, rowIndex) => {
      // Total width of this row
      const totalWidth = row.reduce(
        (sum, k) => sum + k.width * KEY_UNIT + (k.width - 1) * KEY_GAP,
        0
      ) + (row.length - 1) * KEY_GAP;

      // Y position — top to bottom
      const y =
        kbHeight / 2 -
        KB_PADDING -
        PREVIEW_HEIGHT -
        KB_PADDING -
        rowIndex * (KEY_HEIGHT + KEY_GAP) -
        KEY_HEIGHT / 2;

      // Compute each key's x position
      let cursor = -totalWidth / 2;
      const keys = row.map((keyDef) => {
        const keyWidth = keyDef.width * KEY_UNIT + (keyDef.width - 1) * KEY_GAP;
        const x = cursor + keyWidth / 2;
        cursor += keyWidth + KEY_GAP;
        return { keyDef, x, y };
      });

      return keys;
    });
  }, [kbHeight]);

  if (!visible) return null;

  return (
    <animated.group
      ref={groupRef}
      position={position}
      scale={kbScale}
    >
      {/* Glass background panel */}
      <mesh position={[0, 0, -KEY_DEPTH / 2 - 0.001]}>
        <planeGeometry args={[KB_WIDTH + KB_PADDING * 2, kbHeight]} />
        <animated.meshPhysicalMaterial
          color="#0d0d1a"
          transparent
          opacity={kbOpacity.to((v: number) => v * 0.65)}
          metalness={0.05}
          roughness={0.25}
          transmission={0.5}
          thickness={0.01}
          clearcoat={1}
          clearcoatRoughness={0.1}
        />
      </mesh>

      {/* Border glow */}
      <mesh position={[0, 0, -KEY_DEPTH / 2 - 0.002]}>
        <planeGeometry args={[KB_WIDTH + KB_PADDING * 2 + 0.004, kbHeight + 0.004]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.06} />
      </mesh>

      {/* Text preview bar */}
      <group position={[0, kbHeight / 2 - KB_PADDING - PREVIEW_HEIGHT / 2, 0]}>
        {/* Preview background */}
        <mesh>
          <planeGeometry args={[KB_WIDTH, PREVIEW_HEIGHT]} />
          <meshPhysicalMaterial
            color="#111122"
            transparent
            opacity={0.5}
            roughness={0.4}
            clearcoat={0.6}
          />
        </mesh>
        {/* Preview text via canvas texture */}
        <mesh position={[0, 0, 0.001]}>
          <planeGeometry args={[KB_WIDTH - 0.01, PREVIEW_HEIGHT - 0.006]} />
          <meshBasicMaterial
            map={previewTexture}
            transparent
            opacity={0.95}
            depthWrite={false}
          />
        </mesh>
      </group>

      {/* Keyboard keys */}
      {rowPositions.map((rowKeys, rowIndex) =>
        rowKeys.map(({ keyDef, x, y }, keyIndex) => (
          <SpatialKey
            key={`${rowIndex}-${keyIndex}`}
            keyDef={keyDef}
            positionX={x}
            positionY={y}
            onPress={handleKeyPress}
            shifted={shifted}
          />
        ))
      )}

      {/* Close / dismiss button — top-right */}
      <animated.group
        position={[KB_WIDTH / 2 + KB_PADDING + 0.01, kbHeight / 2 - 0.015, 0]}
        scale={closeScale}
        onPointerOver={() => setCloseHovered(true)}
        onPointerOut={() => setCloseHovered(false)}
        onClick={handleDismiss}
      >
        <mesh>
          <circleGeometry args={[0.013, 24]} />
          <meshBasicMaterial
            color={closeHovered ? "#ff6b6b" : "#666666"}
            transparent
            opacity={0.9}
          />
        </mesh>
        {/* X mark */}
        <mesh rotation={[0, 0, Math.PI / 4]} position={[0, 0, 0.001]}>
          <planeGeometry args={[0.012, 0.002]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        <mesh rotation={[0, 0, -Math.PI / 4]} position={[0, 0, 0.001]}>
          <planeGeometry args={[0.012, 0.002]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </animated.group>
    </animated.group>
  );
}
