import { useState, useEffect, useCallback } from "react";

interface XRSessionState {
  isSupported: boolean;
  isActive: boolean;
  sessionMode: XRSessionMode | null;
  referenceSpace: XRReferenceSpace | null;
}

/**
 * Hook for managing WebXR session lifecycle.
 * Checks browser support, handles session start/end,
 * and provides the reference space for spatial tracking.
 */
export function useXRSession() {
  const [state, setState] = useState<XRSessionState>({
    isSupported: false,
    isActive: false,
    sessionMode: null,
    referenceSpace: null,
  });

  // Check WebXR support on mount
  useEffect(() => {
    async function checkSupport() {
      if (!navigator.xr) {
        setState((s) => ({ ...s, isSupported: false }));
        return;
      }

      const arSupported = await navigator.xr.isSessionSupported("immersive-ar").catch(() => false);
      const vrSupported = await navigator.xr.isSessionSupported("immersive-vr").catch(() => false);

      setState((s) => ({ ...s, isSupported: arSupported || vrSupported }));
    }

    checkSupport();
  }, []);

  const requestSession = useCallback(async (mode: XRSessionMode = "immersive-ar") => {
    if (!navigator.xr) return null;

    try {
      const session = await navigator.xr.requestSession(mode, {
        requiredFeatures: ["local-floor"],
        optionalFeatures: [
          "hand-tracking",
          "hit-test",
          "depth-sensing",
          "anchors",
          "eye-tracking",
        ],
      });

      const refSpace = await session.requestReferenceSpace("local-floor");

      session.addEventListener("end", () => {
        setState((s) => ({
          ...s,
          isActive: false,
          sessionMode: null,
          referenceSpace: null,
        }));
      });

      setState((s) => ({
        ...s,
        isActive: true,
        sessionMode: mode,
        referenceSpace: refSpace,
      }));

      return session;
    } catch (err) {
      console.error("Failed to start XR session:", err);
      return null;
    }
  }, []);

  return {
    ...state,
    requestSession,
  };
}
