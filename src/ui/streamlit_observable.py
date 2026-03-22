"""
Streamlit observable components — drop-in replacements for the generic
st.status / st.write progress pattern with real-time progress bar,
per-stage timeline, and a live log panel.

Usage in app.py:
    from src.ui.streamlit_observable import render_progress_panel, render_log_panel
    from src.ui.progress_tracker import ProgressTracker

    tracker = ProgressTracker()
    placeholder = st.empty()

    for event_type, state in orchestrator.stream(claim, thread_id):
        with placeholder.container():
            render_progress_panel(tracker)
        ...

    render_log_panel()
"""

import html
import time
from typing import Optional

import streamlit as st

from src.ui.progress_tracker import ProgressTracker, Stage


def render_progress_panel(tracker: ProgressTracker) -> None:
    """
    Render:
      1. A percentage progress bar
      2. A timeline of all completed stages (last 10)
      3. A live elapsed-time counter
    """
    current = tracker.current
    pct = current.progress_pct if current else 0.0
    msg = current.message if current else "Initializing..."
    elapsed = int(tracker.elapsed)

    # Progress bar
    st.progress(pct, text=f"⏳ {msg}  ({elapsed}s elapsed)")

    # Stage timeline
    updates = tracker.updates[-10:]  # show last 10 stages
    if updates:
        lines = []
        for upd in updates:
            stage_elapsed = int(upd.timestamp - tracker.start_time)
            done = upd.stage in (Stage.COMPLETE,)
            icon = upd.icon
            colour = "#22c55e" if done else ("var(--text)" if upd is current else "#666")
            lines.append(
                f"<span style='color:{colour};font-family:monospace;font-size:11px'>"
                f"{icon} +{stage_elapsed}s  {html.escape(upd.message)}"
                f"</span>"
            )
        st.markdown("<br>".join(lines), unsafe_allow_html=True)


def render_log_panel(max_entries: int = 50, expanded: bool = False) -> None:
    """
    Render an expandable real-time log panel from ObservableLogger.
    Safe to call even if ObservableLogger hasn't been imported yet.
    """
    try:
        from src.utils.observable_logger import get_observable_logger
        logger = get_observable_logger()
        logs = logger.get_recent(max_entries)
    except Exception:
        return

    if not logs:
        return

    _LEVEL_ICON = {
        "ERROR":    "🔴",
        "WARNING":  "🟡",
        "INFO":     "🔵",
        "DEBUG":    "⚪",
        "CRITICAL": "🚨",
    }

    with st.expander("🔍 System Logs", expanded=expanded):
        for entry in reversed(logs):
            icon = _LEVEL_ICON.get(entry.get("level", ""), "•")
            component = entry.get("component", "?")
            message = html.escape(str(entry.get("message", "")))
            ts = entry.get("timestamp", "")[-12:]  # HH:MM:SS.mmm
            st.caption(f"{icon} `{ts}` [{component}] {message}")


def render_stage_grid(tracker: ProgressTracker) -> None:
    """
    Render a compact colour-coded stage grid (like the existing render_progress).
    Stages: Searching → ProAgent → ConAgent → FactCheck → Moderator
    """
    stage_groups = [
        ("🔍 Search",     [Stage.SEARCHING]),
        ("💬 ProAgent",   [Stage.ROUND_1_PRO, Stage.ROUND_2_PRO, Stage.ROUND_3_PRO]),
        ("🔴 ConAgent",   [Stage.ROUND_1_CON, Stage.ROUND_2_CON, Stage.ROUND_3_CON]),
        ("✅ FactCheck",  [Stage.FACT_CHECKING]),
        ("⚖️ Moderator",  [Stage.MODERATING]),
    ]

    completed_stages = {u.stage for u in tracker.updates}
    current = tracker.current

    cols = st.columns(len(stage_groups))
    for col, (label, stages) in zip(cols, stage_groups):
        is_done    = all(s in completed_stages for s in stages)
        is_running = current is not None and current.stage in stages

        if is_done:
            col.success(label)
        elif is_running:
            col.warning(label)
        else:
            col.info(label)


def render_resource_monitor() -> None:
    """
    Render a compact resource monitor (Memory, CPU).
    Uses psutil to monitor the current process.
    """
    import psutil
    import os
    from src.resource.manager import get_resource_manager

    proc = psutil.Process(os.getpid())
    rm = get_resource_manager()

    # Memory
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    mem_limit = rm.max_memory_mb
    mem_pct = (mem_mb / mem_limit) if mem_limit > 0 else 0.0

    # CPU (quick sample)
    cpu_pct = proc.cpu_percent(interval=None)

    # UI Rendering
    st.markdown("<p style='font-family:var(--mono);font-size:9px;color:var(--text2);letter-spacing:4px;text-transform:uppercase;margin:18px 0 10px'>Resource Monitor</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    col1.metric("RAM", f"{mem_mb:.0f}MB", f"{mem_pct:.1%} limit")
    col2.metric("CPU", f"{cpu_pct:.1f}%")

    # Progress bar for memory
    st.progress(min(1.0, mem_pct), text=f"Memory Pressure: {mem_mb:.0f} / {mem_limit} MB")
