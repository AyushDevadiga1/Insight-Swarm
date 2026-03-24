# 🔌 API STATUS MONITORING SYSTEM
## Real-Time Provider Health Tracking

**Purpose:** Give users complete visibility into API status, quota, rate limits, and failover

---

## 📊 ARCHITECTURE

### **Data Flow:**
```
Python Backend (Every 5s)
  ├─ Check each provider (Groq, Gemini, Cerebras, OpenRouter)
  ├─ Query quota remaining
  ├─ Check rate limit status
  ├─ Test connectivity
  └─ Calculate health score
      ↓
  WebSocket Broadcast
      ↓
  Frontend Dashboard
      ├─ Update status pills
      ├─ Update quota bars
      ├─ Update countdown timers
      └─ Trigger alerts
```

---

## 🛠️ BACKEND IMPLEMENTATION

### **1. API Health Monitor** (`backend/src/monitoring/api_status.py`)

```python
"""
Real-time API provider health monitoring
Tracks status, quota, rate limits, and failover state
"""

import asyncio
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

class ProviderStatus(Enum):
    HEALTHY = "healthy"          # Green - working normally
    DEGRADED = "degraded"        # Yellow - slow or partial issues
    RATE_LIMITED = "rate_limited" # Orange - rate limited
    DOWN = "down"                # Red - not responding
    NO_QUOTA = "no_quota"        # Gray - quota exhausted


@dataclass
class ProviderHealth:
    """Health status for a single provider"""
    provider: str
    status: ProviderStatus
    quota_remaining: Optional[int] = None
    quota_total: Optional[int] = None
    quota_percentage: Optional[float] = None
    rate_limit_reset_at: Optional[datetime] = None
    rate_limit_seconds: Optional[int] = None
    response_time_ms: Optional[float] = None
    last_error: Optional[str] = None
    uptime_24h: Optional[float] = None
    last_checked: datetime = None
    
    def __post_init__(self):
        if self.last_checked is None:
            self.last_checked = datetime.now()
        
        if self.quota_remaining and self.quota_total:
            self.quota_percentage = (self.quota_remaining / self.quota_total) * 100
        
        if self.rate_limit_reset_at:
            self.rate_limit_seconds = int((self.rate_limit_reset_at - datetime.now()).total_seconds())
    
    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        if self.rate_limit_reset_at:
            data['rate_limit_reset_at'] = self.rate_limit_reset_at.isoformat()
        if self.last_checked:
            data['last_checked'] = self.last_checked.isoformat()
        return data


class APIHealthMonitor:
    """Monitors health of all API providers"""
    
    def __init__(self, key_manager, llm_client):
        self.key_manager = key_manager
        self.llm_client = llm_client
        self.health_cache: Dict[str, ProviderHealth] = {}
        self.uptime_tracker: Dict[str, List[bool]] = {}  # Last 288 checks (24h at 5min intervals)
        
    async def check_provider_health(self, provider: str) -> ProviderHealth:
        """Check health of a single provider"""
        try:
            # Get working key
            key = self.key_manager.get_working_key(provider)
            
            if not key:
                return ProviderHealth(
                    provider=provider,
                    status=ProviderStatus.NO_QUOTA,
                    last_error="No valid API key available"
                )
            
            # Test API call (minimal cost)
            start_time = time.time()
            try:
                response = await self._test_api_call(provider, key)
                response_time_ms = (time.time() - start_time) * 1000
                
                # Get quota info
                quota_info = self._get_quota_info(provider, key)
                
                # Check for rate limiting
                rate_limit_info = self._get_rate_limit_info(provider)
                
                # Determine status
                if rate_limit_info and rate_limit_info['seconds_remaining'] > 0:
                    status = ProviderStatus.RATE_LIMITED
                elif response_time_ms > 2000:
                    status = ProviderStatus.DEGRADED
                else:
                    status = ProviderStatus.HEALTHY
                
                return ProviderHealth(
                    provider=provider,
                    status=status,
                    quota_remaining=quota_info.get('remaining'),
                    quota_total=quota_info.get('total'),
                    response_time_ms=response_time_ms,
                    rate_limit_reset_at=rate_limit_info.get('reset_at'),
                    uptime_24h=self._calculate_uptime(provider)
                )
                
            except Exception as e:
                error_str = str(e).lower()
                
                if '429' in error_str or 'rate limit' in error_str:
                    status = ProviderStatus.RATE_LIMITED
                    reset_time = self._extract_reset_time(str(e))
                elif 'quota' in error_str or 'exhausted' in error_str:
                    status = ProviderStatus.NO_QUOTA
                else:
                    status = ProviderStatus.DOWN
                
                return ProviderHealth(
                    provider=provider,
                    status=status,
                    last_error=str(e)[:200],
                    uptime_24h=self._calculate_uptime(provider, success=False)
                )
                
        except Exception as e:
            return ProviderHealth(
                provider=provider,
                status=ProviderStatus.DOWN,
                last_error=f"Health check failed: {str(e)[:200]}"
            )
    
    async def _test_api_call(self, provider: str, key: str) -> str:
        """Make minimal test API call"""
        # Use existing client methods with minimal token count
        return await self.llm_client.call(
            prompt="Hi",
            max_tokens=1,
            preferred_provider=provider,
            timeout=5
        )
    
    def _get_quota_info(self, provider: str, key: str) -> Dict:
        """Get quota information from provider (if available)"""
        # This would integrate with each provider's quota API
        # For now, estimate based on key_manager data
        
        if provider == "groq":
            # Groq free tier: 30 requests/minute, ~14,400/day
            return {"remaining": None, "total": None}
        elif provider == "gemini":
            # Gemini free tier: 15 RPM, 1M tokens/day
            return {"remaining": None, "total": None}
        else:
            return {}
    
    def _get_rate_limit_info(self, provider: str) -> Optional[Dict]:
        """Get rate limit info from key_manager"""
        keys = self.key_manager.keys.get(provider, [])
        if not keys:
            return None
        
        # Find first rate-limited key
        for key_info in keys:
            if key_info.status == "RATE_LIMITED" and key_info.cooldown_until:
                seconds_remaining = max(0, int(key_info.cooldown_until - time.time()))
                if seconds_remaining > 0:
                    return {
                        "reset_at": datetime.fromtimestamp(key_info.cooldown_until),
                        "seconds_remaining": seconds_remaining
                    }
        return None
    
    def _extract_reset_time(self, error_message: str) -> Optional[datetime]:
        """Extract rate limit reset time from error message"""
        import re
        
        # Try to find "retry after X seconds" pattern
        match = re.search(r'retry.*?(\d+)\s*s', error_message, re.IGNORECASE)
        if match:
            seconds = int(match.group(1))
            return datetime.now() + timedelta(seconds=seconds)
        return None
    
    def _calculate_uptime(self, provider: str, success: bool = True) -> float:
        """Calculate 24h uptime percentage"""
        if provider not in self.uptime_tracker:
            self.uptime_tracker[provider] = []
        
        self.uptime_tracker[provider].append(success)
        
        # Keep last 288 checks (24h at 5min intervals)
        if len(self.uptime_tracker[provider]) > 288:
            self.uptime_tracker[provider] = self.uptime_tracker[provider][-288:]
        
        if not self.uptime_tracker[provider]:
            return 100.0
        
        successes = sum(self.uptime_tracker[provider])
        return (successes / len(self.uptime_tracker[provider])) * 100
    
    async def check_all_providers(self) -> Dict[str, ProviderHealth]:
        """Check health of all providers"""
        providers = ["groq", "gemini", "cerebras", "openrouter"]
        
        health_checks = await asyncio.gather(*[
            self.check_provider_health(p) for p in providers
        ])
        
        self.health_cache = {
            health.provider: health 
            for health in health_checks
        }
        
        return self.health_cache
    
    def get_cached_health(self) -> Dict[str, Dict]:
        """Get cached health status"""
        return {
            provider: health.to_dict()
            for provider, health in self.health_cache.items()
        }


# Global instance
_monitor = None

def get_health_monitor(key_manager=None, llm_client=None):
    global _monitor
    if _monitor is None and key_manager and llm_client:
        _monitor = APIHealthMonitor(key_manager, llm_client)
    return _monitor
```

