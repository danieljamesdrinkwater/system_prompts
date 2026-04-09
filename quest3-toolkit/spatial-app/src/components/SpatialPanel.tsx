import { useRef, useState, useEffect } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { animated, useSpring } from "@react-spring/three";
import { NoteBoard } from "./NoteBoard";
import { TextEditor } from "./TextEditor";
import { Timer } from "./Timer";
import { VolumetricPanel } from "./VolumetricPanel";
import {
  registerGazeTarget,
  unregisterGazeTarget,
} from "../hooks/useEyeTracking";
import { playSound } from "../hooks/useSpatialAudio";
import { lerp } from "../utils/spatial-math";
import type { Group, Mesh } from "three";
import { Vector3 } from "three";

interface SpatialPanelProps {
  id: string;
  type: "note" | "editor" | "timer" | "volumetric";
  initialPosition: [number, number, number];
  /** The panel ID currently being gazed at (from useEyeTracking) */
  gazeTarget?: string | null;
  onClose: () => void;
}

const PANEL_WIDTH = 0.6;
const PANEL_HEIGHT = 0.45;
const CORNER_RADIUS = 0.03;
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
 */
export function SpatialPanel({ id, type, initialPosition, gazeTarget, onClose }: SpatialPanelProps) {
  const groupRef = useRef<Group>(null);
  const panelRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState(initialPosition);
  const [closeHovered, setCloseHovered] = useState(false);

  /** Whether this panel is currently being gazed at */
  const isGazed = gazeTarget === id;

  /** Distance-based opacity — smoothly interpolated each frame via lerp */
  const distanceOpacity = useRef(1.0);

  /** Reusable vector to avoid allocations in useFrame */
  const worldPosVec = useRef(new Vector3());

  const { camera } = useThree();

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
    scale: 1,
    opacity: 1,
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
      groupRef.current.position.set(...position);

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

  const handlePointerDown = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    setDragging(true);
  };

  const handlePointerUp = () => {
    setDragging(false);
  };

  const handlePointerMove = (e: { point: { x: number; y: number; z: number }; stopPropagation: () => void }) => {
    if (dragging) {
      e.stopPropagation();
      setPosition([e.point.x, e.point.y, position[2]]);
    }
  };

  const handleClose = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    playSound("panelClose", position);
    onClose();
  };

  const renderContent = () => {
    switch (type) {
      case "note":
        return <NoteBoard width={PANEL_WIDTH - 0.04} height={PANEL_HEIGHT - BAR_HEIGHT - 0.04} />;
      case "editor":
        return <TextEditor width={PANEL_WIDTH - 0.04} height={PANEL_HEIGHT - BAR_HEIGHT - 0.04} />;
      case "timer":
        return <Timer width={PANEL_WIDTH - 0.04} height={PANEL_HEIGHT - BAR_HEIGHT - 0.04} />;
      case "volumetric":
        return <VolumetricPanel width={PANEL_WIDTH - 0.04} height={PANEL_HEIGHT - BAR_HEIGHT - 0.04} />;
    }
  };

  return (
    <animated.group
      ref={groupRef}
      scale={scale}
      onPointerOver={() => {
        setHovered(true);
        playSound("hoverEnter", position);
      }}
      onPointerOut={() => {
        setHovered(false);
        setDragging(false);
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

      {/* Panel content */}
      <group position={[0, BAR_HEIGHT / 2, 0.002]}>
        {renderContent()}
      </group>
    </animated.group>
  );
}
