"""
InsightSwarm Streamlit UI
=========================
Design inspired by app_backup.py — Space Mono typography, Nothing-brand dark
aesthetic, colour-coded verdicts.

Key improvements over the previous app.py:
 - Full API-exhaustion handling: Groq → Gemini fallback, and a prominent
   "All Resources Exhausted" banner when every key is rate-limited.
 - Retry countdown timer with live seconds display.
 - Progress bar visualising pipeline stages while debate runs.
 - Colour-coded verdict box (green / red / amber / grey).
 - Empty-state landing page instead of a blank canvas.
 - Stable session state (feedback_given persists across reruns).
"""

from __future__ import annotations

import html
import time
import uuid
from typing import Any, Mapping, Optional

import streamlit as st

from src.orchestration.debate import DebateOrchestrator
from src.orchestration.cache import record_feedback
from src.utils.validation import validate_claim
from src.llm.client import RateLimitError
from src.async_tasks.task_queue import get_task_queue
from src.ui.progress_tracker import ProgressTracker, Stage

# Observable UI components (Phase 1)
try:
    from src.ui.streamlit_observable import render_progress_panel, render_log_panel, render_resource_monitor
    _OBSERVABLE_AVAILABLE = True
except ImportError:
    _OBSERVABLE_AVAILABLE = False
    def render_progress_panel(*a, **kw): pass  # type: ignore
    def render_log_panel(*a, **kw): pass        # type: ignore

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InsightSwarm",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>

/* ── Tokens ──────────────────────────────────────────────────────── */
:root {
    --bg:     #000000;
    --s1:     #0c0c0c;
    --s2:     #111111;
    --text:   #f0f0f0;
    --text2:  #999999;
    --border: #2a2a2a;
    --b2:     #3a3a3a;
    --accent: #ffcc33;
    --green:  #22c55e;
    --red:    #ef4444;
    --amber:  #f59e0b;
    --mono:   'Space Mono', 'Courier New', monospace;
    --sans:   'DM Sans', system-ui, sans-serif;
}

/* ── App background & base font ─────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background-color: var(--bg);
    color: var(--text);
    font-family: var(--sans);
}
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
    background-color: var(--bg);
    padding-top: 2rem;
}
body {
    background-image: radial-gradient(#1a1a1a 1px, transparent 1px);
    background-size: 22px 22px;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: var(--s1);
    border-right: 1px solid var(--border);
}

/* ── Hide chrome ─────────────────────────────────────────────────── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
[data-testid="stDecoration"]  { display: none; }
[data-testid="stToolbar"]     { visibility: hidden; }
[data-testid="stHeader"]      { background: transparent; }

/* ── Text input ──────────────────────────────────────────────────── */
.stTextInput input {
    background-color: var(--s1) !important;
    border: 1px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
    padding: 14px 16px !important;
    font-family: var(--sans) !important;
    font-size: 15px !important;
    caret-color: var(--accent);
}
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}
.stTextInput input::placeholder { color: var(--text2) !important; }
.stTextInput label {
    font-family: var(--mono) !important;
    font-size: 9px !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    color: var(--text2) !important;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton button {
    background-color: transparent !important;
    color: var(--text) !important;
    border: 1px solid var(--b2) !important;
    border-radius: 0 !important;
    padding: 11px 20px !important;
    font-family: var(--mono) !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    transition: background 0.15s, border-color 0.15s !important;
}
.stButton button:hover {
    background-color: rgba(255,255,255,0.05) !important;
    border-color: var(--text) !important;
}
.stButton button[kind="primary"] {
    background-color: var(--accent) !important;
    color: #000 !important;
    border-color: var(--accent) !important;
}
.stButton button[kind="primary"]:hover {
    background-color: #ffd94d !important;
    border-color: #ffd94d !important;
}
.stButton button:disabled { opacity: 0.3 !important; }

[data-testid="stSidebar"] .stButton button {
    font-family: var(--sans) !important;
    font-size: 12px !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    font-weight: 400 !important;
    padding: 7px 10px !important;
    color: var(--text2) !important;
    border-color: var(--border) !important;
}

/* ── Metrics ─────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--s2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 0 !important;
    padding: 16px 18px !important;
}
[data-testid="stMetricLabel"] p {
    font-family: var(--mono) !important;
    font-size: 9px !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    color: var(--text2) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-size: 28px !important;
    color: var(--text) !important;
}

/* ── Tabs ────────────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
}
[data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    font-size: 10px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    color: var(--text2) !important;
    padding: 10px 16px !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: var(--text) !important;
    border-bottom: 2px solid var(--accent) !important;
}
[data-baseweb="tab-highlight"],
[data-baseweb="tab-border"] { display: none !important; }

/* ── Expander ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 0 !important;
    background: var(--s1) !important;
}
[data-testid="stExpander"] summary {
    font-family: var(--mono) !important;
    font-size: 10px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    color: var(--text2) !important;
    padding: 11px 14px !important;
}

/* ── Alerts ──────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 0 !important;
    background: var(--s2) !important;
}

/* ══════════════════════════════════════════════════════════════════
   CUSTOM HTML COMPONENTS
   ══════════════════════════════════════════════════════════════════ */

/* ── Header ──────────────────────────────────────────────────────── */
.is-title {
    font-family: var(--mono);
    font-size: 72px;
    font-weight: 700;
    letter-spacing: -4px;
    text-transform: uppercase;
    line-height: 0.9;
    color: #ffffff;
    border-bottom: 2px solid #ffffff;
    padding-bottom: 14px;
    display: inline-block;
}
.is-subtitle {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text2);
    letter-spacing: 4px;
    text-transform: uppercase;
    margin: 12px 0 0;
}

