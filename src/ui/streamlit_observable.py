"""
src/ui/streamlit_observable.py
B3-P1 / B3-P4 / B3-P5 fix:
  - render_progress_panel now uses the correct ProgressTracker API
    (.current, .updates, .elapsed, .start_time)
  - render_resource_monitor guarded with try/except for missing psutil
  - render_stage_grid uses Stage values that now exist in the enum
"""
import html
import time
from typing import Optional

import streamlit as st

from src.ui.progress_tracker import ProgressTracker, Stage


def render_progress_panel(tracker: ProgressTracker) -> None:
    """
    Render a percentage progress bar + stage timeline + elapsed counter.
    Safe to call even if tracker has no updates yet.
    """
    current = tracker.current
    pct     = current.progress_pct if current else 0.0
    msg     = current.message      if current else "Initialising..."
    elapsed = int(tracker.elapsed)

    st.progress(min(1.0, pct), text=f"⏳ {msg}  ({elapsed}s elapsed)")

    updates = tracker.updates[-10:]
    if updates:
        lines = []
        for upd in updates:
            stage_elapsed = int(upd.timestamp - tracker.start_time)
            done   = upd.stage == Stage.COMPLETE
            colour = "#22c55e" if done else ("var(--text)" if upd is current else "#666")
            lines.append(
                f"<span style='color:{colour};font-family:monospace;font-size:11px'>"
                f"{upd.icon} +{stage_elapsed}s &nbsp; {html.escape(upd.message)}"
                f"</span>"
            )
        st.markdown("<br>".join(lines), unsafe_allow_html=True)


def render_log_panel(max_entries: int = 50, expanded: bool = False) -> None:
    """Render the live log panel from ObservableLogger. Safe to call even if logger absent."""
    try:
        from src.utils.observable_logger import get_observable_logger
        obs_logger = get_observable_logger()
        logs = obs_logger.get_recent(max_entries)
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
            icon      = _LEVEL_ICON.get(entry.get("level", ""), "•")
            component = entry.get("component", "?")
            message   = html.escape(str(entry.get("message", "")))
            ts        = entry.get("timestamp", "")[-12:]
            st.caption(f"{icon} `{ts}` [{component}] {message}")


def render_stage_grid(tracker: ProgressTracker) -> None:
    """Compact colour-coded stage grid. Uses Stage values that exist in the enum."""
    stage_groups = [
        ("🔍 Search",     [Stage.SEARCHING, Stage.CONSENSUS]),
        ("💬 ProAgent",   [Stage.PRO, Stage.ROUND_1_PRO, Stage.ROUND_2_PRO, Stage.ROUND_3_PRO]),
        ("🔴 ConAgent",   [Stage.CON, Stage.ROUND_1_CON, Stage.ROUND_2_CON, Stage.ROUND_3_CON]),
        ("✅ FactCheck",  [Stage.FACT_CHECK, Stage.FACT_CHECKING]),
        ("⚖️ Moderator",  [Stage.MODERATOR, Stage.MODERATING]),
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
    Compact resource monitor. B3-P4 fix: guarded with try/except —
    silently does nothing if psutil or ResourceManager are not available.
    """
    try:
        import psutil
        import os
        from src.resource.manager import get_resource_manager

        proc   = psutil.Process(os.getpid())
        rm     = get_resource_manager()
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        mem_limit = rm.max_memory_mb
        mem_pct   = (mem_mb / mem_limit) if mem_limit > 0 else 0.0
        cpu_pct   = proc.cpu_percent(interval=None)

        st.markdown(
            "<p style='font-family:var(--mono);font-size:9px;color:var(--text2);"
            "letter-spacing:4px;text-transform:uppercase;margin:18px 0 10px'>"
            "Resource Monitor</p>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        c1.metric("RAM", f"{mem_mb:.0f}MB", f"{mem_pct:.1%} limit")
        c2.metric("CPU", f"{cpu_pct:.1f}%")
        st.progress(min(1.0, mem_pct), text=f"Memory: {mem_mb:.0f} / {mem_limit} MB")
    except Exception:
        pass  # psutil or resource manager not available — skip silently
