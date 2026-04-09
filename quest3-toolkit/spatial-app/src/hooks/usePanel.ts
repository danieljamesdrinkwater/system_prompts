import { useState, useCallback, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Vector3Tuple } from "three";

interface PanelState {
  position: Vector3Tuple;
  scale: Vector3Tuple;
  isDragging: boolean;
  isResizing: boolean;
}

interface UsePanelOptions {
  initialPosition: Vector3Tuple;
  initialScale?: Vector3Tuple;
  minScale?: number;
  maxScale?: number;
  snapGrid?: number;
}

/**
 * Hook for panel drag, resize, and snap logic.
 * Provides visionOS-style window management:
 * - Drag via the bottom window bar
 * - Scale by pinching panel edges
 * - Optional grid snapping for organized layouts
 * - Smooth spring-based movement
 */
export function usePanel({
  initialPosition,
  initialScale = [1, 1, 1],
  minScale = 0.5,
  maxScale = 2.0,
  snapGrid = 0,
}: UsePanelOptions) {
  const [state, setState] = useState<PanelState>({
    position: initialPosition,
    scale: initialScale,
    isDragging: false,
    isResizing: false,
  });

  // Smooth interpolation targets
  const targetPosition = useRef<Vector3Tuple>(initialPosition);
  const currentPosition = useRef<Vector3Tuple>([...initialPosition]);

  // Smooth movement with lerp
  useFrame(() => {
    const lerp = 0.15;
    const [cx, cy, cz] = currentPosition.current;
    const [tx, ty, tz] = targetPosition.current;

    currentPosition.current = [
      cx + (tx - cx) * lerp,
      cy + (ty - cy) * lerp,
      cz + (tz - cz) * lerp,
    ];

    // Only update state if moved significantly (avoid re-renders)
    const dx = Math.abs(cx - currentPosition.current[0]);
    const dy = Math.abs(cy - currentPosition.current[1]);
    if (dx > 0.0001 || dy > 0.0001) {
      setState((s) => ({ ...s, position: [...currentPosition.current] }));
    }
  });

  const snapToGrid = useCallback(
    (value: number): number => {
      if (snapGrid <= 0) return value;
      return Math.round(value / snapGrid) * snapGrid;
    },
    [snapGrid]
  );

  const startDrag = useCallback(() => {
    setState((s) => ({ ...s, isDragging: true }));
  }, []);

  const endDrag = useCallback(() => {
    setState((s) => ({ ...s, isDragging: false }));

    // Snap on release if grid is enabled
    if (snapGrid > 0) {
      targetPosition.current = [
        snapToGrid(targetPosition.current[0]),
        snapToGrid(targetPosition.current[1]),
        targetPosition.current[2],
      ];
    }
  }, [snapGrid, snapToGrid]);

  const moveTo = useCallback((x: number, y: number, z?: number) => {
    targetPosition.current = [x, y, z ?? targetPosition.current[2]];
  }, []);

  const resize = useCallback(
    (scaleFactor: number) => {
      setState((s) => {
        const newScale = Math.max(minScale, Math.min(maxScale, s.scale[0] * scaleFactor));
        return { ...s, scale: [newScale, newScale, newScale] };
      });
    },
    [minScale, maxScale]
  );

  return {
    ...state,
    startDrag,
    endDrag,
    moveTo,
    resize,
  };
}