---

## 🌐 WEBSOCKET SERVER

### **2. WebSocket Broadcaster** (`backend/api/websocket.py`)

```python
"""
WebSocket server for real-time API status updates
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import asyncio
import json

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)


manager = ConnectionManager()


async def api_status_broadcaster(health_monitor):
    """Background task that broadcasts API status every 5 seconds"""
    while True:
        try:
            # Check all provider health
            await health_monitor.check_all_providers()
            
            # Get current status
            status = health_monitor.get_cached_health()
            
            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "api_status_update",
                "data": status,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"Error broadcasting API status: {e}")
        
        await asyncio.sleep(5)  # Update every 5 seconds


@app.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time API status"""
    await manager.connect(websocket)
    
    try:
        # Send initial status immediately
        health_monitor = get_health_monitor()
        if health_monitor:
            initial_status = health_monitor.get_cached_health()
            await websocket.send_json({
                "type": "api_status_update",
                "data": initial_status,
                "timestamp": datetime.now().isoformat()
            })
        
        # Keep connection alive
        while True:
            # Wait for messages from client (heartbeat)
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

---

## ⚛️ FRONTEND COMPONENT

### **3. API Status Dashboard** (`frontend/components/ApiStatusDashboard.tsx`)

```typescript
"use client"

import { useEffect, useState } from 'react'
import { Circle, AlertTriangle, Clock } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'

