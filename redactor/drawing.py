from __future__ import annotations

from PIL import Image, ImageDraw


TYPE_COLORS = {
    "FACE": "#e6194B",
    "LICENSE_PLATE": "#3cb44b",
    "QR_CODE": "#4363d8",
    "TV_MONITOR": "#911eb4",
}


def _bbox_pixels(bbox, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    left = max(0, int(round(min(x1, x2))))
    top = max(0, int(round(min(y1, y2))))
    right = min(width, int(round(max(x1, x2))))
    bottom = min(height, int(round(max(y1, y2))))
    if right <= left:
        right = left + 1
    if bottom <= top:
        bottom = top + 1
    return (left, top, right, bottom)


def draw_boxes(
    image: Image.Image,
    detections: list[dict],
    show_labels: bool = True,
    filled: bool = False,
) -> Image.Image:
    """Overlay bounding boxes on a copy of the image (for preview/debug)."""
    overlay = image.copy()
    width, height = overlay.size
    draw = ImageDraw.Draw(overlay)
    for det in detections:
        bbox = det.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = _bbox_pixels(bbox, width, height)
        color = TYPE_COLORS.get(det.get("type", ""), "#ffffff")
        if filled:
            draw.rectangle([x1, y1, x2, y2], fill=color)
        else:
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            if show_labels:
                label = f"{det.get('type', '')} {det.get('confidence', 0.0):.2f}"
                draw.rectangle([x1, y1 - 18, x1 + 8 * len(label) + 8, y1], fill=color)
                draw.text((x1 + 4, y1 - 16), label, fill="#000000")
    return overlay