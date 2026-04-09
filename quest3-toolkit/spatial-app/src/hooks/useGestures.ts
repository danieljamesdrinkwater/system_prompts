import { useRef, useCallback } from "react";
import { useFrame } from "@react-three/fiber";

// --- Gesture event types ---

export type GestureType = "swipe-dismiss" | "two-hand-resize" | "pinch-rotate";

export interface SwipeDismissEvent {
  type: "swipe-dismiss";
  hand: "left" | "right";
  velocity: number;
}

export interface TwoHandResizeEvent {
  type: "two-hand-resize";
  scaleDelta: number; // >1 = growing apart, <1 = coming together
  distance: number; // current distance between hands
}

export interface PinchRotateEvent {
  type: "pinch-rotate";
  hand: "left" | "right";
  angleDelta: number; // radians, positive = clockwise from above
  totalAngle: number; // accumulated rotation since gesture start
}

export type GestureEvent = SwipeDismissEvent | TwoHandResizeEvent | PinchRotateEvent;

export interface GestureCallbacks {
  onSwipeDismiss?: (event: SwipeDismissEvent) => void;
  onTwoHandResize?: (event: TwoHandResizeEvent) => void;
  onPinchRotate?: (event: PinchRotateEvent) => void;
}

// --- Internal tracking state ---

interface HandSample {
  position: [number, number, number];
  timestamp: number;
}

interface PinchState {
  active: boolean;
  startPosition: [number, number, number] | null;
  lastPosition: [number, number, number] | null;
  startAngle: number | null;
  lastAngle: number | null;
  accumulatedAngle: number;
  samples: HandSample[];
}

const EMPTY_PINCH: PinchState = {
  active: false,
  startPosition: null,
  lastPosition: null,
  startAngle: null,
  lastAngle: null,
  accumulatedAngle: 0,
  samples: [],
};

// --- Thresholds ---

/** Minimum lateral velocity (m/s) for swipe dismiss */
const SWIPE_VELOCITY_THRESHOLD = 0.8;
/** Maximum time window (ms) to accumulate swipe samples */
const SWIPE_WINDOW_MS = 200;
/** Minimum hand separation change ratio to trigger resize */
const RESIZE_DEAD_ZONE = 0.005;
/** Minimum wrist twist (radians) per frame to emit rotation */
const ROTATE_DEAD_ZONE = 0.01;

/**
 * Gesture recognition hook for spatial interactions.
 *
 * Reads WebXR hand joint data each frame and detects three gestures:
 *
 * 1. **Swipe dismiss** — quick lateral hand movement while pinching.
 *    Fires `onSwipeDismiss` with velocity. Use to close/dismiss panels.
 *
 * 2. **Two-hand resize** — both hands pinching simultaneously,
 *    moving apart or together. Fires `onTwoHandResize` with scaleDelta.
 *
 * 3. **Pinch-rotate** — single hand pinching + twisting the wrist.
 *    Fires `onPinchRotate` with Y-axis angle delta.
 *
 * All callbacks are stable refs — safe to pass inline closures.
 */
