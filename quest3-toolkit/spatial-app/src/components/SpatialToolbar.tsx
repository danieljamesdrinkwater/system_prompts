import { useState } from "react";
import { Text } from "@react-three/drei";
import { playSound } from "../hooks/useSpatialAudio";
import type { PanelType } from "./SpatialPanel";
import type { EnvironmentMode } from "./Environment";

interface SpatialToolbarProps {
  onSpawn: (type: PanelType) => void;
  envMode?: EnvironmentMode;
  onCycleEnvironment?: () => void;
}

const TOOLBAR_ITEMS = [
  { type: "note" as const, label: "Notes", color: "#FFE066" },
  { type: "editor" as const, label: "Editor", color: "#A3D9FF" },
  { type: "timer" as const, label: "Timer", color: "#BAFFC9" },
  { type: "volumetric" as const, label: "3D Chart", color: "#C9A3FF" },
];

/** Human-readable label for each environment mode */
const ENV_LABELS: Record<EnvironmentMode, string> = {
  passthrough: "Pass",
  space: "Space",
  focus: "Focus",
  calm: "Calm",
};

/** Accent colour for each environment mode button */
const ENV_COLORS: Record<EnvironmentMode, string> = {
  passthrough: "#888899",
  space: "#4B0082",
  focus: "#00aaff",
  calm: "#ff6633",
};

const TOOLBAR_WIDTH = 0.52;
const TOOLBAR_HEIGHT = 0.06;

/**
 * visionOS-style bottom toolbar.
 * Fixed position below the user's default view.
 * Glass capsule with app-spawn buttons.
 */
export function SpatialToolbar({ onSpawn, envMode = "passthrough", onCycleEnvironment }: SpatialToolbarProps) {
  // Position panel-spawn buttons slightly left to make room for env toggle on the right
  const spawnGroupOffset = -0.04;
  const envButtonX = (TOOLBAR_ITEMS.length / 2) * 0.09 + 0.04;

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

      {/* Panel spawn buttons */}
      <group position={[spawnGroupOffset, 0, 0]}>
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

      {/* Divider */}
      <mesh position={[envButtonX - 0.04, 0, 0.001]}>
        <planeGeometry args={[0.001, TOOLBAR_HEIGHT - 0.015]} />
        <meshBasicMaterial color="#555577" transparent opacity={0.4} />
      </mesh>

      {/* Environment toggle button */}
      {onCycleEnvironment && (
        <ToolbarButton
          position={[envButtonX, 0, 0.001]}
          label={ENV_LABELS[envMode]}
          color={ENV_COLORS[envMode]}
          active={envMode !== "passthrough"}
          onClick={onCycleEnvironment}
        />
      )}
    </group>
  );
}

function ToolbarButton({
  position,
  label,
  color,
  active,
  onClick,
}: {
  position: [number, number, number];
  label: string;
  color: string;
  /** When true, the button shows a brighter "active" state */
  active?: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  const baseOpacity = active ? 0.45 : 0.2;

  return (
    <group
      position={position}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
      onClick={(e) => {
        e.stopPropagation();
        playSound("selectionConfirm", position);
        onClick();
      }}
    >
      {/* Button background */}
      <mesh>
        <planeGeometry args={[0.07, 0.04]} />
        <meshPhysicalMaterial
          color={color}
          transparent
          opacity={hovered ? 0.6 : baseOpacity}
          roughness={0.4}
        />
      </mesh>

      {/* Label */}
      <Text
        position={[0, 0, 0.001]}
        fontSize={0.011}
        color={hovered || active ? "#ffffff" : "#cccccc"}
        anchorX="center"
        anchorY="middle"
        font={undefined}
      >
        {label}
      </Text>
    </group>
  );
}
