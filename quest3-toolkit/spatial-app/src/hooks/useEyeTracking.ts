import { useRef, useState, useCallback } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Vector3, Raycaster, type Intersection, type Object3D } from "three";

interface EyeTrackingState {
  /** The panel ID currently being gazed at, or null */
  gazeTarget: string | null;
  /** World-space position where the gaze ray hits, or null */
  gazePosition: Vector3 | null;
  /** Whether a gaze + pinch selection just occurred */
  gazeSelected: boolean;
}

/** Registry mapping Three.js object UUIDs to panel IDs */
const panelRegistry = new Map<string, string>();

/**
 * Register a Three.js mesh as a gaze target for a specific panel.
 * Call this from SpatialPanel when the mesh ref is available.
 */
export function registerGazeTarget(objectUuid: string, panelId: string) {
  panelRegistry.set(objectUuid, panelId);
}

/**
 * Unregister a gaze target when the panel unmounts.
 */
export function unregisterGazeTarget(objectUuid: string) {
  panelRegistry.delete(objectUuid);
}

/**
 * Hook for eye gaze tracking via WebXR input sources.
 *
 * Uses the "gaze" input source (targetRayMode === "gaze") available
 * on Quest 3 when eye tracking is enabled. Raycasts from the gaze
 * direction into the scene to detect which panel is being looked at.
 *
 * When gaze is detected simultaneously with a pinch gesture from
 * either hand, it triggers a selection event.
 */
export function useEyeTracking() {
  const [state, setState] = useState<EyeTrackingState>({
    gazeTarget: null,
    gazePosition: null,
    gazeSelected: false,
  });

  const { scene } = useThree();
  const raycaster = useRef(new Raycaster());
  const gazeOrigin = useRef(new Vector3());
  const gazeDirection = useRef(new Vector3());
  const frameRef = useRef(0);
  const prevTarget = useRef<string | null>(null);
  const selectionCooldown = useRef(0);

  useFrame(({ gl }) => {
    // Throttle to every 2nd frame for performance
    frameRef.current++;
    if (frameRef.current % 2 !== 0) return;

    // Decrement selection cooldown
    if (selectionCooldown.current > 0) {
      selectionCooldown.current--;
    }

    const session = gl.xr.getSession();
    if (!session) return;

    const refSpace = gl.xr.getReferenceSpace();
    if (!refSpace) return;

    let gazeFound = false;
    let pinchDetected = false;

    // Check for pinch on any hand input source
    for (const source of session.inputSources) {
      if (source.hand) {
        // Hand tracking — pinch is detected via the "select" event
        // or by checking the squeeze value on the gamepad
        // For hand tracking, we rely on the selectstart/selectend events
      }
      if (source.gamepad) {
        // Controller or hand with gamepad proxy — trigger counts as pinch
        for (const button of source.gamepad.buttons) {
          if (button.pressed) {
            pinchDetected = true;
            break;
          }
        }
      }
    }

    // Find gaze input source
    for (const source of session.inputSources) {
      if (source.targetRayMode === "gaze") {
        gazeFound = true;

        // Get the XR frame to read the gaze pose
        const frame = gl.xr.getFrame();
        if (!frame || !refSpace) break;

        const pose = frame.getPose(source.targetRaySpace, refSpace);
        if (!pose) break;

        const { position, orientation } = pose.transform;

        gazeOrigin.current.set(position.x, position.y, position.z);

        // Compute forward direction from the gaze orientation quaternion
        // The gaze ray points along -Z in the target ray space
        const qx = orientation.x;
        const qy = orientation.y;
        const qz = orientation.z;
        const qw = orientation.w;

        // Rotate (0, 0, -1) by the quaternion
        gazeDirection.current.set(
          2 * (qx * qz + qw * qy),
          2 * (qy * qz - qw * qx),
          -(1 - 2 * (qx * qx + qy * qy))
        );
        gazeDirection.current.normalize();

        // Raycast into the scene
        raycaster.current.set(gazeOrigin.current, gazeDirection.current);
        const intersections: Intersection<Object3D>[] =
          raycaster.current.intersectObjects(scene.children, true);

        let newTarget: string | null = null;
        let hitPosition: Vector3 | null = null;

        for (const hit of intersections) {
          // Walk up the parent chain to find a registered panel
          let obj: Object3D | null = hit.object;
          while (obj) {
            const panelId = panelRegistry.get(obj.uuid);
            if (panelId) {
              newTarget = panelId;
              hitPosition = hit.point.clone();
              break;
            }
            obj = obj.parent;
          }
          if (newTarget) break;
        }

        const selected =
          pinchDetected &&
          newTarget !== null &&
          selectionCooldown.current === 0;

        if (selected) {
          // Cooldown prevents rapid-fire selections (30 frames ~ 0.5s at 60fps)
          selectionCooldown.current = 30;
        }

        // Only update state when target changes or selection fires
        if (newTarget !== prevTarget.current || selected) {
          prevTarget.current = newTarget;
          setState({
            gazeTarget: newTarget,
            gazePosition: hitPosition,
            gazeSelected: selected,
          });
        }

        break; // Only process first gaze source
      }
    }

    // No gaze source found — clear state
    if (!gazeFound && prevTarget.current !== null) {
      prevTarget.current = null;
      setState({
        gazeTarget: null,
        gazePosition: null,
        gazeSelected: false,
      });
    }
  });

  // Listen for select events (hand pinch triggers "select" in WebXR)
  const handleSelect = useCallback(() => {
    if (prevTarget.current && selectionCooldown.current === 0) {
      selectionCooldown.current = 30;
      setState((prev) => ({
        ...prev,
        gazeSelected: true,
      }));
      // Clear selection flag after one frame
      requestAnimationFrame(() => {
        setState((prev) => ({
          ...prev,
          gazeSelected: false,
        }));
      });
    }
  }, []);

  return {
    ...state,
    /** Call from XR session select event handler for pinch detection */
    handleSelect,
  };
}
