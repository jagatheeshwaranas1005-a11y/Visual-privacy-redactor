from __future__ import annotations

from PIL import Image

from .config import AppConfig


def mock_detections(image: Image.Image, config: AppConfig) -> list[dict]:
    """Deterministic demo detections so the UI can run without an API key.

    Uses the image dimensions so boxes land inside the picture regardless of size.
    """
    width, height = image.size

    face_box = [
        int(width * 0.20),
        int(height * 0.10),
        int(width * 0.38),
        int(height * 0.38),
    ]
    plate_box = [
        int(width * 0.42),
        int(height * 0.75),
        int(width * 0.70),
        int(height * 0.84),
    ]
    qr_box = [
        int(width * 0.82),
        int(height * 0.06),
        int(width * 0.97),
        int(height * 0.24),
    ]
    screen_box = [
        int(width * 0.62),
        int(height * 0.22),
        int(width * 0.98),
        int(height * 0.60),
    ]

    detections = [
        {"type": "FACE", "confidence": 0.98, "bbox": face_box},
        {"type": "LICENSE_PLATE", "confidence": 0.94, "bbox": plate_box},
        {"type": "QR_CODE", "confidence": 0.91, "bbox": qr_box},
        {"type": "TV_MONITOR", "confidence": 0.87, "bbox": screen_box},
    ]

    enabled = config.enabled_types
    return [d for d in detections if d["type"] in enabled]