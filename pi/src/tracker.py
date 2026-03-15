"""Multi-object tracker — IoU-based tracking across frames with velocity estimation."""

import logging
import time
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("tracker")

_next_track_id = 0


def _new_track_id() -> int:
    global _next_track_id
    _next_track_id += 1
    return _next_track_id


@dataclass
class Track:
    """A tracked object persisting across frames."""

    track_id: int
    class_name: str
    bbox: tuple  # (x1, y1, x2, y2)
    confidence: float
    distance_estimate: float = None
    age: int = 0          # Frames since creation
    hits: int = 1         # Total frames matched
    misses: int = 0       # Consecutive frames without match
    velocity: tuple = (0.0, 0.0)  # Pixels/frame (dx, dy) of centre
    _history: list = field(default_factory=list)  # Recent centres + timestamps

    @property
    def centre(self) -> tuple:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def is_confirmed(self) -> bool:
        return self.hits >= 3

    @property
    def speed_px_per_frame(self) -> float:
        vx, vy = self.velocity
        return (vx ** 2 + vy ** 2) ** 0.5

    def predict(self) -> tuple:
        """Predict next bbox position using velocity."""
        vx, vy = self.velocity
        x1, y1, x2, y2 = self.bbox
        return (x1 + vx, y1 + vy, x2 + vx, y2 + vy)

    def update(self, det):
        """Update track with a matched detection."""
        old_cx, old_cy = self.centre

        self.bbox = det.bbox
        self.class_name = det.class_name
        self.confidence = det.confidence
        self.distance_estimate = det.distance_estimate
        self.hits += 1
        self.misses = 0
        self.age += 1

        new_cx, new_cy = self.centre
        now = time.monotonic()
        self._history.append((new_cx, new_cy, now))

        # Keep last 10 positions
        if len(self._history) > 10:
            self._history = self._history[-10:]

        # Compute velocity from last few positions
        if len(self._history) >= 2:
            dx = new_cx - old_cx
            dy = new_cy - old_cy
            # Exponential moving average for smoothing
            alpha = 0.4
            self.velocity = (
                alpha * dx + (1 - alpha) * self.velocity[0],
                alpha * dy + (1 - alpha) * self.velocity[1],
            )

    def mark_missed(self):
        self.misses += 1
        self.age += 1


def _iou(box_a, box_b) -> float:
    """Compute intersection-over-union of two bboxes."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0

    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])

    return inter / (area_a + area_b - inter)


class Tracker:
    """Greedy IoU multi-object tracker.

    Matches new detections to existing tracks by IoU, using predicted
    positions. Creates new tracks for unmatched detections and removes
    tracks that go stale.
    """

    def __init__(self, config):
        self.iou_threshold = getattr(config, "tracker_iou_threshold", 0.25)
        self.max_misses = getattr(config, "tracker_max_misses", 8)
        self.tracks: dict[int, Track] = {}  # track_id → Track

    def update(self, detections: list) -> list:
        """Match detections to existing tracks. Returns list of Track objects.

        Args:
            detections: list of Detection objects from detector.

        Returns:
            List of active Track objects (confirmed + tentative).
        """
        if not self.tracks and not detections:
            return []

        # Predict existing track positions
        predicted_boxes = {}
        for tid, track in self.tracks.items():
            predicted_boxes[tid] = track.predict()

        # Compute IoU matrix between predictions and new detections
        track_ids = list(self.tracks.keys())
        matched_tracks = set()
        matched_dets = set()

        if track_ids and detections:
            # Build cost matrix
            iou_matrix = np.zeros((len(track_ids), len(detections)))
            for i, tid in enumerate(track_ids):
                for j, det in enumerate(detections):
                    iou_matrix[i, j] = _iou(predicted_boxes[tid], det.bbox)

            # Greedy matching — highest IoU first
            while True:
                if iou_matrix.size == 0:
                    break
                idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                best_iou = iou_matrix[idx]

                if best_iou < self.iou_threshold:
                    break

                ti, di = idx
                tid = track_ids[ti]

                self.tracks[tid].update(detections[di])
                matched_tracks.add(tid)
                matched_dets.add(di)

                # Zero out matched row and column
                iou_matrix[ti, :] = 0
                iou_matrix[:, di] = 0

        # Mark unmatched tracks as missed
        for tid in track_ids:
            if tid not in matched_tracks:
                self.tracks[tid].mark_missed()

        # Create new tracks for unmatched detections
        for j, det in enumerate(detections):
            if j not in matched_dets:
                tid = _new_track_id()
                track = Track(
                    track_id=tid,
                    class_name=det.class_name,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    distance_estimate=det.distance_estimate,
                )
                self.tracks[tid] = track

        # Remove stale tracks
        stale = [
            tid for tid, t in self.tracks.items()
            if t.misses > self.max_misses
        ]
        for tid in stale:
            del self.tracks[tid]

        return list(self.tracks.values())
