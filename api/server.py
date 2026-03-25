"""
InsightSwarm FastAPI Server
===========================
Thin REST wrapper around the existing DebateOrchestrator.
Exposes:
  POST /verify   – run a debate and return DebateState as JSON
  POST /feedback – record user thumbs-up / thumbs-down
  GET  /health   – liveness probe

Run with:
  python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import json
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# ── Path setup so imports from root work ─────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import validate_claim
from src.orchestration.debate import DebateOrchestrator
from src.orchestration.cache import record_feedback
from src.llm.client import RateLimitError

logger = logging.getLogger("insightswarm.api")
logging.basicConfig(level=logging.INFO)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="InsightSwarm API",
    description="Multi-Agent Truth Verification Protocol",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # CRA / other
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singleton orchestrator (heavy to initialise, reuse across requests) ───────
_orchestrator: Optional[DebateOrchestrator] = None


def get_orchestrator() -> DebateOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DebateOrchestrator()
    return _orchestrator


# ── Request / response models ─────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=500)


class FeedbackRequest(BaseModel):
    claim: str
    verdict: str
    value: str  # "UP" | "DOWN"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state_to_dict(state: Any) -> Dict[str, Any]:
    """Convert DebateState (Pydantic model or dict) to a plain dict."""
    if hasattr(state, "dict"):
        return state.dict()
    if hasattr(state, "__dict__"):
        return vars(state)
    return dict(state)


def _safe_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return list(val)


def _normalise(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all expected keys exist with sensible defaults."""
    return {
        "claim": raw.get("claim", ""),
        "verdict": raw.get("verdict") or "UNKNOWN",
        "confidence": float(raw.get("confidence") or 0.0),
        "moderator_reasoning": raw.get("moderator_reasoning") or raw.get("reasoning") or "",
        "pro_arguments": _safe_list(raw.get("pro_arguments")),
        "con_arguments": _safe_list(raw.get("con_arguments")),
        "pro_sources": _safe_list(raw.get("pro_sources")),
        "con_sources": _safe_list(raw.get("con_sources")),
        "verification_results": _safe_list(raw.get("verification_results")),
        "pro_verification_rate": float(raw.get("pro_verification_rate") or 0.0),
        "con_verification_rate": float(raw.get("con_verification_rate") or 0.0),
        "metrics": raw.get("metrics") or {},
        "is_cached": bool(raw.get("is_cached", False)),
        "num_rounds": int(raw.get("num_rounds") or 3),
        "retry_count": int(raw.get("retry_count") or 0),
        "pro_model_used": raw.get("pro_model_used"),
        "con_model_used": raw.get("con_model_used"),
        "moderator_model_used": raw.get("moderator_model_used"),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def api_status() -> Dict[str, Any]:
    """Return live health status for all configured LLM providers."""
    from src.monitoring.api_status import get_health_monitor
    monitor = get_health_monitor()
    return await monitor.get_status() if monitor else {}


@app.get("/stream")
async def stream_debate(claim: str, request: Request):
    """SSE endpoint for real-time debate progress."""
    import asyncio, threading, queue as _queue

    valid, err_msg = validate_claim(claim.strip())
    if not valid:
        async def err():
            yield f"event: error\ndata: {json.dumps({'type':'VALIDATION','message':err_msg})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    async def generate():
        q = _queue.Queue()
        def run():
            try:
                orch = get_orchestrator()
                for event_type, state in orch.stream(claim.strip(), str(uuid.uuid4())):
                    raw = _state_to_dict(state)
                    q.put({"type": event_type, "data": _normalise(raw)})
            except Exception as e:
                logger.exception("Stream thread failed")
                q.put({"type": "error", "data": {"message": str(e)}})
            finally:
                q.put(None)  # sentinel

        threading.Thread(target=run, daemon=True).start()

        while True:
            if await request.is_disconnected():
                break
            try:
                # Use a timeout so we can check for is_disconnected
                item = await asyncio.get_event_loop().run_in_executor(None, q.get, True, 1.0)
                if item is None:
                    yield f"event: done\ndata: {{\"message\":\"complete\"}}\n\n"
                    break
                yield f"event: {item['type']}\ndata: {json.dumps(item['data'])}\n\n"
            except _queue.Empty:
                continue

    return StreamingResponse(generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/verify")
def verify(req: VerifyRequest) -> Dict[str, Any]:
    claim = req.claim.strip()

    # ── Validate ──────────────────────────────────────────────────────────────
    valid, err_msg = validate_claim(claim)
    if not valid:
        raise HTTPException(status_code=422, detail=err_msg)

    # ── Run debate ────────────────────────────────────────────────────────────
    thread_id = str(uuid.uuid4())
    try:
        orchestrator = get_orchestrator()
        state = orchestrator.run(claim, thread_id)
        raw = _state_to_dict(state)
        return _normalise(raw)

    except RateLimitError as e:
        retry_after = int(getattr(e, "retry_after", 60) or 60)
        raise HTTPException(
            status_code=429,
            detail={
                "type": "RATE_LIMITED",
                "message": str(e),
                "retry_after": retry_after,
            },
        )
    except Exception as e:
        logger.exception("Debate failed")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "SYSTEM_ERROR",
                "message": str(e),
            },
        )


@app.post("/feedback")
def feedback(req: FeedbackRequest) -> Dict[str, str]:
    try:
        record_feedback(req.claim, req.verdict, req.value)
        return {"status": "recorded"}
    except Exception as e:
        logger.warning("Feedback recording failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
