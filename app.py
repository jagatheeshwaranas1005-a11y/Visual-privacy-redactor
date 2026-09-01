from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone

import certifi

# Fix SSL cert verification cross-platform
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import streamlit as st
from PIL import Image

from redactor.config import (
    REDACTION_METHODS,
    SENSITIVE_TYPES,
    AppConfig,
    load_config,
)
from redactor.drawing import draw_boxes
from redactor.gemini_client import GeminiDetectionError, detect_with_gemini
from redactor.mock import mock_detections
from redactor.policy import apply_policy
from redactor.redaction import redact_image

PREMIUM_CSS = """
<style>
/* Base container */
.block-container {
    padding-top: 3rem !important;
    padding-bottom: 3rem !important;
}
/* Title & typography */
h1 {
    font-size: 3.5rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.025em;
    margin-bottom: 0.5rem !important;
    background: linear-gradient(135deg, #F8FAFC 0%, #94A3B8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
/* Primary button gradient */
[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}
[data-testid="baseButton-primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
}
/* Secondary buttons */
[data-testid="baseButton-secondary"] {
    border-radius: 8px !important;
    font-weight: 500 !important;
    border: 1px solid #334155 !important;
    background-color: transparent !important;
    transition: all 0.2s ease;
}
[data-testid="baseButton-secondary"]:hover {
    background-color: #1E293B !important;
    border-color: #4F46E5 !important;
    color: #F8FAFC !important;
}
/* Metrics */
[data-testid="stMetricValue"] {
    font-weight: 700 !important;
    color: #4F46E5 !important;
    font-size: 2.5rem !important;
}
/* Uploader */
[data-testid="stFileUploadDropzone"] {
    border: 2px dashed #334155 !important;
    border-radius: 12px !important;
    background-color: #0B0F19 !important;
    padding: 2rem !important;
    transition: all 0.2s ease;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: #4F46E5 !important;
    background-color: #1E293B !important;
}
/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0B0F19 !important;
    border-right: 1px solid #1E293B !important;
}
hr {
    border-color: #1E293B !important;
}
</style>
"""

st.set_page_config(page_title="Visual Privacy Redactor", page_icon="🕶️", layout="wide")

MODES = ("Redact", "Detect", "QC")


def _reset_state() -> None:
    for key in ["results"]:
        st.session_state.pop(key, None)


def _image_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _type_label(dtype: str) -> str:
    return dtype.replace("_", " ").title()


@st.cache_data(show_spinner=False)
def _cached_gemini(image_bytes: bytes, model: str, enabled: tuple[str, ...], debug: bool = False):
    """Cache Gemini calls per image+settings so re-runs don't burn API quota."""
    cfg = AppConfig(gemini_api_key=load_config().gemini_api_key, gemini_model=model)
    cfg.enabled_types = set(enabled)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return detect_with_gemini(image, cfg, debug=debug)


def _run_detection(source: Image.Image, base_config: AppConfig, enabled: set[str], debug: bool = False):
    if base_config.use_mock or not base_config.has_real_key:
        return mock_detections(source, base_config), None
    image_bytes = _image_bytes(source, "JPEG")
    return _cached_gemini(image_bytes, base_config.gemini_model, tuple(sorted(enabled)), debug=debug), None


