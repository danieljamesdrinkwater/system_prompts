import { useRef, useState, useEffect } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { animated, useSpring } from "@react-spring/three";
import { Text } from "@react-three/drei";
import { NoteBoard } from "./NoteBoard";
import { TextEditor } from "./TextEditor";
import { Timer } from "./Timer";
import { VolumetricPanel } from "./VolumetricPanel";
import { SpatialKeyboard } from "./SpatialKeyboard";
import {
  registerGazeTarget,
  unregisterGazeTarget,
} from "../hooks/useEyeTracking";
import { playSound } from "../hooks/useSpatialAudio";
import { usePanel } from "../hooks/usePanel";
import { useGestures } from "../hooks/useGestures";
import { lerp } from "../utils/spatial-math";
import type { Group, Mesh } from "three";
import { Vector3 } from "three";

export type PanelType = "note" | "editor" | "timer" | "volumetric" | "dashboard";

interface SpatialPanelProps {
  id: string;
  type: PanelType;
  initialPosition: [number, number, number];
  /** The panel ID currently being gazed at (from useEyeTracking) */
  gazeTarget?: string | null;
  onClose: () => void;
}

const PANEL_WIDTH = 0.6;
const PANEL_HEIGHT = 0.45;
const BAR_HEIGHT = 0.04;

/**
 * visionOS-style floating glass panel.
 *
 * Features:
 * - Frosted glass material (translucent with roughness)
 * - Bottom window bar for grab-to-move
 * - Close button ornament on hover
 * - Spring animations for open/close
 * - Draggable in 3D space
 * - Eye gaze interaction — border glow increases when gazed at
 * - Adaptive opacity — panels dim based on distance from camera
 * - Gesture integration — swipe dismiss, two-hand resize, pinch-rotate
 */
