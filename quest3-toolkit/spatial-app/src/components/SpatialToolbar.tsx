import { useState } from "react";
import { Text } from "@react-three/drei";

interface SpatialToolbarProps {
  onSpawn: (type: "note" | "editor" | "timer") => void;
}

const TOOLBAR_ITEMS = [
  { type: "note" as const, label: "Notes", color: "#FFE066" },
  { type: "editor" as const, label: "Editor", color: "#A3D9FF" },
  { type: "timer" as const, label: "Timer", color: "#BAFFC9" },
];

const TOOLBAR_WIDTH = 0.35;
const TOOLBAR_HEIGHT = 0.06;

/**
 * visionOS-style bottom toolbar.
 * Fixed position below the user's default view.
 * Glass capsule with app-spawn buttons.
 */
export function SpatialToolbar({ onSpawn }: SpatialToolbarProps) {
  return (
    <group position={[0, 1.05, -0.8]}>
      {/* Glass capsule background */}
      <mesh>
        <planeGeometry args={[TOOLBAR_WIDTH, TOOLBAR_HEIGHT]} />
        <meshPhysicalMaterial
          color="#1a1a2e"
          transparent
          opacity={0.6}
          metalness={0.1}
          roughness={0.25}
          transmission={0.5}
          clearcoat={1}
          clearcoatRoughness={0.1}
        />
      </mesh>

      {/* Border */}
      <mesh position={[0, 0, -0.001]}>
        <planeGeometry args={[TOOLBAR_WIDTH + 0.003, TOOLBAR_HEIGHT + 0.003]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.08} />
      </mesh>

      {/* Toolbar items */}
      {TOOLBAR_ITEMS.map((item, index) => {
        const x = (index - (TOOLBAR_ITEMS.length - 1) / 2) * 0.09;
        return (
          <ToolbarButton
            key={item.type}
            position={[x, 0, 0.001]}
            label={item.label}
            color={item.color}
            onClick={() => onSpawn(item.type)}
          />
        );
      })}
    </group>
  );
}

function ToolbarButton({
  position,
  label,
  color,
  onClick,
}: {
  position: [number, number, number];
  label: string;
  color: string;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <group
      position={position}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {/* Button background */}
      <mesh>
        <planeGeometry args={[0.07, 0.04]} />
        <meshPhysicalMaterial
          color={color}
          transparent
          opacity={hovered ? 0.5 : 0.2}
          roughness={0.4}
        />
      </mesh>

      {/* Label */}
      <Text
        position={[0, 0, 0.001]}
        fontSize={0.011}
        color={hovered ? "#ffffff" : "#cccccc"}
        anchorX="center"
        anchorY="middle"
        font={undefined}
      >
        {label}
      </Text>
    </group>
  );
}
