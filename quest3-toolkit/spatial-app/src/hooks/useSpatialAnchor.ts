import { useState, useCallback } from "react";

interface SpatialAnchor {
  id: string;
  position: [number, number, number];
  rotation: [number, number, number];
  data: Record<string, unknown>;
}

const STORAGE_KEY = "spatial-workspace-anchors";

/**
 * Hook for persisting panel positions in 3D space.
 * Uses localStorage to save and restore spatial layouts
 * between sessions. When WebXR Anchors API is available,
 * it can be extended to use real-world anchors.
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

  const saveAnchor = useCallback(
    (id: string, position: [number, number, number], rotation: [number, number, number] = [0, 0, 0], data: Record<string, unknown> = {}) => {
      setAnchors((prev) => {
        const existing = prev.findIndex((a) => a.id === id);
        const anchor: SpatialAnchor = { id, position, rotation, data };

        const updated = existing >= 0
          ? prev.map((a, i) => (i === existing ? anchor : a))
          : [...prev, anchor];

        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        } catch {
          // Storage full or unavailable — continue without persistence
        }

        return updated;
      });
    },
    []
  );

  const removeAnchor = useCallback((id: string) => {
    setAnchors((prev) => {
      const updated = prev.filter((a) => a.id !== id);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // Ignore storage errors
      }
      return updated;
    });
  }, []);

  const getAnchor = useCallback(
    (id: string): SpatialAnchor | undefined => {
      return anchors.find((a) => a.id === id);
    },
    [anchors]
  );

  const clearAnchors = useCallback(() => {
    setAnchors([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore
    }
  }, []);

  return { anchors, saveAnchor, removeAnchor, getAnchor, clearAnchors };
}
