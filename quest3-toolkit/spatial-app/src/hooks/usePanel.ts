import { useState, useCallback, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Vector3Tuple } from "three";
import type {
  SwipeDismissEvent,
  TwoHandResizeEvent,
  PinchRotateEvent,
} from "./useGestures";

interface PanelState {
  position: Vector3Tuple;
  scale: Vector3Tuple;
  rotation: Vector3Tuple;
  isDragging: boolean;
  isResizing: boolean;
  dismissed: boolean;
}

interface SnapZone {
  position: Vector3Tuple;
  /** Radius within which snapping activates */
  radius: number;
}

interface UsePanelOptions {
  initialPosition: Vector3Tuple;
  initialScale?: Vector3Tuple;
  initialRotation?: Vector3Tuple;
  minScale?: number;
  maxScale?: number;
  snapGrid?: number;
  /** Called when a swipe-dismiss gesture closes this panel */
  onDismiss?: () => void;
  /** Optional snap zones — panel bounces subtly when entering one */
  snapZones?: SnapZone[];
  /** Minimum Y position in metres (default 0.3 — can't go below table height) */
  minY?: number;
  /** Maximum Z position (default 0.5 — can't go behind the user) */
  maxZ?: number;
  /** Momentum damping factor per frame (default 0.95) */
  damping?: number;
}

/** Number of frames of drag history to track for velocity calculation */
const VELOCITY_HISTORY_LENGTH = 6;

/** Minimum velocity magnitude to apply momentum (avoids jitter) */
const MIN_VELOCITY_THRESHOLD = 0.0005;

/** Spring parameters for snap-zone bounce oscillation */
const SNAP_SPRING_STIFFNESS = 180;
const SNAP_SPRING_DAMPING_RATIO = 0.35; // underdamped for visible oscillation

/**
 * Hook for panel drag, resize, snap, and bounce physics.
 * Provides visionOS-style window management:
 * - Drag via the bottom window bar
 * - Scale by pinching panel edges
 * - Optional grid snapping for organized layouts
 * - Momentum with damping after drag release
 * - Subtle bounce on snap zones with spring-settle oscillation
 * - Constraints: can't go behind user or below y=0.3m
 */
