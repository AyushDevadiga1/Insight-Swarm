from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class HITLConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, thread_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[thread_id] = websocket
    
    async def disconnect(self, thread_id: str):
        self.active_connections.pop(thread_id, None)
    
    async def notify_pending_review(self, thread_id: str, state: dict):
        if thread_id in self.active_connections:
            try:
                await self.active_connections[thread_id].send_json({
                    "type": "AWAITING_HUMAN_INPUT",
                    "state": state,
                    "claim": state.get("claim", ""),
                    "verification_results": state.get("verification_results", [])
                })
            except Exception as e:
                logger.error(f"Failed to notify pending review to {thread_id}: {e}")

hitl_manager = HITLConnectionManager()
