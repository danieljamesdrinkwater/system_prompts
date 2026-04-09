/**
 * WebXR utility functions for the spatial workspace.
 */

/** Check if the browser supports immersive AR (passthrough on Quest 3). */
export async function isARSupported(): Promise<boolean> {
  if (!navigator.xr) return false;
  return navigator.xr.isSessionSupported("immersive-ar").catch(() => false);
}

/** Check if the browser supports immersive VR. */
export async function isVRSupported(): Promise<boolean> {
  if (!navigator.xr) return false;
  return navigator.xr.isSessionSupported("immersive-vr").catch(() => false);
}

/** Check if hand tracking is available as an optional feature. */
export async function isHandTrackingSupported(): Promise<boolean> {
  if (!navigator.xr) return false;
  try {
    // Attempt to create a session with hand-tracking to check support
    const session = await navigator.xr.requestSession("immersive-ar", {
      requiredFeatures: ["hand-tracking"],
    });
    session.end();
    return true;
  } catch {
    return false;
  }
}

/** Get the preferred session mode for this device. */
export async function getPreferredMode(): Promise<XRSessionMode | null> {
  if (await isARSupported()) return "immersive-ar";
  if (await isVRSupported()) return "immersive-vr";
  return null;
}
