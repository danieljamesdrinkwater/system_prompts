"""Tests for camera module."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import numpy as np


def test_encode_jpeg():
    """JPEG encoding should produce bytes."""
    try:
        from app.camera.capture import _encode_jpeg
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _encode_jpeg(frame)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # JPEG magic bytes
        assert result[:2] == b'\xff\xd8'
    except ImportError:
        pytest.skip("OpenCV not installed")


def test_detector_returns_empty_without_model():
    """Detector should return empty list if model not loaded."""
    from app.camera.detector import Detector
    det = Detector()
    # Don't load model, just test _detect directly
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    with patch.dict("sys.modules", {"ultralytics": None}):
        result = det._detect(frame)
        assert result == []
