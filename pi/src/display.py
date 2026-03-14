"""Display renderer — composites camera feeds with detection overlays."""

import logging

import cv2
import numpy as np

from alert import AlertLevel
from config import Config

log = logging.getLogger("display")

# Alert level colours (BGR)
COLOURS = {
    AlertLevel.NONE: (200, 200, 200),    # Grey
    AlertLevel.CAUTION: (0, 200, 255),    # Amber
    AlertLevel.WARNING: (0, 0, 255),      # Red
    AlertLevel.DANGER: (0, 0, 255),       # Red (flashing)
}

ZONE_LABELS = {
    "left": "LEFT",
    "forward": "FWD",
    "rear": "REAR",
}


class Display:
    """Renders composite camera view with detection overlays on 7" screen."""

    def __init__(self, config: Config):
        self.config = config
        self.width = config.display_width
        self.height = config.display_height
        self._window_name = "HGV-ADAS"
        self._frame_count = 0

    def render(self, frames: dict, detections: dict, alerts: list, radar_data: dict):
        """Render all camera feeds with overlays into a single composite."""
        # Create composite canvas
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Layout: left cam takes left half, forward+rear stack on right
        cam_order = ["left", "forward", "rear"]
        available = [(cid, frames[cid]) for cid in cam_order if cid in frames]

        if not available:
            return

        if len(available) == 1:
            # Single camera — full screen
            cid, frame = available[0]
            resized = cv2.resize(frame, (self.width, self.height))
            self._draw_detections(resized, detections.get(cid, []))
            canvas = resized
        elif len(available) == 2:
            # Two cameras — side by side
            half_w = self.width // 2
            for i, (cid, frame) in enumerate(available):
                resized = cv2.resize(frame, (half_w, self.height))
                self._draw_detections(resized, detections.get(cid, []))
                self._draw_zone_label(resized, cid)
                canvas[:, i * half_w : (i + 1) * half_w] = resized
        else:
            # Three cameras: left takes left half, forward+rear stack on right
            half_w = self.width // 2
            half_h = self.height // 2

            # Left camera — large panel
            if "left" in frames:
                left = cv2.resize(frames["left"], (half_w, self.height))
                self._draw_detections(left, detections.get("left", []))
                self._draw_zone_label(left, "left")
                canvas[:, :half_w] = left

            # Forward — top right
            if "forward" in frames:
                fwd = cv2.resize(frames["forward"], (half_w, half_h))
                self._draw_detections(fwd, detections.get("forward", []))
                self._draw_zone_label(fwd, "forward")
                canvas[:half_h, half_w:] = fwd

            # Rear — bottom right
            if "rear" in frames:
                rear = cv2.resize(frames["rear"], (half_w, half_h))
                self._draw_detections(rear, detections.get("rear", []))
                self._draw_zone_label(rear, "rear")
                canvas[half_h:, half_w:] = rear

        # Draw alert banner at top if any active alerts
        self._draw_alert_banner(canvas, alerts)

        # Draw radar distance indicators
        self._draw_radar_status(canvas, radar_data)

        # Show
        cv2.imshow(self._window_name, canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            raise KeyboardInterrupt

        self._frame_count += 1

    def close(self):
        cv2.destroyAllWindows()

    def _draw_detections(self, frame, detections):
        """Draw bounding boxes and labels on a camera frame."""
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]

            # Scale bbox to resized frame dimensions
            # (detections are in original frame coords)
            colour = (0, 255, 0)  # Default green
            if det.distance_estimate:
                if det.distance_estimate < 1.5:
                    colour = (0, 0, 255)  # Red
                elif det.distance_estimate < 3.0:
                    colour = (0, 128, 255)  # Orange
                elif det.distance_estimate < 6.0:
                    colour = (0, 200, 255)  # Amber

            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)

            label = f"{det.class_name} {det.confidence:.0%}"
            if det.distance_estimate:
                label += f" ~{det.distance_estimate:.1f}m"

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), colour, -1)
            cv2.putText(
                frame, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1,
            )

    def _draw_zone_label(self, frame, cam_id: str):
        """Draw zone label in top-left corner."""
        label = ZONE_LABELS.get(cam_id, cam_id.upper())
        cv2.putText(
            frame, label, (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
        )

    def _draw_alert_banner(self, canvas, alerts):
        """Draw alert status banner at top of composite view."""
        if not alerts:
            return

        max_alert = max(alerts, key=lambda a: a.level)
        if max_alert.level == AlertLevel.NONE:
            return

        colour = COLOURS[max_alert.level]

        # Flash effect for DANGER
        if max_alert.level == AlertLevel.DANGER and self._frame_count % 10 < 5:
            colour = (255, 255, 255)

        # Banner bar
        cv2.rectangle(canvas, (0, 0), (self.width, 35), colour, -1)

        text = max_alert.message.upper()
        cv2.putText(
            canvas, text, (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2,
        )

    def _draw_radar_status(self, canvas, radar_data: dict):
        """Draw radar distance readouts in bottom-left corner."""
        y = self.height - 20
        for pod_id, data in sorted(radar_data.items()):
            dist = data.get("distance", 0)
            if dist <= 0:
                continue
            label = f"{pod_id}: {dist:.1f}m"
            colour = (0, 255, 0) if dist > 3.0 else (0, 0, 255)
            cv2.putText(
                canvas, label, (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1,
            )
            y -= 20
