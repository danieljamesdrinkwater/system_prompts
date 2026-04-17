import { useRef, useState, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { animated, useSpring } from "@react-spring/three";
import { Text } from "@react-three/drei";
import type { Group, Mesh } from "three";

export type OrbPanelType = "note" | "editor" | "timer" | "dashboard";

interface OrbConfig {
  type: OrbPanelType;
  label: string;
  color: string;
}

interface OrbDockProps {
  /** Called when an orb is pinch-selected to spawn a panel */
  onSpawn: (type: OrbPanelType) => void;
  /** Position override — defaults to waist height, centered */
  position?: [number, number, number];
}

const ORB_CONFIGS: OrbConfig[] = [
  { type: "note", label: "Notes", color: "#FFE066" },
  { type: "editor", label: "Editor", color: "#A3D9FF" },
  { type: "timer", label: "Timer", color: "#BAFFC9" },
  { type: "dashboard", label: "Dashboard", color: "#0a84ff" },
];

/** Radius of each app orb */
const ORB_RADIUS = 0.04;
/** Radius of the central frosted dock sphere */
const DOCK_RADIUS = 0.15;
/** Orbit radius — how far orbs sit from the dock center */
const ORBIT_RADIUS = 0.22;
/** Gentle orbital speed (radians per second) */
const ORBIT_SPEED = 0.15;

/**
 * visionOS home-view-style floating orb dock.
 *
 * A translucent frosted-glass sphere with glowing app orbs
 * orbiting around it. Each orb represents a panel type.
 *
 * Interactions:
 * - Hover an orb: scales to 1.3x with a glow halo
 * - Click/pinch an orb: spawns the panel, orb pulses
 * - The dock hovers at waist height, anchored in front of the user
 */
export function OrbDock({
  onSpawn,
  position = [0, 0.95, -0.7],
}: OrbDockProps) {
  const groupRef = useRef<Group>(null);
  const timeRef = useRef(0);

  // Gentle bob animation for the whole dock
  useFrame((_, delta) => {
    timeRef.current += delta;
    if (groupRef.current) {
      // Subtle float: 1cm vertical bob over ~4 seconds
      groupRef.current.position.y =
        position[1] + Math.sin(timeRef.current * 0.8) * 0.01;
    }
  });

  return (
    <group ref={groupRef} position={position}>
      {/* Central frosted glass dock sphere */}
      <DockSphere />

      {/* Orbiting app orbs */}
      {ORB_CONFIGS.map((config, index) => (
        <OrbItem
          key={config.type}
          config={config}
          index={index}
          total={ORB_CONFIGS.length}
          onSelect={() => onSpawn(config.type)}
        />
      ))}
    </group>
  );
}

// --- Dock sphere (central frosted glass) ---

function DockSphere() {
  const meshRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const { dockOpacity } = useSpring({
    dockOpacity: hovered ? 0.35 : 0.2,
    config: { tension: 180, friction: 20 },
  });

  return (
    <group>
      {/* Main frosted sphere */}
      <animated.mesh
        ref={meshRef}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <sphereGeometry args={[DOCK_RADIUS, 48, 48]} />
        <animated.meshPhysicalMaterial
          color="#1a1a2e"
          transparent
          opacity={dockOpacity}
          metalness={0.05}
          roughness={0.15}
          transmission={0.7}
          thickness={0.05}
          envMapIntensity={0.3}
          clearcoat={1}
          clearcoatRoughness={0.05}
        />
      </animated.mesh>

      {/* Outer glow ring — subtle rim light */}
      <mesh>
        <ringGeometry args={[DOCK_RADIUS + 0.005, DOCK_RADIUS + 0.012, 64]} />
        <meshBasicMaterial
          color="#ffffff"
          transparent
          opacity={0.06}
        />
      </mesh>
    </group>
  );
}

// --- Individual orb ---

interface OrbItemProps {
  config: OrbConfig;
  index: number;
  total: number;
  onSelect: () => void;
}

function OrbItem({ config, index, total, onSelect }: OrbItemProps) {
  const groupRef = useRef<Group>(null);
  const [hovered, setHovered] = useState(false);
  const [pulsing, setPulsing] = useState(false);
  const timeRef = useRef(0);

  // Base angle for this orb in the circle
  const baseAngle = useMemo(() => (index / total) * Math.PI * 2, [index, total]);

  // Hover: scale up to 1.3x with spring
  const { orbScale } = useSpring({
    orbScale: pulsing ? 1.5 : hovered ? 1.3 : 1.0,
    config: { mass: 0.4, tension: 350, friction: 14 },
    onRest: () => {
      if (pulsing) setPulsing(false);
    },
  });

  // Glow halo intensity
  const { haloOpacity, haloScale } = useSpring({
    haloOpacity: hovered ? 0.4 : 0,
    haloScale: hovered ? 1.8 : 1.0,
    config: { tension: 250, friction: 18 },
  });

  // Orbit position — updates each frame
  useFrame((_, delta) => {
    timeRef.current += delta;
    const angle = baseAngle + timeRef.current * ORBIT_SPEED;

    if (groupRef.current) {
      groupRef.current.position.x = Math.cos(angle) * ORBIT_RADIUS;
      groupRef.current.position.z = Math.sin(angle) * ORBIT_RADIUS;
      // Slight vertical wave so orbs aren't perfectly flat
      groupRef.current.position.y =
        Math.sin(angle * 2 + index) * 0.015;
    }
  });

  const handleClick = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    setPulsing(true);
    onSelect();
  };

  return (
    <group ref={groupRef}>
      <animated.group
        scale={orbScale}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
        onClick={handleClick}
      >
        {/* Glow halo (behind the orb) */}
        <animated.mesh
          position={[0, 0, -0.005]}
          scale={haloScale}
        >
          <circleGeometry args={[ORB_RADIUS * 1.2, 32]} />
          <animated.meshBasicMaterial
            color={config.color}
            transparent
            opacity={haloOpacity}
          />
        </animated.mesh>

        {/* Main orb sphere */}
        <mesh>
          <sphereGeometry args={[ORB_RADIUS, 32, 32]} />
          <meshPhysicalMaterial
            color={config.color}
            transparent
            opacity={0.85}
            metalness={0}
            roughness={0.2}
            clearcoat={0.8}
            clearcoatRoughness={0.1}
            emissive={config.color}
            emissiveIntensity={hovered ? 0.4 : 0.15}
          />
        </mesh>

        {/* Inner glow core */}
        <mesh>
          <sphereGeometry args={[ORB_RADIUS * 0.5, 16, 16]} />
          <meshBasicMaterial
            color={config.color}
            transparent
            opacity={0.3}
          />
        </mesh>

        {/* Label — floats below the orb */}
        <Text
          position={[0, -(ORB_RADIUS + 0.018), 0]}
          fontSize={0.012}
          color="#ffffff"
          anchorX="center"
          anchorY="top"
          font={undefined}
        >
          {config.label}
        </Text>
      </animated.group>
    </group>
  );
}