export function useGestures(callbacks: GestureCallbacks) {
  // Store callbacks in refs so consumers don't need to memoize
  const cbRef = useRef(callbacks);
  cbRef.current = callbacks;

  const leftPinch = useRef<PinchState>({ ...EMPTY_PINCH });
  const rightPinch = useRef<PinchState>({ ...EMPTY_PINCH });
  const prevTwoHandDist = useRef<number | null>(null);

  /**
   * Compute the angle of a hand's orientation projected onto the XZ plane.
   * Uses the vector from wrist to middle-finger-tip as a proxy for palm facing.
   */
  const computeHandAngle = useCallback(
    (wristPos: [number, number, number], fingerPos: [number, number, number]): number => {
      const dx = fingerPos[0] - wristPos[0];
      const dz = fingerPos[2] - wristPos[2];
      return Math.atan2(dz, dx);
    },
    []
  );

  const distance3 = useCallback(
    (a: [number, number, number], b: [number, number, number]): number => {
      const dx = a[0] - b[0];
      const dy = a[1] - b[1];
      const dz = a[2] - b[2];
      return Math.sqrt(dx * dx + dy * dy + dz * dz);
    },
    []
  );

  useFrame(({ gl }) => {
    const session = gl.xr.getSession();
    if (!session) return;

    const frame = gl.xr.getFrame();
    const refSpace = gl.xr.getReferenceSpace();
    if (!frame || !refSpace) return;

    let leftPos: [number, number, number] | null = null;
    let rightPos: [number, number, number] | null = null;
    let leftPinching = false;
    let rightPinching = false;
    let leftWristPos: [number, number, number] | null = null;
    let rightWristPos: [number, number, number] | null = null;
    let leftFingerPos: [number, number, number] | null = null;
    let rightFingerPos: [number, number, number] | null = null;

    for (const source of session.inputSources) {
      if (!source.hand) continue;

      const isLeft = source.handedness === "left";

      const thumbTip = source.hand.get("thumb-tip");
      const indexTip = source.hand.get("index-finger-tip");
      const wrist = source.hand.get("wrist");
      const middleTip = source.hand.get("middle-finger-tip");

      if (!thumbTip || !indexTip || !wrist) continue;

      // Get joint poses (getJointPose is available on XRFrame when hand-tracking is active)
      const getJointPose = (frame as XRFrame).getJointPose;
      if (!getJointPose) continue;

      const thumbPose = getJointPose.call(frame, thumbTip, refSpace);
      const indexPose = getJointPose.call(frame, indexTip, refSpace);
      const wristPose = getJointPose.call(frame, wrist, refSpace);

      if (!thumbPose || !indexPose || !wristPose) continue;

      const tp = thumbPose.transform.position;
      const ip = indexPose.transform.position;
      const wp = wristPose.transform.position;

      // Pinch = thumb tip and index tip within 2cm
      const pinchDist = Math.sqrt(
        (tp.x - ip.x) ** 2 + (tp.y - ip.y) ** 2 + (tp.z - ip.z) ** 2
      );
      const isPinching = pinchDist < 0.02;

      // Midpoint between thumb and index as the "pinch position"
      const pinchPos: [number, number, number] = [
        (tp.x + ip.x) / 2,
        (tp.y + ip.y) / 2,
        (tp.z + ip.z) / 2,
      ];

      const wristPosition: [number, number, number] = [wp.x, wp.y, wp.z];

      // Middle finger tip for rotation angle computation
      let middlePos: [number, number, number] | null = null;
      if (middleTip) {
        const middlePose = getJointPose.call(frame, middleTip, refSpace);
        if (middlePose) {
          const mp = middlePose.transform.position;
          middlePos = [mp.x, mp.y, mp.z];
        }
      }

      if (isLeft) {
        leftPos = pinchPos;
        leftPinching = isPinching;
        leftWristPos = wristPosition;
        leftFingerPos = middlePos;
      } else {
        rightPos = pinchPos;
        rightPinching = isPinching;
        rightWristPos = wristPosition;
        rightFingerPos = middlePos;
      }
    }

    const now = performance.now();

    // --- Update pinch states ---
    updatePinchState(leftPinch.current, leftPinching, leftPos, now);
    updatePinchState(rightPinch.current, rightPinching, rightPos, now);

    // --- Gesture 1: Two-hand resize ---
    if (leftPinching && rightPinching && leftPos && rightPos) {
      const dist = distance3(leftPos, rightPos);
      if (prevTwoHandDist.current !== null) {
        const delta = dist - prevTwoHandDist.current;
        if (Math.abs(delta) > RESIZE_DEAD_ZONE) {
          const scaleDelta = dist / prevTwoHandDist.current;
          cbRef.current.onTwoHandResize?.({
            type: "two-hand-resize",
            scaleDelta,
            distance: dist,
          });
        }
      }
      prevTwoHandDist.current = dist;
    } else {
      prevTwoHandDist.current = null;
    }

    // --- Gesture 2: Swipe dismiss (per hand, only when NOT two-hand) ---
    if (!(leftPinching && rightPinching)) {
      checkSwipeDismiss(leftPinch.current, "left", now, cbRef);
      checkSwipeDismiss(rightPinch.current, "right", now, cbRef);
    }

    // --- Gesture 3: Pinch-rotate (single hand only when other is NOT pinching) ---
    if (leftPinching && !rightPinching && leftWristPos && leftFingerPos) {
      checkPinchRotate(leftPinch.current, leftWristPos, leftFingerPos, "left", computeHandAngle, cbRef);
    } else {
      leftPinch.current.startAngle = null;
      leftPinch.current.accumulatedAngle = 0;
    }

    if (rightPinching && !leftPinching && rightWristPos && rightFingerPos) {
      checkPinchRotate(rightPinch.current, rightWristPos, rightFingerPos, "right", computeHandAngle, cbRef);
    } else {
      rightPinch.current.startAngle = null;
      rightPinch.current.accumulatedAngle = 0;
    }
  });
}

