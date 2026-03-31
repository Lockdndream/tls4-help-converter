"""
TLS-4 Help Converter — Streamlit UI
Run with: streamlit run app.py
"""

import io
import os
import tempfile
import time
import traceback
from pathlib import Path

import streamlit as st

from converter import convert

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TLS-4 Help Converter",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS — industrial/utilitarian aesthetic
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* Page background */
    .stApp {
        background-color: #0f1117;
        color: #e0e0e0;
    }

    /* Header strip */
    .header-strip {
        background: #1a1d27;
        border-bottom: 2px solid #f0a500;
        padding: 18px 28px;
        margin: -1rem -1rem 2rem -1rem;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .header-strip h1 {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.3rem;
        font-weight: 600;
        color: #f0a500;
        margin: 0;
        letter-spacing: 0.05em;
    }
    .header-strip .subtitle {
        font-size: 0.8rem;
        color: #6b7280;
        font-family: 'IBM Plex Mono', monospace;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .badge {
        background: #f0a500;
        color: #0f1117;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.65rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 2px;
        letter-spacing: 0.1em;
    }

    /* Upload zones */
    [data-testid="stFileUploader"] {
        background: #1a1d27;
        border: 1px dashed #2e3347;
        border-radius: 4px;
        padding: 8px;
        transition: border-color 0.2s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #f0a500;
    }

    /* Buttons */
    .stButton > button {
        background: #f0a500;
        color: #0f1117;
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.08em;
        border: none;
        border-radius: 3px;
        padding: 10px 24px;
        text-transform: uppercase;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        background: #ffc233;
        transform: translateY(-1px);
    }
    .stButton > button:disabled {
        background: #2e3347;
        color: #4b5563;
        transform: none;
    }

    /* Log box */
    .log-container {
        background: #0a0c12;
        border: 1px solid #2e3347;
        border-left: 3px solid #f0a500;
        border-radius: 3px;
        padding: 16px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        line-height: 1.7;
        color: #a0aec0;
        max-height: 380px;
        overflow-y: auto;
    }
    .log-step {
        color: #f0a500;
        font-weight: 600;
    }
    .log-ok {
        color: #34d399;
    }
    .log-warn {
        color: #fbbf24;
    }
    .log-err {
        color: #f87171;
    }

    /* Info cards */
    .info-card {
        background: #1a1d27;
        border: 1px solid #2e3347;
        border-radius: 4px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .info-card h4 {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #6b7280;
        margin: 0 0 6px 0;
    }
    .info-card p {
        font-size: 0.88rem;
        color: #d1d5db;
        margin: 0;
        line-height: 1.5;
    }

    /* Status pill */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 500;
    }
    .pill-ready    { background: #064e3b; color: #34d399; border: 1px solid #065f46; }
    .pill-running  { background: #1c1a05; color: #fbbf24; border: 1px solid #78350f; }
    .pill-done     { background: #064e3b; color: #6ee7b7; border: 1px solid #065f46; }
    .pill-error    { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
    .pill-waiting  { background: #1e2030; color: #6b7280; border: 1px solid #2e3347; }

    /* Download button override */
    [data-testid="stDownloadButton"] > button {
        background: #064e3b !important;
        color: #34d399 !important;
        border: 1px solid #065f46 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        width: 100%;
    }
    [data-testid="stDownloadButton"] > button:hover {
        background: #065f46 !important;
    }

    /* Divider */
    hr { border-color: #2e3347; margin: 1.5rem 0; }

    /* Column labels */
    .col-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #6b7280;
        margin-bottom: 8px;
    }

    /* Hide Streamlit default elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="header-strip">
        <div>
            <div class="subtitle">Gilbarco TLS-450 &nbsp;·&nbsp; Veeder-Root</div>
            <h1>🔧 TLS-4 Help Converter</h1>
        </div>
        <div style="margin-left:auto; text-align:right;">
            <div class="badge">RH 2022 → RH 2019</div>
            <div class="subtitle" style="margin-top:4px;">WebHelp Frame Format</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Layout: two columns
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1, 1.6], gap="large")

# ---------------------------------------------------------------------------
# LEFT — Inputs
# ---------------------------------------------------------------------------
with left_col:

    st.markdown('<div class="col-label">Input Packages</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="info-card">
          <h4>How it works</h4>
          <p>Upload both help packages. The 2022 package provides updated topic content.
          The 2019 package provides the frame-based WebHelp navigation engine that
          the TLS-450 embedded browser can render correctly.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**① New content** — RoboHelp 2022 output zip")
    new_zip = st.file_uploader(
        "2022 package",
        type=["zip"],
        key="new_zip",
        label_visibility="collapsed",
    )

    st.markdown("**② Framework** — RoboHelp 2019 output zip")
    old_zip = st.file_uploader(
        "2019 package",
        type=["zip"],
        key="old_zip",
        label_visibility="collapsed",
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # Status indicators
    def _pill(label: str, cls: str, dot: str) -> str:
        return (
            f'<span class="status-pill {cls}">'
            f'<span>{dot}</span>{label}</span>'
        )

    new_ok = new_zip is not None
    old_ok = old_zip is not None
    both_ok = new_ok and old_ok

    st.markdown(
        f"""
        <div style="display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap;">
            {_pill("2022 package " + ("loaded" if new_ok else "missing"),
                   "pill-ready" if new_ok else "pill-waiting",
                   "●" if new_ok else "○")}
            {_pill("2019 package " + ("loaded" if old_ok else "missing"),
                   "pill-ready" if old_ok else "pill-waiting",
                   "●" if old_ok else "○")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    run_btn = st.button(
        "▶  Run Conversion",
        disabled=not both_ok,
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []
if "output_bytes" not in st.session_state:
    st.session_state.output_bytes = None
if "conversion_state" not in st.session_state:
    st.session_state.conversion_state = "idle"  # idle | running | done | error
if "error_detail" not in st.session_state:
    st.session_state.error_detail = ""

# ---------------------------------------------------------------------------
# RIGHT — Output / Log
# ---------------------------------------------------------------------------
with right_col:

    st.markdown('<div class="col-label">Conversion Log</div>', unsafe_allow_html=True)

    # Status pill
    state = st.session_state.conversion_state
    state_pill = {
        "idle":    _pill("Awaiting input", "pill-waiting", "○"),
        "running": _pill("Running…",        "pill-running", "◉"),
        "done":    _pill("Complete",        "pill-done",    "●"),
        "error":   _pill("Failed",          "pill-error",   "✕"),
    }.get(state, "")

    st.markdown(state_pill, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    log_placeholder = st.empty()
    download_placeholder = st.empty()
    error_placeholder = st.empty()

    def _render_log(lines: list[str]) -> None:
        def _style_line(line: str) -> str:
            if line.startswith("──"):
                return f'<span class="log-step">{line}</span>'
            if "complete ✓" in line.lower() or "copied" in line.lower():
                return f'<span class="log-ok">{line}</span>'
            if "WARNING" in line or "WARN" in line:
                return f'<span class="log-warn">{line}</span>'
            if "ERROR" in line or "error" in line.lower():
                return f'<span class="log-err">{line}</span>'
            return line

        html_lines = "<br>".join(_style_line(l) for l in lines) if lines else "<span style='color:#4b5563'>No output yet…</span>"
        log_placeholder.markdown(
            f'<div class="log-container">{html_lines}</div>',
            unsafe_allow_html=True,
        )

    _render_log(st.session_state.log_lines)

# ---------------------------------------------------------------------------
# Run conversion
# ---------------------------------------------------------------------------
if run_btn and both_ok:
    st.session_state.log_lines = []
    st.session_state.output_bytes = None
    st.session_state.conversion_state = "running"
    st.session_state.error_detail = ""

    with right_col:
        st.markdown(
            _pill("Running…", "pill-running", "◉"),
            unsafe_allow_html=True,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        new_path = tmp / "new.zip"
        old_path = tmp / "old.zip"
        out_path = tmp / "help_converted.zip"

        new_path.write_bytes(new_zip.getvalue())
        old_path.write_bytes(old_zip.getvalue())

        log_lines = st.session_state.log_lines

        def _append_log(msg: str) -> None:
            log_lines.append(msg)
            _render_log(log_lines)

        try:
            convert(
                new_zip_path=str(new_path),
                old_zip_path=str(old_path),
                output_zip_path=str(out_path),
                log_callback=_append_log,
            )
            output_bytes = out_path.read_bytes()
            st.session_state.output_bytes = output_bytes
            st.session_state.conversion_state = "done"

        except Exception:
            tb = traceback.format_exc()
            _append_log("ERROR: Conversion failed — see details below")
            st.session_state.conversion_state = "error"
            st.session_state.error_detail = tb

    st.rerun()

# ---------------------------------------------------------------------------
# Post-run rendering (after rerun)
# ---------------------------------------------------------------------------
_render_log(st.session_state.log_lines)

if st.session_state.conversion_state == "done" and st.session_state.output_bytes:
    with download_placeholder:
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="⬇  Download  help_converted.zip",
            data=st.session_state.output_bytes,
            file_name="help_converted.zip",
            mime="application/zip",
            use_container_width=True,
        )

if st.session_state.conversion_state == "error" and st.session_state.error_detail:
    with error_placeholder:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔴 Error detail — share this when reporting a bug"):
            st.code(st.session_state.error_detail, language="python")

# ---------------------------------------------------------------------------
# Sidebar — reference info
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Conversion reference")
    st.markdown(
        """
**What this tool does**

Takes a RoboHelp 2022 *Frameless/HTML5* output and wraps it in a RoboHelp 2019
*WebHelp* frame-based shell, so it renders on the Gilbarco TLS-450 embedded browser.

---

**Transformations applied per topic file**

| Step | Change |
|------|--------|
| 1 | Remove `<?xml?>` declaration |
| 2 | Fix DOCTYPE to `<!DOCTYPE HTML>` |
| 3 | Remove `_rhdefault.css` link |
| 4 | Rewrite CSS path → `tls4_gui.css` |
| 5 | Flatten `assets/images/` path |
| 6 | Lowercase all `.htm` `href` values |

---

**Known limitations**

- Topics *new* in 2022 (not in 2019 TOC) won't appear in the nav tree — they load via direct URL or breadcrumb links only.
- The 2019 search index covers 2019 topics only.
- To fully update the nav tree/TOC, regenerate the `whxdata/` files using RoboHelp 2019 with the updated project.

---

**Reporting a bug**

1. Note which step failed in the log
2. Copy the error detail from the expander
3. Bring both to Claude with the relevant source files
        """
    )
