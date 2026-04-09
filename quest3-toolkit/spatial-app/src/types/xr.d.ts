/**
 * WebXR type extensions for features not yet in the default TypeScript lib.
 * Quest 3 browser supports these via the WebXR Device API.
 */

interface XRHand extends Map<XRHandJoint, XRJointSpace> {}

type XRHandJoint =
  | "wrist"
  | "thumb-metacarpal"
  | "thumb-phalanx-proximal"
  | "thumb-phalanx-distal"
  | "thumb-tip"
  | "index-finger-metacarpal"
  | "index-finger-phalanx-proximal"
  | "index-finger-phalanx-intermediate"
  | "index-finger-phalanx-distal"
  | "index-finger-tip"
  | "middle-finger-metacarpal"
  | "middle-finger-phalanx-proximal"
  | "middle-finger-phalanx-intermediate"
  | "middle-finger-phalanx-distal"
  | "middle-finger-tip"
  | "ring-finger-metacarpal"
  | "ring-finger-phalanx-proximal"
  | "ring-finger-phalanx-intermediate"
  | "ring-finger-phalanx-distal"
  | "ring-finger-tip"
  | "pinky-finger-metacarpal"
  | "pinky-finger-phalanx-proximal"
  | "pinky-finger-phalanx-intermediate"
  | "pinky-finger-phalanx-distal"
  | "pinky-finger-tip";

interface XRJointSpace extends XRSpace {
  readonly jointName: XRHandJoint;
}

interface XRInputSource {
  readonly hand?: XRHand;
}

interface XRFrame {
  getJointPose?(joint: XRJointSpace, baseSpace: XRReferenceSpace): XRJointPose | null;
}

interface XRJointPose extends XRPose {
  readonly radius: number;
}

// ---------------------------------------------------------------------------
// WebXR Anchors Module
// ---------------------------------------------------------------------------

interface XRAnchor {
  readonly anchorSpace: XRSpace;
  readonly uuid?: string;
  delete(): void;
}

interface XRFrame {
  createAnchor?(
    pose: XRRigidTransform,
    space: XRSpace,
  ): Promise<XRAnchor>;
  trackedAnchors?: ReadonlySet<XRAnchor>;
}

interface XRSession {
  restorePersistentAnchor?(uuid: string): Promise<XRAnchor>;
  deletePersistentAnchor?(uuid: string): Promise<void>;
  readonly persistentAnchors?: readonly string[];
}

// ---------------------------------------------------------------------------
// WebXR Hit-Test Module
// ---------------------------------------------------------------------------

interface XRHitTestSource {
  cancel(): void;
}

interface XRHitTestResult {
  getPose(baseSpace: XRSpace): XRPose | null;
}

interface XRFrame {
  getHitTestResults?(hitTestSource: XRHitTestSource): XRHitTestResult[];
}

interface XRSession {
  requestHitTestSource?(options: {
    space: XRReferenceSpace;
    offsetRay?: XRRay;
  }): Promise<XRHitTestSource>;
}

declare class XRRay {
  constructor(origin?: DOMPointInit, direction?: DOMPointInit);
  readonly origin: DOMPointReadOnly;
  readonly direction: DOMPointReadOnly;
  readonly matrix: Float32Array;
}