def main() -> None:
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
    base_config = load_config()

    st.markdown("<h1>The AI Privacy Redactor</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size: 1.25rem; color: #94A3B8; margin-bottom: 2rem; max-width: 800px;'>"
        "Detect and automatically redact sensitive information at scale. "
        "Powered by Gemini vision models for high-accuracy face, plate, and screen detection."
        "</p>",
        unsafe_allow_html=True
    )

    if base_config.use_mock:
        st.info(
            "⚙️ Running in **mock mode** (no Gemini API key set, or USE_MOCK=true). "
            "Detections are simulated."
        )
    elif not base_config.has_real_key:
        st.warning("⚠️ Set GEMINI_API_KEY in `VLM/PR/.env` to enable real detections.")

    with st.sidebar:
        st.header("Mode")
        mode = st.radio(
            "Redaction mode",
            MODES,
            index=0,
            help=(
                "Redact: apply blur/pixelate/blackout. "
                "Detect: boxes only, no alteration. "
                "QC: check an already-blurred image for missed redactions."
            ),
        )

        st.header("Detection")
        enabled_types: set[str] = set()
        for dtype in SENSITIVE_TYPES:
            if st.checkbox(_type_label(dtype), value=True, key=f"chk_{dtype}"):
                enabled_types.add(dtype)

        st.header("Redaction rules")
        rules = {}
        for dtype in SENSITIVE_TYPES:
            rules[dtype] = st.selectbox(
                f"{_type_label(dtype)}",
                REDACTION_METHODS,
                index=REDACTION_METHODS.index(
                    base_config.redaction_rules.get(dtype, "blur")
                ),
                key=f"rule_{dtype}",
            )

        blur_radius = 18
        block_size = 16
        if mode == "Redact":
            st.header("Strength")
            blur_radius = st.slider(
                "Blur smooth level", 5, 50, 18,
                help="Radius of the Gaussian blur applied to faces, plates, screens.",
            )
            block_size = st.slider(
                "Pixelate block size", 4, 40, 16,
                help="Size of the pixel blocks for QR codes.",
            )

        st.header("Confidence thresholds")
        auto_threshold = st.slider(
            "Auto-redact at ≥", 0.50, 1.00, base_config.auto_threshold, 0.05,
            help="Detections at or above this confidence are redacted automatically.",
        )
        review_threshold = st.slider(
            "Mark for review at ≥", 0.50, 1.00, base_config.review_threshold, 0.05,
            help="Detections between review and auto thresholds are redacted + flagged.",
        )
        if review_threshold >= auto_threshold:
            st.error("Review threshold must be below the auto threshold.")
            st.stop()

        if st.button("Reset queue", use_container_width=True):
            _reset_state()

    st.divider()

    uploaded_files = st.file_uploader(
        "Drag & drop one or more images",
        type=["png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        accept_multiple_files=True,
    )

    if uploaded_files is None or not uploaded_files:
        st.stop()

    debug_mode = st.sidebar.checkbox("Debug: show raw Gemini response", value=False)

    if st.button("Analyze & Redact", type="primary", use_container_width=True):
        _reset_state()
        st.session_state["results"] = {}
        total = len(uploaded_files)
        progress = st.progress(0.0, text="Processing queue…")

        for i, uploaded in enumerate(uploaded_files):
            name = uploaded.name
            source = Image.open(uploaded).convert("RGB")
            raw_gemini = None
            try:
                detections, raw_gemini = _run_detection(source, base_config, enabled_types, debug=debug_mode)
            except GeminiDetectionError as exc:
                st.session_state["results"][name] = {"error": str(exc), "raw_gemini": raw_gemini if debug_mode else None}
                progress.progress((i + 1) / total, text=f"Failed: {name}")
                continue

            cfg = AppConfig(
                gemini_api_key=base_config.gemini_api_key,
                gemini_model=base_config.gemini_model,
                use_mock=base_config.use_mock,
                auto_threshold=auto_threshold,
                review_threshold=review_threshold,
                redaction_rules=rules,
                enabled_types=enabled_types,
            )

            to_redact, flagged = apply_policy(detections, cfg)
            all_boxes = [
                (fd.bbox, fd.method) for fd in to_redact
            ] + [
                (fd.bbox, fd.method) for fd in flagged
            ]
            redacted = (
                redact_image(
                    source,
                    all_boxes,
                    blur_radius=blur_radius,
                    block_size=block_size,
                )
                if mode == "Redact"
                else source
            )
            preview = draw_boxes(source, [fd.as_dict() for fd in to_redact + flagged])

            st.session_state["results"][name] = {
                "source": source,
                "detections": detections,
                "to_redact": to_redact,
                "flagged": flagged,
                "preview": preview,
                "redacted": redacted,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_gemini": raw_gemini if debug_mode else None,
            }
            progress.progress((i + 1) / total, text=f"Processed {name}")

    results = st.session_state.get("results")
    if not results:
        st.stop()

    for name, res in results.items():
        if res.get("error"):
            st.error(f"{name}: {res['error']}")
            continue

        source = res["source"]
        to_redact = res["to_redact"]
        flagged = res["flagged"]
        preview = res["preview"]
        found = len(to_redact) + len(flagged)

        with st.expander(f"{name} — {found} found", expanded=True):
            left, right = st.columns(2)
            with left:
                st.subheader("Original")
                st.image(source, use_container_width=True)
            with right:
                if mode == "Redact":
                    st.subheader("Redacted")
                    st.image(res["redacted"], use_container_width=True)
                else:
                    st.subheader("Detection preview")
                    st.image(preview, use_container_width=True)

            if mode == "Redact":
                st.subheader("Detection preview")
                st.image(preview, use_container_width=True)

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Detected", len(res["detections"]))
            col_b.metric("Redacted", len(to_redact))
            col_c.metric("Review", len(flagged))

            if debug_mode and res.get("raw_gemini"):
                with st.expander("Raw Gemini Response"):
                    st.code(res["raw_gemini"], language="json")

            if mode == "QC" and found:
                st.warning(
                    f"{found} missed redaction(s) detected — verify these regions."
                )
            elif mode == "QC":
                st.success("No unredacted sensitive objects detected.")

            with st.expander("Detection JSON"):
                st.json(
                    {
                        "file": name,
                        "screen_id": "IMAGE_001",
                        "detections": [
                            fd.as_dict() for fd in to_redact + flagged
                        ],
                        "analyzed_at": res["timestamp"],
                    }
                )

            if mode == "Redact":
                st.download_button(
                    f"Download redacted ({name})",
                    data=_image_bytes(res["redacted"]),
                    file_name=f"{name}_redacted.png",
                    mime="image/png",
                    use_container_width=True,
                )
            else:
                st.download_button(
                    f"Download boxed preview ({name})",
                    data=_image_bytes(preview),
                    file_name=f"{name}_boxes.png",
                    mime="image/png",
                    use_container_width=True,
                )

    if mode == "Redact":
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, res in results.items():
                if res.get("error"):
                    continue
                zf.writestr(f"{name}_redacted.png", _image_bytes(res["redacted"]))
        st.download_button(
            "Download all (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="redacted_batch.zip",
            mime="application/zip",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()