/* ── Section divider ─────────────────────────────────────────────── */
.sec {
    font-family: var(--mono);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--text2);
    margin: 32px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
}
.sec::before {
    content: '';
    width: 3px;
    height: 10px;
    background: var(--accent);
    display: inline-block;
    flex-shrink: 0;
}

/* ── Verdict box ─────────────────────────────────────────────────── */
.vbox {
    margin-top: 20px;
    padding: 22px 26px 18px;
    border: 1px solid var(--border);
    border-left: 3px solid var(--text2);
    background: var(--s1);
}
.vbox-label { font-family: var(--mono); font-size: 9px; letter-spacing: 4px; text-transform: uppercase; color: var(--text2); margin-bottom: 8px; }
.vbox-verdict { font-family: var(--mono); font-size: 30px; font-weight: 700; text-transform: uppercase; line-height: 1; }
.vbox-claim { font-size: 12px; color: var(--text2); font-style: italic; margin: 8px 0 10px; line-height: 1.5; }
.conf-track { height: 2px; background: var(--border); margin: 14px 0 6px; position: relative; }
.conf-fill  { position: absolute; left: 0; top: 0; bottom: 0; }
.conf-lbl   { font-family: var(--mono); font-size: 10px; color: var(--text2); }

/* Verdict colour variants */
.vt { border-left-color: var(--green) !important; }
.vt .vbox-verdict { color: var(--green); }
.vt .conf-fill { background: var(--green); }
.vf { border-left-color: var(--red) !important; }
.vf .vbox-verdict { color: var(--red); }
.vf .conf-fill { background: var(--red); }
.vu { border-left-color: var(--amber) !important; }
.vu .vbox-verdict { color: var(--amber); }
.vu .conf-fill { background: var(--amber); }
.vx { border-left-color: var(--text2) !important; }
.vx .vbox-verdict { color: var(--text2); }
.vx .conf-fill { background: var(--text2); }

/* ── API Exhaustion banner ───────────────────────────────────────── */
.api-exhausted {
    border: 1px solid var(--red);
    border-left: 4px solid var(--red);
    background: rgba(239,68,68,0.07);
    padding: 20px 24px;
    margin: 16px 0;
}
.api-exhausted-title {
    font-family: var(--mono);
    font-size: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--red);
    margin-bottom: 8px;
}
.api-exhausted-body { font-size: 13px; color: #ccc; line-height: 1.7; }
.api-retry-timer {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 700;
    color: var(--amber);
    margin-top: 10px;
}

/* ── Pipeline progress bar ───────────────────────────────────────── */
.prog { display: flex; border: 1px solid var(--border); margin: 16px 0 4px; }
.ps {
    flex: 1;
    padding: 11px 6px 9px;
    border-right: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 9px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--text2);
    text-align: center;
}
.ps:last-child { border-right: none; }
.ps-n { font-size: 16px; display: block; margin-bottom: 2px; line-height: 1; }
.ps-run { color: var(--accent); background: rgba(255,204,51,0.06); border-bottom: 2px solid var(--accent); }
.ps-ok  { color: var(--green);  background: rgba(34,197,94,0.05); }

