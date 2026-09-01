# Privacy Redactor (PR)

Visual privacy redaction tool. Upload an image → Gemini detects sensitive regions → app blurs/pixelates/blackouts them.

See [../PRIVACY_REDACTOR.md](../PRIVACY_REDACTOR.md) for the full plan.

## Quick start

```bash
cd VLM/PR
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Add your Gemini API key to `.env`:
```
GEMINI_API_KEY=your_key_here
```

Run the app:
```bash
streamlit run app.py
```

To run without an API key (mock detections), set `USE_MOCK=true` in `.env`.

## Layout
```
PR/
  app.py              # Streamlit UI (Phases 1-3)
  requirements.txt
  .env / .env.example
  redactor/
    config.py         # defaults, redaction map, thresholds
    gemini_client.py  # Gemini Vision → structured JSON
    mock.py           # mock detections for offline / demo
    policy.py         # confidence gating + redaction method selection
    redaction.py      # blur / pixelate / blackout
    drawing.py        # box overlays for preview / debug
  evidence/           # confirmed-incident snapshots (reserved for Phase 4+)
```
