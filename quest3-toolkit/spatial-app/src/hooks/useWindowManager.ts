import { useState, useCallback, useRef } from "react";
import type { Vector3Tuple } from "three";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ManagedPanel {
  id: string;
  position: Vector3Tuple;
  /** Width/height in metres used for edge detection. */
  size: [number, number];
  /** Optional group key — grouped panels move together. */
  groupId: string | null;
}

export type LayoutPreset = "side-by-side" | "stacked" | "grid";

export type SnapZone = "left" | "right" | "top" | "bottom";

export interface SnapIndicator {
  /** Panel being snapped *to*. */
  targetId: string;
  zone: SnapZone;
  /** World position of the snap guide line / glow. */
  position: Vector3Tuple;
}

const LAYOUT_PRESETS: LayoutPreset[] = ["side-by-side", "stacked", "grid"];

/** Gap between snapped panels in metres. */
const SNAP_GAP = 0.02;

/** Distance (metres) from an edge at which the snap indicator activates. */
const SNAP_THRESHOLD = 0.08;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Window-tiling manager for the spatial workspace.
 *
 * Tracks open panels, provides snap-zone detection, layout presets,
 * and panel grouping so that grouped panels move together.
 *
 * Exports:
 *   panels          – current list of managed panels
 *   snapIndicator   – active snap guide (or null)
 *   currentPreset   – last-applied layout preset
 *   registerPanel   – add a panel to the manager
 *   unregisterPanel – remove a panel
 *   updatePosition  – move a panel (triggers snap detection)
 *   snapPanel       – commit a snap: position the panel at the snap zone
 *   groupPanels     – assign panels to the same group
 *   ungroupPanel    – remove a panel from its group
 *   layoutPreset    – apply a named layout to all (or grouped) panels
 *   cyclePreset     – cycle through presets (double-pinch on grab bar)
 */