export function usePanel({
  initialPosition,
  initialScale = [1, 1, 1],
  initialRotation = [0, 0, 0],
  minScale = 0.5,
  maxScale = 2.0,
  snapGrid = 0,
  onDismiss,
  snapZones = [],
  minY = 0.3,
  maxZ = 0.5,
  damping = 0.95,
}: UsePanelOptions) {
  const [state, setState] = useState<PanelState>({
    position: initialPosition,
    scale: initialScale,
    rotation: initialRotation,
    isDragging: false,
    isResizing: false,
    dismissed: false,
  });

  // Smooth interpolation targets
  const targetPosition = useRef<Vector3Tuple>(initialPosition);
  const currentPosition = useRef<Vector3Tuple>([...initialPosition]);

  // Velocity tracking for momentum after drag release
  const velocity = useRef<Vector3Tuple>([0, 0, 0]);
  const isDraggingRef = useRef(false);

  // Drag position history for velocity calculation
  const dragHistory = useRef<{ pos: Vector3Tuple; time: number }[]>([]);

  // Spring oscillation state for snap-zone bounce
  const springOffset = useRef<Vector3Tuple>([0, 0, 0]);
  const springVelocity = useRef<Vector3Tuple>([0, 0, 0]);
  const isSpringActive = useRef(false);

  // Track which snap zone we last entered (avoid repeated bounces)
  const lastSnapZoneIndex = useRef<number | null>(null);

  /**
   * Clamp position to constraints:
   * - Y >= minY (can't go below 0.3m)
   * - Z <= maxZ (can't go behind the user)
   */
  const clampPosition = useCallback(
    (pos: Vector3Tuple): Vector3Tuple => {
      return [pos[0], Math.max(minY, pos[1]), Math.min(maxZ, pos[2])];
    },
    [minY, maxZ]
  );

  /**
   * Find the index of the nearest snap zone the position is inside,
   * or -1 if not within any zone.
   */
  const findNearestSnapZone = useCallback(
    (pos: Vector3Tuple): number => {
      for (let i = 0; i < snapZones.length; i++) {
        const zone = snapZones[i];
        const dx = pos[0] - zone.position[0];
        const dy = pos[1] - zone.position[1];
        const dz = pos[2] - zone.position[2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < zone.radius) return i;
      }
      return -1;
    },
    [snapZones]
  );

  /**
   * Trigger a spring bounce from the current offset toward zero.
   * The panel overshoots then oscillates back to the snap point.
   */
  const triggerSnapBounce = useCallback(
    (fromPos: Vector3Tuple, toPos: Vector3Tuple) => {
      springOffset.current = [
        fromPos[0] - toPos[0],
        fromPos[1] - toPos[1],
        fromPos[2] - toPos[2],
      ];
      // Give it a kick in the direction of travel for extra bounce
      springVelocity.current = [
        velocity.current[0] * 0.3,
        velocity.current[1] * 0.3,
        velocity.current[2] * 0.3,
      ];
      isSpringActive.current = true;
    },
    []
  );

  // Physics update loop — momentum, spring oscillation, and constraints
  useFrame((_, delta) => {
    // Clamp delta to avoid huge jumps (e.g. tab switch, frame spike)
    const dt = Math.min(delta, 0.05);

    if (isDraggingRef.current) {
      // While dragging: record position history for velocity calculation
      dragHistory.current.push({
        pos: [...targetPosition.current],
        time: performance.now(),
      });
      if (dragHistory.current.length > VELOCITY_HISTORY_LENGTH) {
        dragHistory.current.shift();
      }

      // Responsive lerp while dragging
      const lerpFactor = 0.25;
      const [cx, cy, cz] = currentPosition.current;
      const [tx, ty, tz] = targetPosition.current;
      currentPosition.current = clampPosition([
        cx + (tx - cx) * lerpFactor,
        cy + (ty - cy) * lerpFactor,
        cz + (tz - cz) * lerpFactor,
      ]);

      // Reset momentum state during drag
      velocity.current = [0, 0, 0];
      isSpringActive.current = false;
      springOffset.current = [0, 0, 0];
    } else {
      // ── Post-drag momentum phase ──
      const [vx, vy, vz] = velocity.current;
      const speed = Math.sqrt(vx * vx + vy * vy + vz * vz);

      if (speed > MIN_VELOCITY_THRESHOLD) {
        // Apply velocity to target position
        targetPosition.current = clampPosition([
          targetPosition.current[0] + vx,
          targetPosition.current[1] + vy,
          targetPosition.current[2] + vz,
        ]);

        // Apply damping
        velocity.current = [vx * damping, vy * damping, vz * damping];

        // Check for snap zone entry
        const zoneIdx = findNearestSnapZone(targetPosition.current);
        if (zoneIdx >= 0 && zoneIdx !== lastSnapZoneIndex.current) {
          lastSnapZoneIndex.current = zoneIdx;
          const zone = snapZones[zoneIdx];
          const prevPos: Vector3Tuple = [...targetPosition.current];
          targetPosition.current = clampPosition([...zone.position]);
          triggerSnapBounce(prevPos, zone.position);
          velocity.current = [0, 0, 0]; // spring takes over
        }
      } else if (speed > 0) {
        velocity.current = [0, 0, 0]; // below threshold — stop
      }

      // ── Spring oscillation (snap bounce) ──
      if (isSpringActive.current) {
        const [ox, oy, oz] = springOffset.current;
        const [svx, svy, svz] = springVelocity.current;

        // Damped harmonic oscillator: F = -kx - cv
        const dampCoeff =
          2 * SNAP_SPRING_DAMPING_RATIO * Math.sqrt(SNAP_SPRING_STIFFNESS);

        const ax = -SNAP_SPRING_STIFFNESS * ox - dampCoeff * svx;
        const ay = -SNAP_SPRING_STIFFNESS * oy - dampCoeff * svy;
        const az = -SNAP_SPRING_STIFFNESS * oz - dampCoeff * svz;

        springVelocity.current = [
          svx + ax * dt,
          svy + ay * dt,
          svz + az * dt,
        ];
        springOffset.current = [
          ox + springVelocity.current[0] * dt,
          oy + springVelocity.current[1] * dt,
          oz + springVelocity.current[2] * dt,
        ];

        // Check if spring has settled
        const springMag = Math.sqrt(
          springOffset.current[0] ** 2 +
            springOffset.current[1] ** 2 +
            springOffset.current[2] ** 2
        );
        const springVelMag = Math.sqrt(
          springVelocity.current[0] ** 2 +
            springVelocity.current[1] ** 2 +
            springVelocity.current[2] ** 2
        );
        if (springMag < 0.0001 && springVelMag < 0.0001) {
          isSpringActive.current = false;
          springOffset.current = [0, 0, 0];
          springVelocity.current = [0, 0, 0];
        }
      }

      // Lerp current position toward target + spring offset
      const lerpFactor = 0.15;
      const [cx, cy, cz] = currentPosition.current;
      const [tx, ty, tz] = targetPosition.current;
      const [sox, soy, soz] = springOffset.current;

      currentPosition.current = clampPosition([
        cx + (tx + sox - cx) * lerpFactor,
        cy + (ty + soy - cy) * lerpFactor,
        cz + (tz + soz - cz) * lerpFactor,
      ]);
    }

    // Only update React state if position moved significantly (avoid re-renders)
    const [px, py] = state.position;
    const dx = Math.abs(px - currentPosition.current[0]);
    const dy = Math.abs(py - currentPosition.current[1]);
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
    isDraggingRef.current = true;
    dragHistory.current = [];
    lastSnapZoneIndex.current = null;
    setState((s) => ({ ...s, isDragging: true }));
  }, []);

  const endDrag = useCallback(() => {
    isDraggingRef.current = false;

    // Calculate velocity from drag history
    const history = dragHistory.current;
    if (history.length >= 2) {
      const newest = history[history.length - 1];
      const oldest = history[0];
      const elapsed = (newest.time - oldest.time) / 1000; // seconds

      if (elapsed > 0.001) {
        // Convert to velocity per frame (~16ms at 60fps)
        const frameTime = 1 / 60;
        velocity.current = [
          ((newest.pos[0] - oldest.pos[0]) / elapsed) * frameTime,
          ((newest.pos[1] - oldest.pos[1]) / elapsed) * frameTime,
          ((newest.pos[2] - oldest.pos[2]) / elapsed) * frameTime,
        ];
      }
    }
    dragHistory.current = [];

    // Snap on release if grid is enabled
    if (snapGrid > 0) {
      const snapped: Vector3Tuple = [
        snapToGrid(targetPosition.current[0]),
        snapToGrid(targetPosition.current[1]),
        targetPosition.current[2],
      ];
      const prevPos: Vector3Tuple = [...targetPosition.current];
      targetPosition.current = clampPosition(snapped);

      // Trigger a subtle bounce toward the snap point
      const snapDist = Math.sqrt(
        (prevPos[0] - snapped[0]) ** 2 + (prevPos[1] - snapped[1]) ** 2
      );
      if (snapDist > 0.005) {
        triggerSnapBounce(prevPos, snapped);
        velocity.current = [0, 0, 0]; // spring handles it
      }
    }

    setState((s) => ({ ...s, isDragging: false }));
  }, [snapGrid, snapToGrid, clampPosition, triggerSnapBounce]);

  const moveTo = useCallback(
    (x: number, y: number, z?: number) => {
      targetPosition.current = clampPosition([
        x,
        y,
        z ?? targetPosition.current[2],
      ]);
    },
    [clampPosition]
  );

  const resize = useCallback(
    (scaleFactor: number) => {
      setState((s) => {
        const newScale = Math.max(minScale, Math.min(maxScale, s.scale[0] * scaleFactor));
        return { ...s, scale: [newScale, newScale, newScale] };
      });
    },
    [minScale, maxScale]
  );

  const rotateTo = useCallback((y: number) => {
    setState((s) => ({ ...s, rotation: [s.rotation[0], y, s.rotation[2]] }));
  }, []);

  const rotateBy = useCallback((deltaY: number) => {
    setState((s) => ({
      ...s,
      rotation: [s.rotation[0], s.rotation[1] + deltaY, s.rotation[2]],
    }));
  }, []);

  const dismiss = useCallback(() => {
    setState((s) => ({ ...s, dismissed: true }));
    onDismiss?.();
  }, [onDismiss]);

  // --- Gesture event handlers (pass these to useGestures callbacks) ---

  const handleSwipeDismiss = useCallback(
    (_event: SwipeDismissEvent) => {
      dismiss();
    },
    [dismiss]
  );

  const handleTwoHandResize = useCallback(
    (event: TwoHandResizeEvent) => {
      resize(event.scaleDelta);
    },
    [resize]
  );

  const handlePinchRotate = useCallback(
    (event: PinchRotateEvent) => {
      rotateBy(event.angleDelta);
    },
    [rotateBy]
  );

  return {
    ...state,
    startDrag,
    endDrag,
    moveTo,
    resize,
    rotateTo,
    rotateBy,
    dismiss,
    handleSwipeDismiss,
    handleTwoHandResize,
    handlePinchRotate,
  };
}
