from __future__ import annotations

import io
import json

from PIL import Image
from google import genai
from google.genai import types

from .config import AppConfig

DETECTION_PROMPT = """You are a privacy-redaction assistant for a security tool.
Analyze the image and find privacy-sensitive objects. Look specifically for:
FACE, LICENSE_PLATE, QR_CODE, TV_MONITOR.

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:
{"detections": [{"type": "FACE", "confidence": 0.98, "bbox": [x1, y1, x2, y2]}]}

Rules:
- bbox is [left, top, right, bottom] in PIXEL coordinates (integers).
  x1=left, y1=top, x2=right, y2=bottom relative to the image you see.
- confidence is a number 0.0 to 1.0.
- Do NOT extract, transcribe, or read any text. Detection only.
- If nothing sensitive is present, return {"detections": []}.
- For privacy software, false negatives are more dangerous than false positives: when in doubt,
  include the object with a lower confidence score rather than omitting it.
"""


class GeminiDetectionError(Exception):
    pass


def _normalize(detection: dict) -> dict | None:
    dtype = str(detection.get("type", "")).strip().upper()
    bbox = detection.get("bbox")
    if not dtype or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        confidence = max(0.0, min(1.0, float(detection.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "type": dtype,
        "confidence": confidence,
        "bbox": [float(v) for v in bbox],
    }


def _parse_response(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    data = json.loads(text)
    raw = data.get("detections", []) if isinstance(data, dict) else data
    return [d for d in (_normalize(item) for item in raw) if d is not None]


def _scale_bbox(detection: dict, width: int, height: int) -> dict:
    """Ensure bbox is in pixel space.

    We ask Gemini for pixel coordinates, but defensively handle normalized
    (0..1) if it ignores the prompt. Also clamp to image bounds.
    """
    x1, y1, x2, y2 = detection["bbox"]
    if max(x1, y1, x2, y2) <= 1.0:
        # Fallback: treat as normalized and scale
        detection["bbox"] = [x1 * width, y1 * height, x2 * width, y2 * height]
    # Clamp to image bounds
    detection["bbox"] = [
        max(0, min(width, detection["bbox"][0])),
        max(0, min(height, detection["bbox"][1])),
        max(0, min(width, detection["bbox"][2])),
        max(0, min(height, detection["bbox"][3])),
    ]
    return detection


def detect_with_gemini(image: Image.Image, config: AppConfig, debug: bool = False):
    """Send image to Gemini, return pixel-coordinate detections.

    Raises GeminiDetectionError on API/malformed-response failure.
    Returns (detections, raw_response) if debug=True.
    """
    if not config.has_real_key:
        raise GeminiDetectionError(
            "Gemini API key is not configured. Set GEMINI_API_KEY in .env or enable USE_MOCK."
        )

    client = genai.Client(api_key=config.gemini_api_key)

    width, height = image.size
    prompt = f"{DETECTION_PROMPT}\n\nImage dimensions: {width}x{height} pixels."

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=92)
    image_data = buffer.getvalue()

    response = client.models.generate_content(
        model=config.gemini_model,
        contents=[
            types.Part(
                inline_data=types.Blob(mime_type="image/jpeg", data=image_data)
            ),
            prompt,
        ],
        config={
            "response_mime_type": "application/json",
            "temperature": 0.0,
        },
    )

    text = response.text or ""
    if not text.strip():
        raise GeminiDetectionError("Gemini returned an empty response.")

    try:
        detections = _parse_response(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GeminiDetectionError(f"Could not parse Gemini response as JSON: {exc}") from exc

    scaled = [_scale_bbox(d, width, height) for d in detections]
    return (scaled, text) if debug else scaled