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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import json
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field

# ── Path setup so imports from root work ─────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import validate_claim
from src.orchestration.debate import DebateOrchestrator
from src.core.models import DebateState
from src.orchestration.cache import record_feedback
from src.llm.client import RateLimitError
from fastapi import WebSocket, WebSocketDisconnect
from api.websocket_hitl import hitl_manager

logger = logging.getLogger("insightswarm.api")
logging.basicConfig(level=logging.INFO)

# ── Pre-warm orchestrator at startup ─────────────────────────────────────────
# Loads sentence-transformers embedding model NOW so the first user request
# doesn't block for 5-15s waiting for the model to download.
@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    loop = asyncio.get_event_loop()
    logger.info("Pre-warming orchestrator (loading embedding model)...")
    try:
        await loop.run_in_executor(None, get_orchestrator)
        logger.info("Orchestrator pre-warm complete.")
    except Exception as e:
        logger.warning("Orchestrator pre-warm failed (non-fatal): %s", e)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="InsightSwarm API",
    description="Multi-Agent Truth Verification Protocol",
    version="1.0.0",
    lifespan=lifespan,
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

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
        <head>
            <title>InsightSwarm API</title>
            <style>
                body { font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); padding: 2.5rem; border-radius: 1.5rem; text-align: center; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); max-width: 500px; }
                h1 { color: #38bdf8; margin-bottom: 1rem; font-weight: 700; }
                p { line-height: 1.6; color: #94a3b8; }
                .status { display: inline-block; padding: 0.5rem 1rem; background: #10b981; color: #fff; border-radius: 9999px; font-size: 0.875rem; font-weight: 600; margin-bottom: 1.5rem; }
                .instruction { background: #1e293b; padding: 1rem; border-radius: 0.75rem; text-align: left; border-left: 4px solid #38bdf8; margin-top: 2rem; }
                code { color: #f472b6; font-family: 'Fira Code', monospace; }
                a { color: #38bdf8; text-decoration: none; font-weight: 600; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="status">Backend Online</div>
                <h1>🦅 InsightSwarm API</h1>
                <p>The multi-agent truth verification backend is running correctly.</p>
                <div class="instruction">
                    <strong>Next Step:</strong> Start the UI to interact with the app.
                    <br><br>
                    1. Open a new terminal<br>
                    2. Run <code>cd frontend && npm run dev</code><br>
                    3. Visit <a href="http://localhost:5173">http://localhost:5173</a>
                </div>
                <p style="margin-top: 1.5rem; font-size: 0.8rem;"><a href="/health">Health Check</a> | <a href="/docs">Docs</a></p>
            </div>
        </body>
    </html>
    """


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
async def stream_debate(claim: str, request: Request, thread_id: str = None):
    """SSE endpoint for real-time debate progress."""
    import asyncio, threading, queue as _queue
    
    if not thread_id:
        thread_id = str(uuid.uuid4())

    valid, err_msg = validate_claim(claim.strip())
    if not valid:
        async def err():
            yield f"event: error\ndata: {json.dumps({'type':'VALIDATION','message':err_msg})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    async def generate():
        q = _queue.Queue()
        DEBATE_TIMEOUT_S = 180   # hard cap — emit error if debate takes > 3 min
        HEARTBEAT_EVERY_S = 3    # keep browser alive during silent LLM/Tavily phases
        
        def run():
            start_time = time.time()
            try:
                orch = get_orchestrator()
                
                class SSETracker:
                    def set_stage(self, stage, message=""):
                        s_str = str(stage).split('.')[-1].lower()
                        elapsed = round(time.time() - start_time, 2)
                        # Map internal stage strings to frontend stage keys
                        mapped = s_str
                        if s_str == "decomposing":
                            mapped = "decomposing"
                        elif s_str == "searching":
                            mapped = "searching"
                        elif s_str == "consensus":
                            mapped = "consensus_check"
                        elif s_str == "fact_check":
                            mapped = "fact_checking"
                        elif s_str == "moderator":
                            mapped = "moderating"
                        elif s_str == "complete":
                            mapped = "complete"
                        elif s_str == "error":
                            mapped = "error"
                        elif "round" in message.lower():
                            for i in range(1, 10):
                                if str(i) in message:
                                    mapped = f"round_{i}_{s_str}"
                                    break
                        
                        q.put({"type": "stage", "data": {
                            "stage": mapped,
                            "message": message,
                            "progress": 0.5,
                            "elapsed": elapsed
                        }})
                
                orch.set_tracker(SSETracker())
                
                config = {"configurable": {"thread_id": thread_id}}
                prev_pro = 0
                prev_con = 0
                prev_src = 0
                sub_claims_emitted = False   # Guard: emit sub_claims only once
                
                for event_type, state in orch.stream(claim.strip(), thread_id):
                    raw = _state_to_dict(state)
                    
                    # ── Emit sub_claims once after decomposition is visible ────
                    if not sub_claims_emitted:
                        sub_claims_raw = raw.get("sub_claims") or []
                        if sub_claims_raw:
                            q.put({"type": "sub_claims", "data": {"claims": sub_claims_raw}})
                            sub_claims_emitted = True

                    # Extract lists once per tick — all default to [] if None
                    pro_args = raw.get("pro_arguments") or []
                    con_args = raw.get("con_arguments") or []
                    src_list = raw.get("verification_results") or []

                    cur_pro = len(pro_args)
                    if cur_pro > prev_pro:
                        for i in range(prev_pro, cur_pro):
                            q.put({"type": "pro_argument", "data": pro_args[i]})
                        prev_pro = cur_pro

                    cur_con = len(con_args)
                    if cur_con > prev_con:
                        for i in range(prev_con, cur_con):
                            q.put({"type": "con_argument", "data": con_args[i]})
                        prev_con = cur_con

                    cur_src = len(src_list)
                    if cur_src > prev_src:
                        for i in range(prev_src, cur_src):
                            q.put({"type": "verification_result", "data": src_list[i]})
                        prev_src = cur_src
                        
                    if event_type in ("complete", "cache_hit"):
                        # Check if graph paused
                        graph_state = orch.graph.get_state(config)
                        if graph_state and graph_state.next and "human_review" in graph_state.next:
                            q.put({"type": "human_review_required", "data": _normalise(raw)})
                        else:
                            q.put({"type": "verdict", "data": _normalise(raw)})
                        
            except Exception as e:
                logger.exception("Stream thread failed")
                q.put({"type": "error", "data": {"type": "SYSTEM_ERROR", "message": str(e)}})
            finally:
                q.put(None)  # sentinel

        threading.Thread(target=run, daemon=True).start()

        last_heartbeat = time.time()
        debate_start   = time.time()

        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.get_event_loop().run_in_executor(None, q.get, True, 1.0)
                last_heartbeat = time.time()
                if item is None:
                    yield f"event: done\ndata: {{\"message\":\"complete\"}}\n\n"
                    break
                yield f"event: {item['type']}\ndata: {json.dumps(item['data'])}\n\n"
            except _queue.Empty:
                elapsed = time.time() - debate_start
                # Hard timeout guard — emit error event if debate stalls
                if elapsed > DEBATE_TIMEOUT_S:
                    yield (
                        f"event: error\ndata: {json.dumps({'type': 'TIMEOUT', 'message': f'Debate timed out after {int(elapsed)}s.'})}\n\n"
                    )
                    break
                # Send heartbeat every 3s so the browser knows we're alive
                if time.time() - last_heartbeat >= HEARTBEAT_EVERY_S:
                    yield f"event: heartbeat\ndata: {json.dumps({'elapsed': round(elapsed, 1)})}\n\n"
                    last_heartbeat = time.time()
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

class ResumeRequest(BaseModel):
    source_overrides: Dict[str, str] = {}
    verdict_override: Optional[str] = None

@app.post("/api/debate/resume/{thread_id}")
def resume_debate(thread_id: str, human_input: ResumeRequest) -> Dict[str, Any]:
    """Resume debate after human intervention."""
    orchestrator = get_orchestrator()
    config = {"configurable": {"thread_id": thread_id}}
    
    current_state = orchestrator.graph.get_state(config)
    if not current_state or not current_state.values:
        raise HTTPException(status_code=404, detail="Thread state not found")
        
    state_vals = current_state.values
    overrides = human_input.dict()
    
    for source_url, new_rating in overrides.get("source_overrides", {}).items():
        for result in state_vals.get("verification_results", []):
            if result.get("url") == source_url:
                result["status"] = new_rating
                result["human_override"] = True
    
    if overrides.get("verdict_override"):
        state_vals["human_verdict_override"] = overrides["verdict_override"]
        
    # Resume execution
    final_state_raw = orchestrator.graph.invoke(
        None,  # Continue from checkpoint
        config=config,
        input=state_vals
    )
    
    if isinstance(final_state_raw, dict):
        final_state = DebateState.model_validate(final_state_raw)
    elif hasattr(final_state_raw, "model_dump"):
        final_state = final_state_raw
    else:
        final_state = DebateState.model_validate(dict(final_state_raw))
        
    return _normalise(_state_to_dict(final_state))

@app.websocket("/ws/hitl/{thread_id}")
async def hitl_websocket(websocket: WebSocket, thread_id: str):
    await hitl_manager.connect(thread_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle human override over ws if desired
            if data.get("type") == "OVERRIDE":
                pass
    except WebSocketDisconnect:
        await hitl_manager.disconnect(thread_id)
