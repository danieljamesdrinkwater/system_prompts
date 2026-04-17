import { useRef, useState, useCallback } from "react";
import { useFrame } from "@react-three/fiber";
import { SpatialPanel } from "./SpatialPanel";
import type { PanelType } from "./SpatialPanel";
import { HandMenu } from "./HandMenu";
import { SpatialToolbar } from "./SpatialToolbar";
import { OrbDock } from "./OrbDock";
import type { OrbPanelType } from "./OrbDock";
import { Environment, type EnvironmentMode } from "./Environment";
import { useEyeTracking } from "../hooks/useEyeTracking";
import type { Group } from "three";

/**
 * Root XR scene. Manages the spatial workspace: ambient lighting,
 * default panels, and the hand menu for spawning new panels.
 */
/** Ordered list of environment modes for cycling */
const ENV_CYCLE: EnvironmentMode[] = ["passthrough", "space", "focus", "calm"];

export function XRScene() {
  const sceneRef = useRef<Group>(null);
  const { gazeTarget } = useEyeTracking();
  const [panels, setPanels] = useState<
    { id: string; type: PanelType; position: [number, number, number] }[]
  >([
    { id: "welcome", type: "note", position: [0, 1.5, -1.2] },
    { id: "timer-1", type: "timer", position: [0.7, 1.5, -1.0] },
  ]);
  const [envMode, setEnvMode] = useState<EnvironmentMode>("passthrough");

  const handleSpawnPanel = useCallback((type: PanelType) => {
    const id = `${type}-${Date.now()}`;
    // Spawn slightly in front of the user, offset randomly to avoid stacking
    const offsetX = (Math.random() - 0.5) * 0.4;
    const position: [number, number, number] = [offsetX, 1.5, -1.0];
    setPanels((prev) => [...prev, { id, type, position }]);
  }, []);

  /** OrbDock spawns panels with the same handler, mapped from OrbPanelType */
  const handleOrbSpawn = useCallback((type: OrbPanelType) => {
    handleSpawnPanel(type);
  }, [handleSpawnPanel]);

  const handleClosePanel = useCallback((id: string) => {
    setPanels((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const handleCycleEnvironment = useCallback(() => {
    setEnvMode((prev) => {
      const idx = ENV_CYCLE.indexOf(prev);
      return ENV_CYCLE[(idx + 1) % ENV_CYCLE.length];
    });
  }, []);

  // Gentle ambient rotation for visual polish (disabled in XR)
  useFrame(() => {
    // Scene-level updates can go here
  });

  return (
    <group ref={sceneRef}>
      {/* Immersive environment (behind everything) */}
      <Environment mode={envMode} />

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

      {/* Orb dock — waist-height app launcher */}
      <OrbDock onSpawn={handleOrbSpawn} />

      {/* Bottom toolbar with environment toggle */}
      <SpatialToolbar
        onSpawn={handleSpawnPanel}
        envMode={envMode}
        onCycleEnvironment={handleCycleEnvironment}
      />
    </group>
  );
}