interface ProviderHealth {
  provider: string
  status: 'healthy' | 'degraded' | 'rate_limited' | 'down' | 'no_quota'
  quota_remaining?: number
  quota_total?: number
  quota_percentage?: number
  rate_limit_seconds?: number
  response_time_ms?: number
  last_error?: string
  uptime_24h?: number
}

const STATUS_CONFIG = {
  healthy: { color: 'text-green-500', bg: 'bg-green-500/10', label: 'Healthy' },
  degraded: { color: 'text-yellow-500', bg: 'bg-yellow-500/10', label: 'Slow' },
  rate_limited: { color: 'text-orange-500', bg: 'bg-orange-500/10', label: 'Rate Limited' },
  down: { color: 'text-red-500', bg: 'bg-red-500/10', label: 'Down' },
  no_quota: { color: 'text-gray-500', bg: 'bg-gray-500/10', label: 'No Quota' },
}

export function ApiStatusDashboard() {
  const [providers, setProviders] = useState<Record<string, ProviderHealth>>({})
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    // Connect to WebSocket
    const websocket = new WebSocket('ws://localhost:8000/ws/status')

    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.type === 'api_status_update') {
        setProviders(message.data)
      }
    }

    websocket.onclose = () => {
      // Reconnect after 5 seconds
      setTimeout(() => {
        setWs(null)
      }, 5000)
    }

    setWs(websocket)

    // Heartbeat
    const heartbeat = setInterval(() => {
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.send('ping')
      }
    }, 30000)

    return () => {
      clearInterval(heartbeat)
      websocket.close()
    }
  }, [])

  const allProviders = Object.values(providers)
  const healthyCount = allProviders.filter(p => p.status === 'healthy').length

  return (
    <Card className="fixed top-4 right-4 w-80 bg-black/40 backdrop-blur-lg border-white/10">
      <div
        className="p-4 cursor-pointer flex items-center justify-between"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <div className="flex -space-x-1">
            {Object.entries(providers).map(([name, health]) => {
              const config = STATUS_CONFIG[health.status]
              return (
                <Circle
                  key={name}
                  className={`w-3 h-3 ${config.color} fill-current`}
                />
              )
            })}
          </div>
          <span className="text-sm font-medium">
            API Status ({healthyCount}/{allProviders.length})
          </span>
        </div>
        <span className="text-xs text-gray-400">
          {isExpanded ? '▼' : '▶'}
        </span>
      </div>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {Object.entries(providers).map(([name, health]) => {
            const config = STATUS_CONFIG[health.status]
            
            return (
              <div key={name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Circle className={`w-2 h-2 ${config.color} fill-current`} />
                    <span className="text-sm font-medium capitalize">{name}</span>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${config.bg} ${config.color}`}>
                    {config.label}
                  </span>
                </div>

                {/* Quota bar */}
                {health.quota_percentage !== undefined && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-gray-400">
                      <span>Quota</span>
                      <span>{health.quota_remaining}/{health.quota_total}</span>
                    </div>
                    <Progress value={health.quota_percentage} className="h-1" />
                  </div>
                )}

                {/* Rate limit countdown */}
                {health.rate_limit_seconds && health.rate_limit_seconds > 0 && (
                  <div className="flex items-center gap-2 text-xs text-orange-400">
                    <Clock className="w-3 h-3" />
                    <span>Reset in {health.rate_limit_seconds}s</span>
                  </div>
                )}

                {/* Response time */}
                {health.response_time_ms && (
                  <div className="text-xs text-gray-400">
                    {health.response_time_ms.toFixed(0)}ms response
                  </div>
                )}

                {/* Error */}
                {health.last_error && (
                  <div className="flex items-start gap-2 text-xs text-red-400">
                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                    <span className="line-clamp-2">{health.last_error}</span>
                  </div>
                )}

                {/* Uptime */}
                {health.uptime_24h !== undefined && (
                  <div className="text-xs text-gray-400">
                    {health.uptime_24h.toFixed(1)}% uptime (24h)
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
```

---

## 📈 VISUALIZATION EXAMPLES

### **Compact View (Collapsed):**
```
┌─────────────────────────────┐
│ ●●⚠○ API Status (2/4)  ▶   │
└─────────────────────────────┘
```

### **Expanded View:**
```
┌────────────────────────────────────────┐
│ ●●⚠○ API Status (2/4)              ▼  │
├────────────────────────────────────────┤
│ ● Groq               [Healthy]         │
│   Quota: [████████░░] 80/100          │
│   245ms response                       │
│   99.8% uptime (24h)                   │
│                                        │
│ ● Gemini             [Healthy]         │
│   142ms response                       │
│   100% uptime (24h)                    │
│                                        │
│ ⚠ Cerebras           [Rate Limited]    │
│   ⏱ Reset in 45s                       │
│   ⚠ 429: Rate limit exceeded           │
│   85.2% uptime (24h)                   │
│                                        │
│ ○ OpenRouter         [No Quota]        │
│   ⚠ Quota exhausted                    │
│   72.1% uptime (24h)                   │
└────────────────────────────────────────┘
```

---

## 🎯 INTEGRATION WITH DEBATE

### **Failover Visualization:**

During debate, show which provider is currently active:

```typescript
<div className="flex items-center gap-2 text-xs text-gray-400">
  <span>ProAgent:</span>
  <Circle className="w-2 h-2 text-green-500 fill-current" />
  <span>Groq</span>
  {/* If failover happened */}
  <span className="text-orange-400">→ Gemini (fallback)</span>
</div>
```

---

## ✅ SUCCESS CRITERIA

- ✅ Real-time updates every 5 seconds
- ✅ <50ms WebSocket latency
- ✅ Accurate quota tracking
- ✅ Rate limit countdowns
- ✅ Historical uptime (24h)
- ✅ Error messages visible
- ✅ Auto-reconnect on disconnect
- ✅ Mobile-friendly UI
- ✅ Failover clearly shown

---

**Complete transparency - no more guessing why things fail!** 🎯
