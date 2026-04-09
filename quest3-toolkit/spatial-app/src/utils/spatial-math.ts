/**
 * 3D positioning, snapping, and layout math for spatial panels.
 */

import type { Vector3Tuple } from "three";

/** Snap a value to the nearest grid point. */
export function snapToGrid(value: number, gridSize: number): number {
  if (gridSize <= 0) return value;
  return Math.round(value / gridSize) * gridSize;
}

/** Snap a 3D position to a grid. */
export function snapPositionToGrid(
  position: Vector3Tuple,
  gridSize: number
): Vector3Tuple {
  return [
    snapToGrid(position[0], gridSize),
    snapToGrid(position[1], gridSize),
    snapToGrid(position[2], gridSize),
  ];
}

/** Calculate distance between two 3D points. */
export function distance(a: Vector3Tuple, b: Vector3Tuple): number {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  const dz = a[2] - b[2];
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

/** Linearly interpolate between two values. */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Linearly interpolate between two 3D positions. */
export function lerpPosition(
  a: Vector3Tuple,
  b: Vector3Tuple,
  t: number
): Vector3Tuple {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

/**
 * Arrange N panels in a curved arc around the user.
 * Returns an array of positions for each panel.
 */
export function arcLayout(
  count: number,
  radius: number = 1.2,
  arcAngle: number = Math.PI * 0.6,
  centerY: number = 1.5
): Vector3Tuple[] {
  const positions: Vector3Tuple[] = [];
  for (let i = 0; i < count; i++) {
    const t = count === 1 ? 0 : (i / (count - 1)) * arcAngle - arcAngle / 2;
    const x = Math.sin(t) * radius;
    const z = -Math.cos(t) * radius;
    positions.push([x, centerY, z]);
  }
  return positions;
}

/**
 * Arrange panels in a grid pattern in front of the user.
 */
export function gridLayout(
  count: number,
  columns: number = 3,
  spacing: number = 0.65,
  startY: number = 1.8,
  depth: number = -1.2
): Vector3Tuple[] {
  const positions: Vector3Tuple[] = [];
  for (let i = 0; i < count; i++) {
    const col = i % columns;
    const row = Math.floor(i / columns);
    const x = (col - (columns - 1) / 2) * spacing;
    const y = startY - row * (spacing * 0.8);
    positions.push([x, y, depth]);
  }
  return positions;
}

/** Clamp a value between min and max. */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
