import json
import logging
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections for real-time status broadcasting."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        payload = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

async def status_broadcaster():
    """Background task to poll health and broadcast to all WS clients."""
    from src.monitoring.api_status import get_health_monitor
    monitor = get_health_monitor()
    
    while True:
        if monitor:
            status = monitor.get_status()
            await manager.broadcast({"type": "api_status", "data": status})
        await asyncio.sleep(10)  # Broadcast every 10 seconds