export function SpatialPanel({ id, type, initialPosition, gazeTarget, onClose }: SpatialPanelProps) {
  const groupRef = useRef<Group>(null);
  const panelRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const [closeHovered, setCloseHovered] = useState(false);
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const [editorText, setEditorText] = useState("");

  /** Whether this panel is currently being gazed at */
  const isGazed = gazeTarget === id;

  /** Distance-based opacity — smoothly interpolated each frame via lerp */
  const distanceOpacity = useRef(1.0);

  /** Reusable vector to avoid allocations in useFrame */
  const worldPosVec = useRef(new Vector3());

  const { camera } = useThree();

  // --- Gesture-aware panel management with bounce physics via usePanel ---
  const panel = usePanel({
    initialPosition,
    minY: 0.3,
    maxZ: 0.5,
    damping: 0.95,
    onDismiss: () => {
      playSound("panelClose", panel.position);
      onClose();
    },
  });

  // Wire gesture recognition into the panel's handlers.
  // Gestures only fire when the panel is hovered/focused to avoid
  // every panel responding to the same hand movement.
  useGestures({
    onSwipeDismiss: (isGazed || hovered) ? panel.handleSwipeDismiss : undefined,
    onTwoHandResize: (isGazed || hovered) ? panel.handleTwoHandResize : undefined,
    onPinchRotate: (isGazed || hovered) ? panel.handlePinchRotate : undefined,
  });

  // Play open sound when panel mounts
  useEffect(() => {
    playSound("panelOpen", initialPosition);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Register/unregister the panel mesh for gaze raycasting
  useEffect(() => {
    const mesh = panelRef.current;
    if (mesh) {
      registerGazeTarget(mesh.uuid, id);
      return () => unregisterGazeTarget(mesh.uuid);
    }
  }, [id]);

  // Spring animation for panel appearance
  const { scale, opacity } = useSpring({
    scale: panel.dismissed ? 0.3 : 1,
    opacity: panel.dismissed ? 0 : 1,
    from: { scale: 0.8, opacity: 0 },
    config: { mass: 1, tension: 200, friction: 20 },
  });

  // Close button spring
  const { closeScale } = useSpring({
    closeScale: closeHovered ? 1.2 : hovered ? 1 : 0,
    config: { mass: 0.5, tension: 300, friction: 15 },
  });

  // Hover glow intensity — boosted when gazed at (0.08 baseline -> 0.2 on gaze)
  const { glowIntensity } = useSpring({
    glowIntensity: isGazed ? 0.2 : hovered ? 0.15 : 0.08,
    config: { tension: 200, friction: 20 },
  });

  useFrame(() => {
    if (groupRef.current) {
      // Position is driven by usePanel (includes momentum + bounce physics)
      groupRef.current.position.set(...panel.position);

      // Apply gesture-driven rotation from usePanel
      groupRef.current.rotation.set(
        panel.rotation[0],
        panel.rotation[1],
        panel.rotation[2]
      );

      // Apply gesture-driven scale from usePanel
      const gestureScale = panel.scale[0];
      // The spring scale handles the open/close animation;
      // gesture scale is multiplicative (applied to the group's base)
      groupRef.current.userData.gestureScale = gestureScale;

      // --- Adaptive opacity based on distance from camera ---
      groupRef.current.getWorldPosition(worldPosVec.current);
      const dist = camera.position.distanceTo(worldPosVec.current);

      // Determine target opacity based on distance thresholds
      let targetOpacity: number;
      if (dist <= 0.5) {
        // Within arm's reach — full clarity
        targetOpacity = 1.0;
      } else if (dist <= 1.5) {
        // Mid range — slight fade (linear 1.0 -> 0.85)
        const t = (dist - 0.5) / 1.0;
        targetOpacity = 1.0 - t * 0.15;
      } else {
        // Far panels — dimmed to reduce visual clutter
        targetOpacity = 0.6;
      }

      // Smooth lerp towards target (0.08 factor for gentle ~12-frame transition)
      distanceOpacity.current = lerp(distanceOpacity.current, targetOpacity, 0.08);
    }
  });

  // Drag handlers now use usePanel's momentum system
  const handlePointerDown = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    panel.startDrag();
  };

  const handlePointerUp = () => {
    if (panel.isDragging) {
      panel.endDrag();
      playSound("panelSnap", panel.position);
    }
  };

  const handlePointerMove = (e: { point: { x: number; y: number; z: number }; stopPropagation: () => void }) => {
    if (panel.isDragging) {
      e.stopPropagation();
      panel.moveTo(e.point.x, e.point.y);
    }
  };

  const handleClose = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    playSound("panelClose", panel.position);
    onClose();
  };

  // Keyboard interaction for editor panels
  const handleEditorClick = () => {
    if (type === "editor" && !keyboardVisible) {
      setKeyboardVisible(true);
    }
  };

  const handleKeyboardType = (text: string) => {
    setEditorText(text);
  };

  const handleKeyboardDismiss = () => {
    setKeyboardVisible(false);
  };

  const renderContent = () => {
    const contentWidth = PANEL_WIDTH - 0.04;
    const contentHeight = PANEL_HEIGHT - BAR_HEIGHT - 0.04;

    switch (type) {
      case "note":
        return <NoteBoard width={contentWidth} height={contentHeight} />;
      case "editor":
        return <TextEditor width={contentWidth} height={contentHeight} />;
      case "timer":
        return <Timer width={contentWidth} height={contentHeight} />;
      case "volumetric":
        return <VolumetricPanel width={contentWidth} height={contentHeight} />;
      case "dashboard":
        return <DashboardContent width={contentWidth} height={contentHeight} />;
    }
  };

  return (
    <animated.group
      ref={groupRef}
      scale={scale.to((s) => s * panel.scale[0])}
      onPointerOver={() => {
        setHovered(true);
        playSound("hoverEnter", panel.position);
      }}
      onPointerOut={() => {
        setHovered(false);
        if (panel.isDragging) panel.endDrag();
      }}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      {/* Glass panel background — opacity modulated by distance */}
      <mesh ref={panelRef}>
        <planeGeometry args={[PANEL_WIDTH, PANEL_HEIGHT]} />
        <animated.meshPhysicalMaterial
          transparent
          opacity={opacity.to((o) => o * distanceOpacity.current)}
          color="#1a1a2e"
          metalness={0.1}
          roughness={0.3}
          transmission={0.6}
          thickness={0.02}
          envMapIntensity={0.5}
          clearcoat={1}
          clearcoatRoughness={0.1}
        />
      </mesh>

      {/* Glass border glow — enhanced on eye gaze */}
      <mesh position={[0, 0, -0.001]}>
        <planeGeometry args={[PANEL_WIDTH + 0.004, PANEL_HEIGHT + 0.004]} />
        <animated.meshBasicMaterial
          transparent
          opacity={glowIntensity}
          color="#ffffff"
        />
      </mesh>

      {/* Window bar (bottom) — visionOS grab handle */}
      <mesh
        position={[0, -(PANEL_HEIGHT / 2) + BAR_HEIGHT / 2, 0.001]}
        onPointerDown={handlePointerDown}
      >
        <planeGeometry args={[PANEL_WIDTH, BAR_HEIGHT]} />
        <meshPhysicalMaterial
          transparent
          opacity={0.3 * distanceOpacity.current}
          color="#ffffff"
          metalness={0}
          roughness={0.5}
        />
      </mesh>

      {/* Grab indicator dots on the bar */}
      {[-0.02, 0, 0.02].map((x, i) => (
        <mesh key={i} position={[x, -(PANEL_HEIGHT / 2) + BAR_HEIGHT / 2, 0.002]}>
          <circleGeometry args={[0.003, 16]} />
          <meshBasicMaterial color="#999999" transparent opacity={0.6 * distanceOpacity.current} />
        </mesh>
      ))}

      {/* Close button ornament (appears on hover) — visionOS style */}
      <animated.group
        position={[-(PANEL_WIDTH / 2) - 0.02, PANEL_HEIGHT / 2 + 0.02, 0]}
        scale={closeScale}
        onPointerOver={() => setCloseHovered(true)}
        onPointerOut={() => setCloseHovered(false)}
        onClick={handleClose}
      >
        <mesh>
          <circleGeometry args={[0.015, 24]} />
          <meshBasicMaterial
            color={closeHovered ? "#ff6b6b" : "#888888"}
            transparent
            opacity={0.9}
          />
        </mesh>
        {/* X mark */}
        <mesh rotation={[0, 0, Math.PI / 4]}>
          <planeGeometry args={[0.014, 0.002]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        <mesh rotation={[0, 0, -Math.PI / 4]}>
          <planeGeometry args={[0.014, 0.002]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </animated.group>

      {/* Panel content — click to open keyboard on editor panels */}
      <group position={[0, BAR_HEIGHT / 2, 0.002]} onClick={handleEditorClick}>
        {renderContent()}
      </group>

      {/* Spatial keyboard — appears below editor panels when activated */}
      {type === "editor" && (
        <SpatialKeyboard
          position={[0, -(PANEL_HEIGHT / 2) - 0.15, 0.02]}
          visible={keyboardVisible}
          onType={handleKeyboardType}
          onDismiss={handleKeyboardDismiss}
        />
      )}
    </animated.group>
  );
}

/**
 * Dashboard panel content — shows a simple status overview.
 * Placeholder for richer dashboard widgets.
 */
function DashboardContent({ width, height }: { width: number; height: number }) {
  const [time, setTime] = useState("");

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: true,
        })
      );
    };
    update();
    const interval = setInterval(update, 10000);
    return () => clearInterval(interval);
  }, []);

  const statItems = [
    { label: "Panels", value: "--", color: "#A3D9FF" },
    { label: "Focus", value: "--", color: "#BAFFC9" },
    { label: "Session", value: time, color: "#FFE066" },
  ];

  return (
    <group>
      {/* Title */}
      <Text
        position={[0, height / 2 - 0.02, 0.001]}
        fontSize={0.016}
        color="#ffffff"
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        Dashboard
      </Text>

      {/* Status cards */}
      {statItems.map((item, index) => {
        const x = (index - 1) * (width / 3);
        return (
          <group key={item.label} position={[x, 0, 0.001]}>
            {/* Card background */}
            <mesh>
              <planeGeometry args={[width / 3 - 0.01, 0.08]} />
              <meshPhysicalMaterial
                color={item.color}
                transparent
                opacity={0.15}
                roughness={0.4}
              />
            </mesh>
            {/* Value */}
            <Text
              position={[0, 0.01, 0.001]}
              fontSize={0.016}
              color={item.color}
              anchorX="center"
              anchorY="middle"
              font={undefined}
            >
              {item.value}
            </Text>
            {/* Label */}
            <Text
              position={[0, -0.02, 0.001]}
              fontSize={0.009}
              color="#888899"
              anchorX="center"
              anchorY="middle"
              font={undefined}
            >
              {item.label}
            </Text>
          </group>
        );
      })}
    </group>
  );
}