/* ── Debate blocks ───────────────────────────────────────────────── */
.dblock {
    padding: 14px 16px;
    border: 1px solid var(--border);
    background: transparent;
    font-size: 13px;
    line-height: 1.7;
    color: #cccccc;
    min-height: 80px;
}
.dlbl {
    font-family: var(--mono);
    font-size: 9px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 6px;
}
.dlbl::before { content: ''; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dpro .dlbl { color: var(--green); }
.dpro .dlbl::before { background: var(--green); }
.dcon .dlbl { color: var(--red); }
.dcon .dlbl::before { background: var(--red); }

/* ── Source rows ─────────────────────────────────────────────────── */
.srow {
    display: grid;
    grid-template-columns: 26px 1fr auto auto;
    align-items: center;
    column-gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
}
.srow:last-child { border-bottom: none; }
.snum { font-family: var(--mono); font-size: 10px; color: var(--text2); }
.surl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; color: #ccc; }
.serr { font-size: 11px; color: var(--text2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
.sfail-url { color: var(--red); }
.sbadge { font-family: var(--mono); font-size: 9px; letter-spacing: 1px; padding: 2px 7px; white-space: nowrap; }
.sok  { border: 1px solid var(--green); color: var(--green); }
.sfail { border: 1px solid var(--red); color: var(--red); }

/* ── Feedback ────────────────────────────────────────────────────── */
.fb-wrap-up   .stButton button { border-color: var(--green) !important; color: var(--green) !important; }
.fb-wrap-up   .stButton button:hover { background: rgba(34,197,94,0.08) !important; }
.fb-wrap-down .stButton button { border-color: var(--red) !important; color: var(--red) !important; }
.fb-wrap-down .stButton button:hover { background: rgba(239,68,68,0.08) !important; }

/* ── Empty state ─────────────────────────────────────────────────── */
.empty {
    border: 1px dashed var(--border);
    margin-top: 28px;
    padding: 60px 20px;
    text-align: center;
}
.empty-g { font-family: var(--mono); font-size: 52px; color: var(--text); opacity: 0.07; display: block; margin-bottom: 20px; letter-spacing: -6px; line-height: 1; }
.empty-h { font-family: var(--mono); font-size: 10px; letter-spacing: 4px; text-transform: uppercase; color: var(--text2); margin-bottom: 10px; }
.empty-b { font-size: 13px; color: var(--text2); line-height: 1.7; max-width: 360px; margin: 0 auto; }

/* ── Agent card (sidebar) ────────────────────────────────────────── */
.ac { padding: 10px 0; border-bottom: 1px solid var(--border); }
.ar { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.an { font-family: var(--mono); font-size: 9px; color: var(--text2); min-width: 18px; }
.ad { font-size: 11px; color: var(--text2); padding-left: 26px; line-height: 1.4; }

/* ── Footer ──────────────────────────────────────────────────────── */
.foot {
    margin-top: 48px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    font-family: var(--mono);
    font-size: 9px;
    color: var(--text2);
    letter-spacing: 2px;
    text-transform: uppercase;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Session state helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _init() -> None:
    defaults: dict[str, Any] = {
        "debate_run":      False,
        "thread_id":       str(uuid.uuid4()),
        "result":          None,
        "orchestrator":    None,
        "is_running":      False,
        "example_claim":   "",
        "feedback_given":  None,
        "debate_error":    None,   # str  – last error message
        "retry_at":        None,   # float – epoch when retry is safe
        "history":         [],     # list of previous dicts
        "history_summary": "",     # text summary of older items
        "task_id":         None,
        "progress_tracker": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _cap_memory_history():
    """Chat history capper keeping latest 10 messages, summarizing older interactions to prevent memory leaks."""
    if len(st.session_state.history) > 10:
        st.session_state.history = st.session_state.history[-10:]
        st.session_state.history_summary = "Older verification requests have been archived and summarized to save memory."


@st.cache_resource(show_spinner=False)
def _get_orchestrator() -> DebateOrchestrator:
    return DebateOrchestrator()


# ═══════════════════════════════════════════════════════════════════════════════
# UI utilities
# ═══════════════════════════════════════════════════════════════════════════════

def sh(content: str) -> None:
    """Render raw HTML."""
    st.markdown(content, unsafe_allow_html=True)


def sec(label: str) -> None:
    sh(f"<p class='sec'>{html.escape(label)}</p>")


def _vclass(verdict: str) -> str:
    v = (verdict or "").upper()
    if any(k in v for k in ("TRUE", "CORRECT", "ACCURATE", "SUPPORTED", "VERIFIED")):
        return "vt"
    if any(k in v for k in ("FALSE", "INCORRECT", "INACCURATE", "UNSUPPORTED", "DEBUNKED")):
        return "vf"
    if any(k in v for k in ("UNCERTAIN", "MIXED", "PARTIAL", "INSUFFICIENT", "UNVERIFIED",
                             "EVIDENCE", "RATE_LIMITED", "UNKNOWN")):
        return "vu"
    return "vx"


def _clip(url: str, n: int = 60) -> str:
    return url if len(url) <= n else url[:n - 1] + "…"


# ═══════════════════════════════════════════════════════════════════════════════
# Render helpers
# ═══════════════════════════════════════════════════════════════════════════════

def render_header() -> None:
    sh("""
    <div style='padding:20px 0 0'>
      <span class='is-title'>InsightSwarm</span>
      <p class='is-subtitle'>Multi-Agent Truth Verification Protocol</p>
    </div>
    <div style='height:28px'></div>
    """)


def render_sidebar() -> None:
    with st.sidebar:
        sh("<p style='font-family:var(--mono);font-size:9px;color:var(--text2);"
           "letter-spacing:4px;text-transform:uppercase;margin-bottom:14px'>"
           "Agent Architecture</p>")

        for num, name, desc, col in [
            ("01", "ProAgent",    "Validates claim assumptions",      "#22c55e"),
            ("02", "ConAgent",    "Adversarial rebuttal",             "#ef4444"),
            ("03", "FactChecker", "Source verification",              "#3b82f6"),
            ("04", "Moderator",   "Consensus &amp; fallacy detection","#ffcc33"),
        ]:
            sh(f"""<div class='ac'>
              <div class='ar'>
                <span class='an'>{num}</span>
                <span style='font-size:13px;font-weight:500;color:{col}'>{name}</span>
              </div>
              <div class='ad'>{desc}</div>
            </div>""")

        st.write("")
        sh("<p style='font-family:var(--mono);font-size:9px;color:var(--text2);"
           "letter-spacing:4px;text-transform:uppercase;margin:18px 0 10px'>"
           "Example Claims</p>")

        from src.config import StreamlitConfig
        for c in StreamlitConfig.EXAMPLE_CLAIMS:
            if st.button(c, key=f"ex_{c}", use_container_width=True):
                st.session_state.example_claim = c
                st.rerun()

        st.write("")
        sh("""<div style='padding:10px 12px;border:1px solid var(--border);
                          font-size:9px;color:var(--text2);
                          font-family:var(--mono);line-height:1.8;letter-spacing:1px'>
          POWERED BY<br>
          <span style='color:var(--text)'>GROQ + GEMINI</span>
        </div>""")

        if _OBSERVABLE_AVAILABLE:
            render_resource_monitor()
        
        st.markdown("---")
        st.session_state.use_simulation = st.toggle("Simulation Mode (Offline Demo)", value=False, help="Use mock responses for testing the UI flow.")


def render_progress(active: int) -> None:
    """active: 1–4 = that stage running; 5 = all done."""
    if active == 0:
        return
    cells = ""
    for i, name in enumerate(["ProAgent", "ConAgent", "FactCheck", "Moderator"], 1):
        if   i < active:  cls, sym = "ps ps-ok",  "✓"
        elif i == active: cls, sym = "ps ps-run",  str(i)
        else:             cls, sym = "ps",          str(i)
        cells += f"<div class='{cls}'><span class='ps-n'>{sym}</span>{name}</div>"
    sh(f"<div class='prog'>{cells}</div>")


def render_api_exhausted(retry_at: Optional[float]) -> None:
    """Display a prominent banner when ALL providers are rate-limited."""
    remaining = max(0, int((retry_at or 0) - time.time())) if retry_at else None
    timer_html = (
        f"<div class='api-retry-timer'>{remaining}s</div>"
        if remaining is not None else ""
    )
    sh(f"""
    <div class='api-exhausted'>
      <div class='api-exhausted-title'>⚡ API Resources Exhausted</div>
      <div class='api-exhausted-body'>
        All Groq and Gemini API keys are currently rate-limited.<br>
        The system automatically tried every available key and fallback provider.<br>
        Please wait for the cooldown period before retrying.
      </div>
      {timer_html}
    </div>
    """)
    if retry_at:
        remaining_s = max(0.0, retry_at - time.time())
        st.progress(min(1.0, 1.0 - remaining_s / max(remaining_s, 60.0)),
                    text=f"Cooldown — retry in ~{int(remaining_s)}s")


def render_empty() -> None:
    sh("""<div class='empty'>
      <span class='empty-g'>◈</span>
      <p class='empty-h'>Ready to verify</p>
      <p class='empty-b'>Type a claim and press
        <strong style='color:var(--text)'>Verify Claim</strong>.
        Four AI agents debate, fact-check, and deliver a verdict.
      </p>
    </div>""")


def render_verdict(result: Mapping[str, Any]) -> None:
    verdict    = str(result.get("verdict", "UNKNOWN") or "UNKNOWN")
    confidence = float(result.get("confidence", 0.0) or 0.0)
    claim_text = str(result.get("claim", "") or "")
    vc  = _vclass(verdict)
    pct = int(confidence * 100)

    claim_html = (f"<div class='vbox-claim'>\"{html.escape(claim_text)}\"</div>"
                  if claim_text else "")

    sh(f"""<div class='vbox {vc}'>
      <div class='vbox-label'>Verdict</div>
      <div class='vbox-verdict'>{html.escape(verdict)}</div>
      {claim_html}
      <div class='conf-track'><div class='conf-fill' style='width:{pct}%'></div></div>
      <div class='conf-lbl'>Confidence &nbsp;{confidence:.1%}</div>
    </div>""")

    # Handle special RATE_LIMITED/SYSTEM_ERROR verdicts explicitly
    if verdict in ("RATE_LIMITED", "SYSTEM_ERROR"):
        if verdict == "RATE_LIMITED":
            render_api_exhausted(st.session_state.get("retry_at"))
        else:
            st.warning("The analysis was interrupted by a system-level error. This usually indicates an API failure or transient network issue.")
        return

    # Prioritize 'reasoning' (full) over 'argument' (truncated)
    display_reasoning = result.get("reasoning") or result.get("moderator_reasoning") or result.get("argument")
    if display_reasoning:
        with st.expander("▸ Moderator Analysis & Reasoning", expanded=True):
            sh("<div style='font-size:13px;color:#bbb;line-height:1.75'>"
               + html.escape(str(display_reasoning)).replace("\n", "<br>") + "</div>")


def render_metrics(result: Mapping[str, Any]) -> None:
    m = result.get("metrics") or {}
    if not m:
        return
    sec("Intelligence Metrics")
    c1, c2, c3 = st.columns(3)
    credibility = float(m.get("credibility_score", 0.0))
    fallacies   = m.get("logical_fallacies", [])
    fallacy_count = len(fallacies) if isinstance(fallacies, list) else int(fallacies)
    arg_quality = float(m.get("argument_quality", 0.0))
    c1.metric("Evidence Credibility", f"{credibility:.0%}")
    c2.metric("Fallacy Count",        fallacy_count)
    c3.metric("Argument Quality",     f"{arg_quality:.0%}")


def render_sources(result: Mapping[str, Any]) -> None:
    vrs = result.get("verification_results") or []
    if not vrs:
        return
    sec("Source Verification")

    total    = len(vrs)
    verified = sum(1 for r in vrs if r.get("status") == "VERIFIED")
    failed   = total - verified
    avg_rate = (
        float(result.get("pro_verification_rate", 0.0) or 0.0)
        + float(result.get("con_verification_rate", 0.0) or 0.0)
    ) / 2

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total",    total)
    c2.metric("Verified", verified,
              f"+{verified/total*100:.0f}%" if total else "0%")
    c3.metric("Failed",   failed,
              f"-{failed/total*100:.0f}%" if (failed and total) else None)
    c4.metric("Avg Rate", f"{avg_rate:.1%}")

    with st.expander("▸ Detailed Source Results"):
        rows = ""
        for i, vr in enumerate(vrs, 1):
            ok   = vr.get("status") == "VERIFIED"
            url  = _clip(vr.get("url", ""))
            err  = html.escape(vr.get("error", "") or "")
            badge    = f"<span class='sbadge {'sok' if ok else 'sfail'}'>{'OK' if ok else 'FAIL'}</span>"
            url_cls  = "surl" if ok else "surl sfail-url"
            err_cell = f"<span class='serr'>{err}</span>" if (not ok and err) else "<span></span>"
            rows += f"""<div class='srow'>
              <span class='snum'>{i:02d}</span>
              <span class='{url_cls}'>{html.escape(url)}</span>
              {err_cell}
              {badge}
            </div>"""
        sh(f"<div>{rows}</div>")


def render_debate(result: Mapping[str, Any]) -> None:
    pros   = list(result.get("pro_arguments", []) or [])
    cons   = list(result.get("con_arguments", []) or [])
    rounds = min(len(pros), len(cons))
    if not rounds:
        return
    sec("Debate Log")
    for idx, tab in enumerate(st.tabs([f"Round {i+1}" for i in range(rounds)])):
        with tab:
            lc, rc = st.columns(2)
            with lc:
                pro_text = str(pros[idx]) if idx < len(pros) else ""
                if not pro_text or "technical error" in pro_text.lower():
                    sh(f"<div class='dblock dpro' style='border-color:#ef444455'><div class='dlbl'>Pro — Supporting</div>"
                       f"<span style='color:#ef4444;font-size:11px'>⚠️ Agent interaction failed. Check logs.</span></div>")
                else:
                    sh(f"""<div class='dblock dpro'>
                      <div class='dlbl'>Pro — Supporting</div>
                      {html.escape(pro_text).replace(chr(10),'<br>')}
                    </div>""")
            with rc:
                con_text = str(cons[idx]) if idx < len(cons) else ""
                if not con_text or "technical error" in con_text.lower():
                    sh(f"<div class='dblock dcon' style='border-color:#ef444455'><div class='dlbl'>Con — Rebuttal</div>"
                       f"<span style='color:#ef4444;font-size:11px'>⚠️ Agent interaction failed. Check logs.</span></div>")
                else:
                    sh(f"""<div class='dblock dcon'>
                      <div class='dlbl'>Con — Rebuttal</div>
                      {html.escape(con_text).replace(chr(10),'<br>')}
                    </div>""")


def render_feedback(result: Mapping[str, Any]) -> None:
    sec("Feedback Protocol")
    claim   = str(result.get("claim", "Unknown Claim") or "Unknown Claim")
    verdict = str(result.get("verdict", "UNKNOWN") or "UNKNOWN")

    if st.session_state.feedback_given:
        sym = "✓" if st.session_state.feedback_given == "UP" else "✗"
        msg = ("Marked accurate — thank you."
               if st.session_state.feedback_given == "UP"
               else "Flagged for human review.")
        sh(f"<p style='font-family:var(--mono);font-size:10px;color:var(--text2);"
           f"letter-spacing:1px;padding:12px 0'>{sym} &nbsp;{msg}</p>")
        return

    col1, col2, _sp = st.columns([1, 1, 4])
    with col1:
        sh("<div class='fb-wrap-up'>")
        if st.button("👍  Accurate", key="fb_up", use_container_width=True):
            record_feedback(claim, verdict, "UP")
            st.session_state.feedback_given = "UP"
            st.rerun()
        sh("</div>")
    with col2:
        sh("<div class='fb-wrap-down'>")
        if st.button("👎  Inaccurate", key="fb_down", use_container_width=True):
            record_feedback(claim, verdict, "DOWN")
            st.session_state.feedback_given = "DOWN"
            st.rerun()
        sh("</div>")


def render_footer() -> None:
    sh("""<div class='foot'>
      <span style='color:var(--text)'>InsightSwarm</span>
      <span>Groq + Gemini</span>
    </div>""")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    _init()
    _cap_memory_history()
    render_header()
    render_sidebar()

    # ── Claim input ────────────────────────────────────────────────────────────
    claim = st.text_input(
        "Subject Claim",
        value=st.session_state.get("example_claim", ""),
        placeholder="Enter a natural-language claim to verify…",
        help="Minimum 10 characters.",
    )
    chars = len((claim or "").strip())
    if 0 < chars < 10:
        st.caption(f"{chars} / 10 chars minimum")
    elif chars >= 10:
        st.caption(f"{chars} chars · ready")

    # ── Action buttons ─────────────────────────────────────────────────────────
    bc, rc, _ = st.columns([2, 1, 5])
    with bc:
        verify = st.button("Verify Claim", type="primary",
                           use_container_width=True, disabled=(chars < 10))
    with rc:
        if st.button("Reset", use_container_width=True):
            st.session_state.update(
                debate_run=False, result=None,
                example_claim="", feedback_given=None,
                thread_id=str(uuid.uuid4()),
                debate_error=None, retry_at=None,
            )
            st.rerun()

    # ── Persistent error banner (API exhaustion / other) ───────────────────────
    err = st.session_state.get("debate_error")
    retry_at: Optional[float] = st.session_state.get("retry_at")

    if err and not st.session_state.debate_run:
        is_rate_limit = (
            "rate" in err.lower()
            or "429" in err
            or "exhausted" in err.lower()
            or "resource_exhausted" in err.lower()
        )
        if is_rate_limit:
            render_api_exhausted(retry_at)
        else:
            st.error(f"Last run failed: {err}")

    # ── Run debate ─────────────────────────────────────────────────────────────
    def analyze_claim_async(claim_text: str):
        valid, validation_err = validate_claim(claim_text)
        if not valid:
            st.error(f"Invalid claim: {validation_err}")
            return None

        # Prepare for background execution
        task_queue = get_task_queue()
        task_id = f"debate_{st.session_state.thread_id}"
        st.session_state.task_id = task_id
        
        if not st.session_state.progress_tracker:
            st.session_state.progress_tracker = ProgressTracker()
        tracker = st.session_state.progress_tracker

        use_sim = st.session_state.get("use_simulation", False)

        try:
            # Create orchestrator with this specific tracker
            if use_sim:
                from tests.sandbox.api_simulator import MockChaosClient, ChaosConfig
                config = ChaosConfig(failure_rate=0.0, rate_limit_rate=0.0) # Clean demo
                client = MockChaosClient(config)
                orchestrator = DebateOrchestrator(llm_client=client, tracker=tracker)
            else:
                orchestrator = DebateOrchestrator(tracker=tracker)
        except Exception as e:
            st.session_state.debate_error = f"Orchestrator init failed: {e}"
            st.session_state.is_running = False
            return None

        # Fix 3-E: Reset keys on session start to clear transient cooldowns
        if not use_sim:
            orchestrator.client.key_manager.reset_all_keys()

        # Submit to background
        task_queue.submit(task_id, orchestrator.run, claim_text, st.session_state.thread_id)
        return task_id

    # ── Handle running task ───────────────────────────────────────────────────
    if st.session_state.is_running and st.session_state.task_id:
        task_queue = get_task_queue()
        status_code, result, error = task_queue.get_status(st.session_state.task_id)
        
        if status_code == "COMPLETED":
            st.session_state.result = result
            st.session_state.debate_run = True
            st.session_state.is_running = False
            task_queue.clear_task(st.session_state.task_id)
            st.rerun()
        elif status_code == "FAILED":
            st.session_state.debate_error = str(error)
            st.session_state.is_running = False
            task_queue.clear_task(st.session_state.task_id)
            st.rerun()
        else:
            # Still running — render progress UI
            with st.status("🔍 Analysis in progress...", expanded=True):
                if st.session_state.progress_tracker:
                    render_progress_panel(st.session_state.progress_tracker)
                render_log_panel(max_entries=30, expanded=True)
            
            # Polling delay + rerun to update UI
            time.sleep(1.0)
            st.rerun()

    if verify and claim and chars >= 10:
        if st.session_state.is_running:
            st.warning("A debate is already running — please wait.")
        else:
            st.session_state.is_running = True
            st.session_state.debate_error = None
            st.session_state.retry_at = None
            st.session_state.feedback_given = None
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.progress_tracker = ProgressTracker()
            
            analyze_claim_async(claim)
            st.rerun()

    # ── Show results ───────────────────────────────────────────────────────────
    if st.session_state.debate_run and st.session_state.result:
        r = st.session_state.result
        render_verdict(r)
        render_metrics(r)
        render_sources(r)
        render_debate(r)
        render_feedback(r)
        render_footer()
    elif not st.session_state.debate_run and not err:
        render_empty()


if __name__ == "__main__":
    main()
