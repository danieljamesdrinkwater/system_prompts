import { useState } from "react";
import { Text } from "@react-three/drei";
import { animated, useSpring } from "@react-spring/three";
import { playSound } from "../hooks/useSpatialAudio";
import type { PanelType } from "./SpatialPanel";

interface HandMenuProps {
  onSpawn: (type: PanelType) => void;
}

const MENU_ITEMS = [
  { type: "note" as const, label: "Notes", icon: "N", color: "#FFE066" },
  { type: "editor" as const, label: "Editor", icon: "E", color: "#A3D9FF" },
  { type: "timer" as const, label: "Timer", icon: "T", color: "#BAFFC9" },
  { type: "volumetric" as const, label: "3D Chart", icon: "V", color: "#C9A3FF" },
];

/**
 * visionOS-style hand menu.
 * In full implementation, appears when the user turns their palm up.
 * For now, it's a fixed floating radial menu that can be toggled.
 */
export function HandMenu({ onSpawn }: HandMenuProps) {
  const [open, setOpen] = useState(false);

  const { menuScale } = useSpring({
    menuScale: open ? 1 : 0,
    config: { mass: 0.6, tension: 300, friction: 18 },
  });

  const handleToggle = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    setOpen((prev) => !prev);
  };

  return (
    <group position={[-0.4, 1.2, -0.6]}>
      {/* Toggle button — small glass orb */}
      <group onClick={handleToggle}>
        <mesh>
          <sphereGeometry args={[0.025, 24, 24]} />
          <meshPhysicalMaterial
            color="#1a1a2e"
            transparent
            opacity={0.7}
            metalness={0.1}
            roughness={0.2}
            transmission={0.4}
            clearcoat={1}
          />
        </mesh>
        <Text
          position={[0, 0, 0.026]}
          fontSize={0.015}
          color="#ffffff"
          anchorX="center"
          anchorY="middle"
          font={undefined}
        >
          +
        </Text>
      </group>

      {/* Radial menu items */}
      {MENU_ITEMS.map((item, index) => {
        const angle = (index / MENU_ITEMS.length) * Math.PI - Math.PI / 2;
        const radius = 0.08;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        return (
          <animated.group
            key={item.type}
            position-x={x}
            position-y={y}
            scale={menuScale}
            onClick={(e: { stopPropagation: () => void }) => {
              e.stopPropagation();
              playSound("selectionConfirm", [x, y, 0]);
              onSpawn(item.type);
              setOpen(false);
            }}
          >
            {/* Menu item background */}
            <mesh>
              <circleGeometry args={[0.022, 24]} />
              <meshPhysicalMaterial
                color={item.color}
                transparent
                opacity={0.85}
                roughness={0.4}
                metalness={0}
                clearcoat={0.5}
              />
            </mesh>

            {/* Icon */}
            <Text
              position={[0, 0.003, 0.001]}
              fontSize={0.012}
              color="#333333"
              anchorX="center"
              anchorY="middle"
              font={undefined}
            >
              {item.icon}
            </Text>

            {/* Label below */}
            <Text
              position={[0, -0.032, 0.001]}
              fontSize={0.008}
              color="#cccccc"
              anchorX="center"
              anchorY="middle"
              font={undefined}
            >
              {item.label}
            </Text>
          </animated.group>
        );
      })}
    </group>
  );
}