// --- Helper functions ---

function updatePinchState(
  state: PinchState,
  isPinching: boolean,
  position: [number, number, number] | null,
  now: number
) {
  if (isPinching && position) {
    if (!state.active) {
      // Pinch just started
      state.active = true;
      state.startPosition = [...position];
      state.samples = [];
      state.accumulatedAngle = 0;
      state.startAngle = null;
      state.lastAngle = null;
    }
    state.lastPosition = [...position];
    state.samples.push({ position: [...position], timestamp: now });
    // Trim old samples outside the swipe window
    state.samples = state.samples.filter((s) => now - s.timestamp < SWIPE_WINDOW_MS);
  } else {
    if (state.active) {
      // Pinch just ended — keep samples for one more check then reset
      state.active = false;
    }
    // Clear stale data after release
    if (!isPinching) {
      state.startPosition = null;
      state.lastPosition = null;
      state.samples = [];
      state.startAngle = null;
      state.lastAngle = null;
      state.accumulatedAngle = 0;
    }
  }
}

function checkSwipeDismiss(
  state: PinchState,
  hand: "left" | "right",
  now: number,
  cbRef: React.MutableRefObject<GestureCallbacks>
) {
  if (!state.active || state.samples.length < 2) return;

  const recent = state.samples.filter((s) => now - s.timestamp < SWIPE_WINDOW_MS);
  if (recent.length < 2) return;

  const first = recent[0];
  const last = recent[recent.length - 1];
  const dt = (last.timestamp - first.timestamp) / 1000; // seconds
  if (dt < 0.01) return;

  // Lateral velocity (X axis in world space)
  const dx = last.position[0] - first.position[0];
  const lateralVelocity = Math.abs(dx) / dt;

  if (lateralVelocity > SWIPE_VELOCITY_THRESHOLD) {
    cbRef.current.onSwipeDismiss?.({
      type: "swipe-dismiss",
      hand,
      velocity: lateralVelocity,
    });
    // Reset so we don't fire continuously
    state.samples = [];
  }
}

function checkPinchRotate(
  state: PinchState,
  wristPos: [number, number, number],
  fingerPos: [number, number, number],
  hand: "left" | "right",
  computeAngle: (w: [number, number, number], f: [number, number, number]) => number,
  cbRef: React.MutableRefObject<GestureCallbacks>
) {
  const angle = computeAngle(wristPos, fingerPos);

  if (state.startAngle === null) {
    state.startAngle = angle;
    state.lastAngle = angle;
    state.accumulatedAngle = 0;
    return;
  }

  let delta = angle - (state.lastAngle ?? angle);

  // Handle wraparound at +/- PI
  if (delta > Math.PI) delta -= Math.PI * 2;
  if (delta < -Math.PI) delta += Math.PI * 2;

  if (Math.abs(delta) > ROTATE_DEAD_ZONE) {
    state.accumulatedAngle += delta;
    state.lastAngle = angle;

    cbRef.current.onPinchRotate?.({
      type: "pinch-rotate",
      hand,
      angleDelta: delta,
      totalAngle: state.accumulatedAngle,
    });
  }
}
