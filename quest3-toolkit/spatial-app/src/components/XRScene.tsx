import { useRef, useState, useCallback } from "react";
import { useFrame } from "@react-three/fiber";
import { SpatialPanel } from "./SpatialPanel";
import { HandMenu } from "./HandMenu";
import { SpatialToolbar } from "./SpatialToolbar";
import { Environment, type EnvironmentMode } from "./Environment";
import { useEyeTracking } from "../hooks/useEyeTracking";
import type { Group } from "three";

/**
 * Root XR scene. Manages the spatial workspace: ambient lighting,
 * default panels, and the hand menu for spawning new panels.
 */
export function XRScene() {
  const sceneRef = useRef<Group>(null);
  const { gazeTarget } = useEyeTracking();
  const [panels, setPanels] = useState([
    { id: "welcome", type: "note" as const, position: [0, 1.5, -1.2] as [number, number, number] },
    { id: "timer-1", type: "timer" as const, position: [0.7, 1.5, -1.0] as [number, number, number] },
  ]);

  const handleSpawnPanel = (type: "note" | "editor" | "timer") => {
    const id = `${type}-${Date.now()}`;
    // Spawn slightly in front of the user, offset randomly to avoid stacking
    const offsetX = (Math.random() - 0.5) * 0.4;
    const position: [number, number, number] = [offsetX, 1.5, -1.0];
    setPanels((prev) => [...prev, { id, type, position }]);
  };

  const handleClosePanel = (id: string) => {
    setPanels((prev) => prev.filter((p) => p.id !== id));
  };

  // Gentle ambient rotation for visual polish (disabled in XR)
  useFrame(() => {
    // Scene-level updates can go here
  });

  return (
    <group ref={sceneRef}>
      {/* Soft ambient light — doesn't fight with passthrough */}
      <ambientLight intensity={0.4} />
      <directionalLight position={[2, 4, 1]} intensity={0.3} />

      {/* Spatial panels */}
      {panels.map((panel) => (
        <SpatialPanel
          key={panel.id}
          id={panel.id}
          type={panel.type}
          initialPosition={panel.position}
          gazeTarget={gazeTarget}
          onClose={() => handleClosePanel(panel.id)}
        />
      ))}

      {/* Hand menu for spawning panels */}
      <HandMenu onSpawn={handleSpawnPanel} />

      {/* Bottom toolbar */}
      <SpatialToolbar onSpawn={handleSpawnPanel} />
    </group>
  );
}