export function useWindowManager() {
  const [panels, setPanels] = useState<ManagedPanel[]>([]);
  const [snapIndicator, setSnapIndicator] = useState<SnapIndicator | null>(null);
  const [currentPreset, setCurrentPreset] = useState<LayoutPreset>("side-by-side");
  const presetIndex = useRef(0);

  // -------------------------------------------------------------------
  // Panel registration
  // -------------------------------------------------------------------

  const registerPanel = useCallback(
    (id: string, position: Vector3Tuple, size: [number, number] = [0.6, 0.45]) => {
      setPanels((prev) => {
        if (prev.some((p) => p.id === id)) return prev;
        return [...prev, { id, position, size, groupId: null }];
      });
    },
    [],
  );

  const unregisterPanel = useCallback((id: string) => {
    setPanels((prev) => prev.filter((p) => p.id !== id));
    setSnapIndicator((cur) => (cur?.targetId === id ? null : cur));
  }, []);

  // -------------------------------------------------------------------
  // Position updates & snap detection
  // -------------------------------------------------------------------

  /**
   * Call on every drag move. Detects proximity to other panels' edges
   * and activates / clears the snap indicator accordingly.
   */
  const updatePosition = useCallback(
    (id: string, newPos: Vector3Tuple) => {
      setPanels((prev) =>
        prev.map((p) => (p.id === id ? { ...p, position: newPos } : p)),
      );

      // Find the moving panel's size
      const movingPanel = panels.find((p) => p.id === id);
      if (!movingPanel) {
        setSnapIndicator(null);
        return;
      }

      const [mw, mh] = movingPanel.size;

      let bestSnap: SnapIndicator | null = null;
      let bestDist = SNAP_THRESHOLD;

      for (const other of panels) {
        if (other.id === id) continue;

        const [ow, oh] = other.size;
        const [ox, oy, oz] = other.position;

        // Right edge of target → left edge of moving
        const rightEdge = ox + ow / 2 + SNAP_GAP + mw / 2;
        const dRight = Math.abs(newPos[0] - rightEdge);
        if (dRight < bestDist && Math.abs(newPos[1] - oy) < oh) {
          bestDist = dRight;
          bestSnap = {
            targetId: other.id,
            zone: "right",
            position: [ox + ow / 2 + SNAP_GAP / 2, oy, oz],
          };
        }

        // Left edge of target → right edge of moving
        const leftEdge = ox - ow / 2 - SNAP_GAP - mw / 2;
        const dLeft = Math.abs(newPos[0] - leftEdge);
        if (dLeft < bestDist && Math.abs(newPos[1] - oy) < oh) {
          bestDist = dLeft;
          bestSnap = {
            targetId: other.id,
            zone: "left",
            position: [ox - ow / 2 - SNAP_GAP / 2, oy, oz],
          };
        }

        // Top edge of target → bottom of moving
        const topEdge = oy + oh / 2 + SNAP_GAP + mh / 2;
        const dTop = Math.abs(newPos[1] - topEdge);
        if (dTop < bestDist && Math.abs(newPos[0] - ox) < ow) {
          bestDist = dTop;
          bestSnap = {
            targetId: other.id,
            zone: "top",
            position: [ox, oy + oh / 2 + SNAP_GAP / 2, oz],
          };
        }

        // Bottom edge of target → top of moving
        const bottomEdge = oy - oh / 2 - SNAP_GAP - mh / 2;
        const dBottom = Math.abs(newPos[1] - bottomEdge);
        if (dBottom < bestDist && Math.abs(newPos[0] - ox) < ow) {
          bestDist = dBottom;
          bestSnap = {
            targetId: other.id,
            zone: "bottom",
            position: [ox, oy - oh / 2 - SNAP_GAP / 2, oz],
          };
        }
      }

      setSnapIndicator(bestSnap);
    },
    [panels],
  );

  // -------------------------------------------------------------------
  // Snap commit
  // -------------------------------------------------------------------

  /**
   * Snap `panelId` to the current snap indicator position.
   * Call on pointer-up / drag-end.
   * Returns the snapped position (or null if no active indicator).
   */
  const snapPanel = useCallback(
    (panelId: string): Vector3Tuple | null => {
      if (!snapIndicator) return null;

      const target = panels.find((p) => p.id === snapIndicator.targetId);
      const moving = panels.find((p) => p.id === panelId);
      if (!target || !moving) return null;

      const [tw, th] = target.size;
      const [mw, mh] = moving.size;
      const [tx, ty, tz] = target.position;
      let snapped: Vector3Tuple;

      switch (snapIndicator.zone) {
        case "right":
          snapped = [tx + tw / 2 + SNAP_GAP + mw / 2, ty, tz];
          break;
        case "left":
          snapped = [tx - tw / 2 - SNAP_GAP - mw / 2, ty, tz];
          break;
        case "top":
          snapped = [tx, ty + th / 2 + SNAP_GAP + mh / 2, tz];
          break;
        case "bottom":
          snapped = [tx, ty - th / 2 - SNAP_GAP - mh / 2, tz];
          break;
      }

      setPanels((prev) =>
        prev.map((p) => (p.id === panelId ? { ...p, position: snapped } : p)),
      );
      setSnapIndicator(null);
      return snapped;
    },
    [snapIndicator, panels],
  );

  // -------------------------------------------------------------------
  // Grouping
  // -------------------------------------------------------------------

  /**
   * Group the given panel IDs together. Grouped panels translate as a unit
   * when any member is dragged.
   */
  const groupPanels = useCallback((ids: string[], groupId?: string) => {
    const gid = groupId ?? `group-${Date.now()}`;
    setPanels((prev) =>
      prev.map((p) => (ids.includes(p.id) ? { ...p, groupId: gid } : p)),
    );
  }, []);

  const ungroupPanel = useCallback((id: string) => {
    setPanels((prev) =>
      prev.map((p) => (p.id === id ? { ...p, groupId: null } : p)),
    );
  }, []);

  /**
   * Move all panels sharing the same group by a delta vector.
   * Useful when one grouped panel is dragged.
   */
  const moveGroup = useCallback(
    (groupId: string, delta: Vector3Tuple) => {
      setPanels((prev) =>
        prev.map((p) => {
          if (p.groupId !== groupId) return p;
          return {
            ...p,
            position: [
              p.position[0] + delta[0],
              p.position[1] + delta[1],
              p.position[2] + delta[2],
            ],
          };
        }),
      );
    },
    [],
  );

  // -------------------------------------------------------------------
  // Layout presets
  // -------------------------------------------------------------------

  /**
   * Apply a tiling layout to all panels (or only panels in `filterGroupId`).
   */
  const layoutPreset = useCallback(
    (preset: LayoutPreset, filterGroupId?: string) => {
      setCurrentPreset(preset);

      setPanels((prev) => {
        const target = filterGroupId
          ? prev.filter((p) => p.groupId === filterGroupId)
          : prev;
        const rest = filterGroupId
          ? prev.filter((p) => p.groupId !== filterGroupId)
          : [];

        if (target.length === 0) return prev;

        const arranged = applyPreset(target, preset);
        return [...rest, ...arranged];
      });
    },
    [],
  );

  /**
   * Cycle through layout presets. Intended for double-pinch on grab bar.
   */
  const cyclePreset = useCallback(
    (filterGroupId?: string) => {
      presetIndex.current = (presetIndex.current + 1) % LAYOUT_PRESETS.length;
      const next = LAYOUT_PRESETS[presetIndex.current];
      layoutPreset(next, filterGroupId);
    },
    [layoutPreset],
  );

  return {
    panels,
    snapIndicator,
    currentPreset,
    registerPanel,
    unregisterPanel,
    updatePosition,
    snapPanel,
    groupPanels,
    ungroupPanel,
    moveGroup,
    layoutPreset,
    cyclePreset,
  };
}

