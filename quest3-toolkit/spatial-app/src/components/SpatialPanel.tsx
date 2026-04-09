import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { animated, useSpring } from "@react-spring/three";
import { NoteBoard } from "./NoteBoard";
import { TextEditor } from "./TextEditor";
import { Timer } from "./Timer";
import type { Group, Mesh } from "three";

interface SpatialPanelProps {
  id: string;
  type: "note" | "editor" | "timer";
  initialPosition: [number, number, number];
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
 */
export function SpatialPanel({ id, type, initialPosition, onClose }: SpatialPanelProps) {
  const groupRef = useRef<Group>(null);
  const panelRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState(initialPosition);
  const [closeHovered, setCloseHovered] = useState(false);

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

  // Hover glow intensity
  const { glowIntensity } = useSpring({
    glowIntensity: hovered ? 0.15 : 0.05,
    config: { tension: 200, friction: 20 },
  });

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.position.set(...position);
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
    }
  };

  return (
    <animated.group
      ref={groupRef}
      scale={scale}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => {
        setHovered(false);
        setDragging(false);
      }}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      {/* Glass panel background */}
      <mesh ref={panelRef}>
        <planeGeometry args={[PANEL_WIDTH, PANEL_HEIGHT]} />
        <animated.meshPhysicalMaterial
          transparent
          opacity={opacity}
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

      {/* Glass border glow */}
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
          opacity={0.3}
          color="#ffffff"
          metalness={0}
          roughness={0.5}
        />
      </mesh>

      {/* Grab indicator dots on the bar */}
      {[-0.02, 0, 0.02].map((x, i) => (
        <mesh key={i} position={[x, -(PANEL_HEIGHT / 2) + BAR_HEIGHT / 2, 0.002]}>
          <circleGeometry args={[0.003, 16]} />
          <meshBasicMaterial color="#999999" transparent opacity={0.6} />
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
