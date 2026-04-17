import { useState, useCallback, useRef } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SpatialAnchor {
  id: string;
  position: [number, number, number];
  rotation: [number, number, number];
  data: Record<string, unknown>;
  /** UUID of the corresponding XRAnchor (only set when WebXR Anchors API is used). */
  xrAnchorUUID: string | null;
}

interface AnchorCapabilities {
  /** Whether the WebXR Anchors API is available in this session. */
  webxrAnchors: boolean;
  /** Whether hit-test (floor detection) is available. */
  hitTest: boolean;
}

const STORAGE_KEY = "spatial-workspace-anchors";
const XR_ANCHOR_MAP_KEY = "spatial-workspace-xr-anchor-map";

/** Default height above detected floor plane for docked panels (metres). */
const FLOOR_DOCK_HEIGHT = 1.2;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Persist the UUID-to-panelId mapping so we can restore XR anchors. */
function saveAnchorMap(map: Record<string, string>): void {
  try {
    localStorage.setItem(XR_ANCHOR_MAP_KEY, JSON.stringify(map));
  } catch {
    // Storage full or unavailable
  }
}

function loadAnchorMap(): Record<string, string> {
  try {
    const raw = localStorage.getItem(XR_ANCHOR_MAP_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Hook for persisting panel positions in 3D space.
 *
 * **Primary path** (WebXR Anchors API available — Quest 3 in immersive session):
 *   - Creates an `XRAnchor` for each panel.
 *   - Persists the anchor UUID to localStorage so it can be re-requested
 *     in a subsequent session.
 *   - On restore, requests stored anchors and positions panels to match.
 *
 * **Fallback path** (no XR session / no anchors feature):
 *   - Saves / restores positions via localStorage only (original behaviour).
 *
 * **Floor-plane docking**:
 *   - Uses WebXR hit-test to detect the floor plane.
 *   - Dock panels at `floor + 1.2 m` above the detected plane.
 *
 * Exports: createAnchor, restoreAnchors, clearAnchors (plus legacy helpers).
 */
export function useSpatialAnchor() {
  const [anchors, setAnchors] = useState<SpatialAnchor[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [capabilities, setCapabilities] = useState<AnchorCapabilities>({
    webxrAnchors: false,
    hitTest: false,
  });

  const [floorY, setFloorY] = useState<number | null>(null);

  /** Maps XR anchor UUID -> panel id. */
  const anchorMapRef = useRef<Record<string, string>>(loadAnchorMap());

  /** Reference to active XR anchors so we can clean up. */
  const liveXRAnchorRef = useRef<Map<string, unknown>>(new Map());

  // -------------------------------------------------------------------
  // Detect capabilities once an XR session is available
  // -------------------------------------------------------------------

  const detectCapabilities = useCallback((session: XRSession) => {
    const hasAnchors =
      typeof session.requestReferenceSpace === "function" &&
      // The Anchors API is signalled by "anchors" being in enabledFeatures
      // (there is no direct typeof check — it's a session feature).
      (session as unknown as Record<string, string[]>).enabledFeatures?.includes(
        "anchors",
      );

    const hasHitTest =
      (session as unknown as Record<string, string[]>).enabledFeatures?.includes(
        "hit-test",
      );

    setCapabilities({
      webxrAnchors: Boolean(hasAnchors),
      hitTest: Boolean(hasHitTest),
    });

    return { webxrAnchors: Boolean(hasAnchors), hitTest: Boolean(hasHitTest) };
  }, []);

  // -------------------------------------------------------------------
  // Floor plane detection via hit-test
  // -------------------------------------------------------------------

  /**
   * Run a single hit-test against the floor plane and update `floorY`.
   * Call once per session start; it fires a downward ray from head height.
   */
  const detectFloorPlane = useCallback(
    async (session: XRSession, refSpace: XRReferenceSpace) => {
      if (!capabilities.hitTest) return null;

      try {
        const hitTestSource = await (
          session as unknown as {
            requestHitTestSource: (opts: {
              space: XRReferenceSpace;
              offsetRay: unknown;
            }) => Promise<{ cancel: () => void }>;
          }
        ).requestHitTestSource({
          space: refSpace,
          // Downward ray from ~2 m height
          offsetRay: new XRRay(
            new DOMPoint(0, 2, 0, 1),
            new DOMPoint(0, -1, 0, 0),
          ),
        });

        // We only need one result; schedule a single-frame read.
        const onFrame: XRFrameRequestCallback = (_time, frame) => {
          const results = (
            frame as unknown as {
              getHitTestResults: (
                src: unknown,
              ) => Array<{ getPose: (ref: XRReferenceSpace) => XRPose | null }>;
            }
          ).getHitTestResults(hitTestSource);

          if (results.length > 0) {
            const pose = results[0].getPose(refSpace);
            if (pose) {
              const detectedY = pose.transform.position.y;
              setFloorY(detectedY);
            }
          }
          hitTestSource.cancel();
        };

        session.requestAnimationFrame(onFrame);
      } catch {
        // Hit-test not available — fall through silently
      }

      return floorY;
    },
    [capabilities.hitTest, floorY],
  );

  // -------------------------------------------------------------------
  // Create anchor (primary API)
  // -------------------------------------------------------------------

  /**
   * Create a spatial anchor for `panelId`.
   *
   * - If an XR session + Anchors API is available, creates a real XRAnchor
   *   and stores its UUID for later restoration.
   * - Otherwise falls back to localStorage persistence.
   */
  const createAnchor = useCallback(
    async (
      panelId: string,
      position: [number, number, number],
      rotation: [number, number, number] = [0, 0, 0],
      data: Record<string, unknown> = {},
      frame?: XRFrame,
      refSpace?: XRReferenceSpace,
    ) => {
      let xrAnchorUUID: string | null = null;

      // Attempt WebXR Anchor creation
      if (capabilities.webxrAnchors && frame && refSpace) {
        try {
          const anchorPose = new XRRigidTransform(
            { x: position[0], y: position[1], z: position[2], w: 1 },
            { x: 0, y: 0, z: 0, w: 1 },
          );

          const xrAnchor = await (
            frame as unknown as {
              createAnchor: (
                pose: XRRigidTransform,
                space: XRReferenceSpace,
              ) => Promise<{ uuid?: string; anchorSpace: XRSpace; delete: () => void }>;
            }
          ).createAnchor(anchorPose, refSpace);

          // Some implementations expose a UUID; generate one if not provided.
          xrAnchorUUID =
            (xrAnchor as unknown as { uuid?: string }).uuid ??
            `xa-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

          liveXRAnchorRef.current.set(panelId, xrAnchor);

          // Persist the mapping
          anchorMapRef.current[xrAnchorUUID] = panelId;
          saveAnchorMap(anchorMapRef.current);
        } catch {
          // Anchor creation failed — fall through to localStorage only
        }
      }

      const anchor: SpatialAnchor = {
        id: panelId,
        position,
        rotation,
        data,
        xrAnchorUUID,
      };

      setAnchors((prev) => {
        const idx = prev.findIndex((a) => a.id === panelId);
        const updated =
          idx >= 0
            ? prev.map((a, i) => (i === idx ? anchor : a))
            : [...prev, anchor];

        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        } catch {
          // Storage full
        }
        return updated;
      });

      return anchor;
    },
    [capabilities.webxrAnchors],
  );

  // -------------------------------------------------------------------
  // Restore anchors
  // -------------------------------------------------------------------

  /**
   * Restore anchors from persistence.
   *
   * - When a live XR session with the Anchors API is available, it
   *   attempts to re-request each stored XRAnchor by UUID and reads
   *   the updated pose.
   * - Falls back to localStorage positions otherwise.
   *
   * Returns the list of restored anchors (with possibly updated positions).
   */
  const restoreAnchors = useCallback(
    async (
      session?: XRSession,
      refSpace?: XRReferenceSpace,
    ): Promise<SpatialAnchor[]> => {
      // Start with localStorage data
      let stored: SpatialAnchor[] = [];
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        stored = raw ? JSON.parse(raw) : [];
      } catch {
        stored = [];
      }

      if (!session || !refSpace || !capabilities.webxrAnchors) {
        setAnchors(stored);
        return stored;
      }

      // Attempt to restore via the persistent anchors API.
      // The WebXR Anchors Module (when supported) exposes
      // `session.restorePersistentAnchor(uuid)`.
      const restoreFn = (
        session as unknown as {
          restorePersistentAnchor?: (
            uuid: string,
          ) => Promise<{
            anchorSpace: XRSpace;
            uuid: string;
            delete: () => void;
          }>;
        }
      ).restorePersistentAnchor;

      if (typeof restoreFn !== "function") {
        setAnchors(stored);
        return stored;
      }

      const map = anchorMapRef.current;
      const restored: SpatialAnchor[] = [];

      for (const anchor of stored) {
        if (!anchor.xrAnchorUUID) {
          // No XR anchor — keep localStorage position
          restored.push(anchor);
          continue;
        }

        try {
          const xrAnchor = await restoreFn.call(session, anchor.xrAnchorUUID);
          liveXRAnchorRef.current.set(anchor.id, xrAnchor);

          // We'll read the updated pose on the next frame.
          // For now, keep stored position; the frame loop will refine it.
          restored.push(anchor);
        } catch {
          // Anchor no longer valid — keep localStorage fallback
          delete map[anchor.xrAnchorUUID];
          restored.push({ ...anchor, xrAnchorUUID: null });
        }
      }

      saveAnchorMap(map);
      setAnchors(restored);

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(restored));
      } catch {
        // Ignore
      }

      return restored;
    },
    [capabilities.webxrAnchors],
  );

  // -------------------------------------------------------------------
  // Clear
  // -------------------------------------------------------------------

  /**
   * Remove all saved anchors — both localStorage and live XR anchors.
   */
  const clearAnchors = useCallback(() => {
    // Delete live XR anchors
    for (const [, xrAnchor] of liveXRAnchorRef.current) {
      try {
        (xrAnchor as { delete?: () => void }).delete?.();
      } catch {
        // Ignore
      }
    }
    liveXRAnchorRef.current.clear();
    anchorMapRef.current = {};

    setAnchors([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(XR_ANCHOR_MAP_KEY);
    } catch {
      // Ignore
    }
  }, []);

  // -------------------------------------------------------------------
  // Legacy helpers (preserved for backwards compatibility)
  // -------------------------------------------------------------------

  const saveAnchor = useCallback(
    (
      id: string,
      position: [number, number, number],
      rotation: [number, number, number] = [0, 0, 0],
      data: Record<string, unknown> = {},
    ) => {
      // Delegate to createAnchor without XR frame (localStorage-only path)
      void createAnchor(id, position, rotation, data);
    },
    [createAnchor],
  );

  const removeAnchor = useCallback((id: string) => {
    // Clean up any live XR anchor
    const xrAnchor = liveXRAnchorRef.current.get(id);
    if (xrAnchor) {
      try {
        (xrAnchor as { delete?: () => void }).delete?.();
      } catch {
        // Ignore
      }
      liveXRAnchorRef.current.delete(id);
    }

    setAnchors((prev) => {
      const removed = prev.find((a) => a.id === id);
      if (removed?.xrAnchorUUID) {
        delete anchorMapRef.current[removed.xrAnchorUUID];
        saveAnchorMap(anchorMapRef.current);
      }
      const updated = prev.filter((a) => a.id !== id);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // Ignore
      }
      return updated;
    });
  }, []);

  const getAnchor = useCallback(
    (id: string): SpatialAnchor | undefined => {
      return anchors.find((a) => a.id === id);
    },
    [anchors],
  );

  // -------------------------------------------------------------------
  // Floor dock helper
  // -------------------------------------------------------------------

  /**
   * Calculate the Y position for a panel docked at floor level + offset.
   * Uses the detected floor plane if available, otherwise defaults to 1.2 m.
   */
  const getFloorDockY = useCallback(
    (offset: number = FLOOR_DOCK_HEIGHT): number => {
      return (floorY ?? 0) + offset;
    },
    [floorY],
  );

  return {
    // State
    anchors,
    capabilities,
    floorY,

    // Primary API
    createAnchor,
    restoreAnchors,
    clearAnchors,

    // Floor detection
    detectCapabilities,
    detectFloorPlane,
    getFloorDockY,

    // Legacy API (backwards compatible)
    saveAnchor,
    removeAnchor,
    getAnchor,
  };
}