// ---------------------------------------------------------------------------
// Internal layout helpers
// ---------------------------------------------------------------------------

/**
 * Position panels according to a preset layout. Returns new panel objects
 * with updated positions, preserving all other fields.
 */
function applyPreset(panels: ManagedPanel[], preset: LayoutPreset): ManagedPanel[] {
  if (panels.length === 0) return panels;

  // Use the centroid of existing panels as the layout origin.
  const cx =
    panels.reduce((sum, p) => sum + p.position[0], 0) / panels.length;
  const cy =
    panels.reduce((sum, p) => sum + p.position[1], 0) / panels.length;
  const cz =
    panels.reduce((sum, p) => sum + p.position[2], 0) / panels.length;

  switch (preset) {
    case "side-by-side":
      return layoutSideBySide(panels, cx, cy, cz);
    case "stacked":
      return layoutStacked(panels, cx, cy, cz);
    case "grid":
      return layoutGrid(panels, cx, cy, cz);
  }
}

function layoutSideBySide(
  panels: ManagedPanel[],
  cx: number,
  cy: number,
  cz: number,
): ManagedPanel[] {
  const totalWidth = panels.reduce(
    (sum, p) => sum + p.size[0] + SNAP_GAP,
    -SNAP_GAP,
  );
  let x = cx - totalWidth / 2;

  return panels.map((p) => {
    const pos: Vector3Tuple = [x + p.size[0] / 2, cy, cz];
    x += p.size[0] + SNAP_GAP;
    return { ...p, position: pos };
  });
}

function layoutStacked(
  panels: ManagedPanel[],
  cx: number,
  cy: number,
  cz: number,
): ManagedPanel[] {
  const totalHeight = panels.reduce(
    (sum, p) => sum + p.size[1] + SNAP_GAP,
    -SNAP_GAP,
  );
  let y = cy + totalHeight / 2;

  return panels.map((p) => {
    const pos: Vector3Tuple = [cx, y - p.size[1] / 2, cz];
    y -= p.size[1] + SNAP_GAP;
    return { ...p, position: pos };
  });
}

function layoutGrid(
  panels: ManagedPanel[],
  cx: number,
  cy: number,
  cz: number,
): ManagedPanel[] {
  const cols = 2; // 2x2
  return panels.map((p, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = cx + (col - (cols - 1) / 2) * (p.size[0] + SNAP_GAP);
    const y = cy - (row - Math.floor((panels.length - 1) / cols / 2)) * (p.size[1] + SNAP_GAP);
    return { ...p, position: [x, y, cz] };
  });
}
