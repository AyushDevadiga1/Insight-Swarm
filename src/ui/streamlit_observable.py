"""
src/ui/streamlit_observable.py — Final production version.
"""
import html, time
from typing import Optional
import streamlit as st
from src.ui.progress_tracker import ProgressTracker, Stage


def render_progress_panel(tracker: ProgressTracker) -> None:
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
                f"{upd.icon} +{stage_elapsed}s &nbsp; {html.escape(upd.message)}</span>"
            )
        st.markdown("<br>".join(lines), unsafe_allow_html=True)


def render_log_panel(max_entries: int = 50, expanded: bool = False) -> None:
    try:
        from src.utils.observable_logger import get_observable_logger
        logs = get_observable_logger().get_recent(max_entries)
    except Exception:
        return
    if not logs:
        return
    _ICON = {"ERROR":"🔴","WARNING":"🟡","INFO":"🔵","DEBUG":"⚪","CRITICAL":"🚨"}
    with st.expander("🔍 System Logs", expanded=expanded):
        for entry in reversed(logs):
            icon = _ICON.get(entry.get("level",""),"•")
            st.caption(f"{icon} `{entry.get('timestamp','')[-12:]}` [{entry.get('component','?')}] {html.escape(str(entry.get('message','')))}") 


def render_stage_grid(tracker: ProgressTracker) -> None:
    stage_groups = [
        ("🔍 Search",    [Stage.SEARCHING, Stage.CONSENSUS]),
        ("💬 ProAgent",  [Stage.PRO, Stage.ROUND_1_PRO, Stage.ROUND_2_PRO, Stage.ROUND_3_PRO]),
        ("🔴 ConAgent",  [Stage.CON, Stage.ROUND_1_CON, Stage.ROUND_2_CON, Stage.ROUND_3_CON]),
        ("✅ FactCheck", [Stage.FACT_CHECK, Stage.FACT_CHECKING]),
        ("⚖️ Moderator", [Stage.MODERATOR, Stage.MODERATING]),
    ]
    completed_stages = {u.stage for u in tracker.updates}
    current = tracker.current
    cols = st.columns(len(stage_groups))
    for col, (label, stages) in zip(cols, stage_groups):
        is_done    = all(s in completed_stages for s in stages)
        is_running = current is not None and current.stage in stages
        if is_done:        col.success(label)
        elif is_running:   col.warning(label)
        else:              col.info(label)


def render_resource_monitor() -> None:
    try:
        import psutil, os
        from src.resource.manager import get_resource_manager
        proc   = psutil.Process(os.getpid())
        rm     = get_resource_manager()
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        mem_pct = (mem_mb / rm.max_memory_mb) if rm.max_memory_mb > 0 else 0.0
        cpu_pct = proc.cpu_percent(interval=None)
        st.markdown(
            "<p style='font-family:var(--mono);font-size:9px;color:var(--text2);"
            "letter-spacing:4px;text-transform:uppercase;margin:18px 0 10px'>Resource Monitor</p>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        c1.metric("RAM", f"{mem_mb:.0f}MB", f"{mem_pct:.1%} limit")
        c2.metric("CPU", f"{cpu_pct:.1f}%")
        st.progress(min(1.0, mem_pct), text=f"Memory: {mem_mb:.0f} / {rm.max_memory_mb} MB")
    except Exception:
        pass
