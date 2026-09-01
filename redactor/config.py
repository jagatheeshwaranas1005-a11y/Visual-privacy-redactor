from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "evidence"


SENSITIVE_TYPES = [
    "FACE",
    "LICENSE_PLATE",
    "QR_CODE",
    "TV_MONITOR",
]


REDACTION_METHODS = ("blur", "pixelate", "blackout")


DEFAULT_REDACTION_RULES: dict[str, str] = {
    "FACE": "blur",
    "LICENSE_PLATE": "blur",
    "QR_CODE": "pixelate",
    "TV_MONITOR": "blur",
}


CONFIDENCE_AUTO = 0.90
CONFIDENCE_REVIEW = 0.70


@dataclass
class AppConfig:
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    use_mock: bool = False

    auto_threshold: float = CONFIDENCE_AUTO
    review_threshold: float = CONFIDENCE_REVIEW

    redaction_rules: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_REDACTION_RULES)
    )

    enabled_types: set[str] = field(
        default_factory=lambda: set(SENSITIVE_TYPES)
    )

    @property
    def has_real_key(self) -> bool:
        return bool(self.gemini_api_key) and self.gemini_api_key != "your_gemini_api_key_here"

    def ensure_evidence_dir(self) -> Path:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        return EVIDENCE_DIR


def load_config() -> AppConfig:
    load_dotenv(REPO_ROOT / ".env")
    use_mock_raw = os.getenv("USE_MOCK", "false").strip().lower()
    use_mock = use_mock_raw in ("1", "true", "yes", "on")
    cfg = AppConfig(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash",
        use_mock=use_mock,
    )
    if not cfg.has_real_key:
        cfg.use_mock = True
    return cfg
