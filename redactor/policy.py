from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig


@dataclass
class FilteredDetection:
    type: str
    confidence: float
    bbox: list[float]
    method: str
    action: str  # "redacted" | "review"
    boxed: bool

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "method": self.method,
            "action": self.action,
        }


def apply_policy(
    detections: list[dict],
    config: AppConfig,
) -> tuple[list[FilteredDetection], list[FilteredDetection]]:
    """Gate detections by confidence and assign a redaction method.

    Confidence >= auto_threshold -> redact automatically.
    review_threshold <= confidence < auto_threshold -> redact + flag for review.
    confidence < review_threshold -> excluded (not redacted).
    """
    auto = config.auto_threshold
    review = config.review_threshold

    to_redact: list[FilteredDetection] = []
    flagged: list[FilteredDetection] = []

    for det in detections:
        dtype = str(det.get("type", "")).upper()
        if dtype not in config.enabled_types:
            continue
        confidence = float(det.get("confidence", 0.0))
        method = config.redaction_rules.get(dtype, "blur")

        if confidence >= auto:
            to_redact.append(
                FilteredDetection(
                    type=dtype,
                    confidence=confidence,
                    bbox=det.get("bbox", []),
                    method=method,
                    action="redacted",
                    boxed=True,
                )
            )
        elif confidence >= review:
            flagged.append(
                FilteredDetection(
                    type=dtype,
                    confidence=confidence,
                    bbox=det.get("bbox", []),
                    method=method,
                    action="review",
                    boxed=True,
                )
            )
    return to_redact, flagged