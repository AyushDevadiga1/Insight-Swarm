# 🎯 INSIGHTSWARM STRATEGIC REDESIGN PLAN
## Production-Grade Architecture Overhaul

**Date:** March 22, 2026  
**Status:** 🔴 **CRITICAL ARCHITECTURAL REDESIGN REQUIRED**  
**Objective:** Transform from buggy prototype to production-ready system  
**Timeline:** 3-5 days full implementation  
**Approach:** Fix the SYSTEM, not the SYMPTOMS

---

## 🔥 ROOT CAUSE ANALYSIS

### **Why the System Keeps Breaking**

The current implementation has **fundamental architectural flaws** that no amount of bug fixes can solve:

| **Issue** | **Root Cause** | **Impact** | **Severity** |
|-----------|---------------|-----------|--------------|
| Frontend Freezes | Synchronous blocking architecture | UI unresponsive 30+ seconds | 🔴 CRITICAL |
| RAM Exhaustion | No resource limits, memory leaks, unbounded caches | Crashes after 5-10 uses | 🔴 CRITICAL |
| API Failures | No fallback strategy, poor error handling | Random failures, unpredictable | 🔴 CRITICAL |
| Black Box UI | No observability, minimal logging | Can't debug, users confused | 🔴 CRITICAL |
| Tests Pass, Production Fails | Unit tests don't reflect real API constraints | False confidence | 🟡 HIGH |
| No Graceful Degradation | One component failure breaks everything | Brittle system | 🟡 HIGH |

---

## 📊 CURRENT vs TARGET ARCHITECTURE

### **Current Architecture (BROKEN):**

```
User Input → Streamlit (sync) → DebateOrchestrator (sync)
                                       ↓
                          Creates 4 LLM Clients (blocking)
                                       ↓
                          Each validates ALL providers (20s)
                                       ↓
                          Runs 3 rounds sequentially (60s)
                                       ↓
                          Writes to SQL (locks)
                                       ↓
                          Caches unbounded (memory leak)
                                       ↓
                          Returns or crashes
```

**Problems:**
- ❌ Everything blocks the main thread
- ❌ No progress visibility
- ❌ Redundant initialization
- ❌ No resource limits
- ❌ No fallback on failure
- ❌ No retry logic
- ❌ No circuit breakers

---

### **Target Architecture (PRODUCTION-READY):**

```
User Input → Streamlit UI (async)
                ↓
        Task Queue (background worker)
                ↓
        Orchestrator (w/ circuit breakers)
                ↓
        ┌───────┴────────┐
        ↓                ↓
   Lightweight       Fallback
   Fast Path         Path
        ↓                ↓
   [Cache Hit]      [Degraded Mode]
        ↓                ↓
   Progress Stream   Result + Warning
        ↓                
   Result Display
```

**Features:**
- ✅ Async/non-blocking
- ✅ Real-time progress
- ✅ Singleton clients
- ✅ Memory limits
- ✅ Fallback strategies
- ✅ Exponential backoff
- ✅ Circuit breakers
- ✅ Observability

---

## 🎯 STRATEGIC GOALS

### **Primary Objectives:**

1. **Make Observable** - User sees exactly what's happening
2. **Make Resilient** - System degrades gracefully, never crashes
3. **Make Lightweight** - <500MB RAM, instant startup
4. **Make Testable** - Sandbox environment matches production
5. **Make Maintainable** - Clear patterns, documented decisions

### **Success Metrics:**

| **Metric** | **Current** | **Target** |
|-----------|-------------|-----------|
| UI Responsiveness | 🔴 Freezes 30s | ✅ Always responsive |
| Startup Time | 🔴 20-30s | ✅ <2s |
| Memory Usage | 🔴 2GB+ (leak) | ✅ <500MB stable |
| API Failure Recovery | ❌ None | ✅ 3-tier fallback |
| User Visibility | 🔴 Black box | ✅ Full transparency |
| Error Recovery | ❌ Crashes | ✅ Degrades gracefully |
| Test Coverage | 🟡 Unit only | ✅ E2E + Load |

---

## 📋 IMPLEMENTATION PHASES

---

## **PHASE 0: DIAGNOSTIC & SANDBOX** (Day 1: 4 hours)

### **Objective:** Understand EXACTLY what's failing before fixing anything

### **0.1 Create Diagnostic Suite**

**File:** `tests/diagnostics/system_diagnostics.py`

```python
"""
Comprehensive system diagnostics - run this FIRST
Identifies bottlenecks, memory leaks, API issues
"""

import time
import tracemalloc
import psutil
import os
from src.llm.client import FreeLLMClient
from src.orchestration.debate import DebateOrchestrator

class SystemDiagnostics:
    """Comprehensive system health and performance diagnostics"""
    
    def __init__(self):
        self.results = {}
        self.process = psutil.Process(os.getpid())
    
    def run_all(self):
        """Run complete diagnostic suite"""
        print("\n" + "="*70)
        print("🔍 INSIGHTSWARM SYSTEM DIAGNOSTICS")
        print("="*70 + "\n")
        
        self.test_api_keys()
        self.test_client_initialization()
        self.test_memory_usage()
        self.test_orchestrator_performance()
        self.test_api_reliability()
        self.test_concurrent_requests()
        
        self.print_summary()
        return self.results
    
    def test_api_keys(self):
        """Test API key loading and validation"""
        print("Test 1: API Key Validation")
        print("-" * 70)
        
        from dotenv import load_dotenv
        load_dotenv()
        
        keys_to_check = {
            "GROQ_API_KEY": "gsk_",
            "CEREBRAS_API_KEY": "csk-",
            "OPENROUTER_API_KEY": "sk-or-",
            "TAVILY_API_KEY": "tvly-",
        }
        
        for key_name, prefix in keys_to_check.items():
            value = os.getenv(key_name)
            if value and value.startswith(prefix):
                print(f"✅ {key_name}: Loaded ({len(value)} chars)")
                self.results[f"api_key_{key_name.lower()}"] = "PASS"
            else:
                print(f"❌ {key_name}: Missing or invalid")
                self.results[f"api_key_{key_name.lower()}"] = "FAIL"
        
        print()
    
    def test_client_initialization(self):
        """Test LLM client initialization time and memory"""
        print("Test 2: Client Initialization")
        print("-" * 70)
        
        tracemalloc.start()
        mem_before = self.process.memory_info().rss / 1024 / 1024  # MB
        
        start = time.time()
        client = FreeLLMClient()
        elapsed = time.time() - start
        
        mem_after = self.process.memory_info().rss / 1024 / 1024  # MB
        mem_used = mem_after - mem_before
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"Time: {elapsed:.2f}s")
        print(f"Memory: {mem_used:.1f}MB increase")
        print(f"Peak: {peak / 1024 / 1024:.1f}MB")
        
        if elapsed > 5.0:
            print("⚠️  SLOW: Init takes >5s (liveness probes enabled?)")
            self.results["client_init"] = "SLOW"
        else:
            print("✅ FAST: Init <5s")
            self.results["client_init"] = "PASS"
        
        print()
    
    def test_memory_usage(self):
        """Test memory usage over multiple operations"""
        print("Test 3: Memory Leak Detection")
        print("-" * 70)
        
        mem_readings = []
        
        for i in range(5):
            client = FreeLLMClient()
            mem = self.process.memory_info().rss / 1024 / 1024
            mem_readings.append(mem)
            del client
            time.sleep(0.5)
        
        growth = mem_readings[-1] - mem_readings[0]
        
        print(f"Memory readings: {[f'{m:.1f}MB' for m in mem_readings]}")
        print(f"Growth: {growth:.1f}MB over 5 iterations")
        
        if growth > 100:
            print("❌ LEAK DETECTED: >100MB growth")
            self.results["memory_leak"] = "FAIL"
        else:
            print("✅ NO SIGNIFICANT LEAK")
            self.results["memory_leak"] = "PASS"
        
        print()
    
    def test_orchestrator_performance(self):
        """Test orchestrator initialization and first run"""
        print("Test 4: Orchestrator Performance")
        print("-" * 70)
        
        try:
            start = time.time()
            orch = DebateOrchestrator()
            init_time = time.time() - start
            
            print(f"Init time: {init_time:.2f}s")
            
            if init_time > 10:
                print("❌ CRITICAL: Init >10s (investigate client creation)")
                self.results["orch_init"] = "FAIL"
            else:
                print("✅ Init time acceptable")
                self.results["orch_init"] = "PASS"
            
            # Test simple claim (should hit hardcoded consensus)
            start = time.time()
            result = orch.run("The Earth is round")
            run_time = time.time() - start
            
            print(f"Simple claim time: {run_time:.2f}s")
            print(f"Verdict: {result.verdict}")
            
            if run_time > 60:
                print("⚠️  SLOW: Simple claim >60s")
                self.results["orch_run"] = "SLOW"
            else:
                print("✅ Performance acceptable")
                self.results["orch_run"] = "PASS"
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.results["orch_init"] = "FAIL"
            self.results["orch_run"] = "FAIL"
        
        print()
    
    def test_api_reliability(self):
        """Test actual API calls to each provider"""
        print("Test 5: Live API Provider Test")
        print("-" * 70)
        
        client = FreeLLMClient()
        
        providers_to_test = []
        if client.groq_available:
            providers_to_test.append(("groq", "Groq"))
        if client.cerebras_available:
            providers_to_test.append(("cerebras", "Cerebras"))
        if client.openrouter_available:
            providers_to_test.append(("openrouter", "OpenRouter"))
        
        for provider_key, provider_name in providers_to_test:
            try:
                start = time.time()
                response = client.call(
                    "Say 'test'",
                    max_tokens=10,
                    preferred_provider=provider_key,
                    timeout=10
                )
                elapsed = time.time() - start
                
                if response and len(response) > 0:
                    print(f"✅ {provider_name:12}: {elapsed:.2f}s - '{response[:20]}'")
                    self.results[f"api_{provider_key}"] = "PASS"
                else:
                    print(f"⚠️  {provider_name:12}: Empty response")
                    self.results[f"api_{provider_key}"] = "WARN"
            except Exception as e:
                error_msg = str(e)[:50]
                print(f"❌ {provider_name:12}: {error_msg}")
                self.results[f"api_{provider_key}"] = "FAIL"
        
        print()
    
    def test_concurrent_requests(self):
        """Test behavior under concurrent load"""
        print("Test 6: Concurrent Request Handling")
        print("-" * 70)
        
        # Simulate what happens when user submits multiple claims rapidly
        print("Simulating rapid consecutive submissions...")
        
        try:
            orch = DebateOrchestrator()
            
            claims = [
                "Coffee is healthy",
                "Exercise prevents disease",
                "Water is H2O"
            ]
            
            start = time.time()
            for i, claim in enumerate(claims, 1):
                print(f"  Claim {i}/3: {claim}")
                result = orch.run(claim)
                print(f"    → {result.verdict}")
            
            total_time = time.time() - start
            avg_time = total_time / 3
            
            print(f"\nTotal: {total_time:.1f}s, Avg: {avg_time:.1f}s per claim")
            
            if avg_time > 60:
                print("⚠️  SLOW: >60s per claim average")
                self.results["concurrent"] = "SLOW"
            else:
                print("✅ Performance acceptable")
                self.results["concurrent"] = "PASS"
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.results["concurrent"] = "FAIL"
        
        print()
    
    def print_summary(self):
        """Print diagnostic summary"""
        print("="*70)
        print("📊 DIAGNOSTIC SUMMARY")
        print("="*70)
        
        passed = sum(1 for v in self.results.values() if v == "PASS")
        failed = sum(1 for v in self.results.values() if v == "FAIL")
        warnings = sum(1 for v in self.results.values() if v in ("SLOW", "WARN"))
        
        print(f"\n✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}\n")
        
        if failed > 0:
            print("🔴 CRITICAL ISSUES FOUND")
            print("Failed tests:")
            for test, result in self.results.items():
                if result == "FAIL":
                    print(f"  - {test}")
        elif warnings > 0:
            print("🟡 PERFORMANCE ISSUES FOUND")
        else:
            print("🎉 ALL DIAGNOSTICS PASSED")
        
        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    diagnostics = SystemDiagnostics()
    results = diagnostics.run_all()
    
    # Exit code for CI/CD
    failed = sum(1 for v in results.values() if v == "FAIL")
    exit(0 if failed == 0 else 1)
```

### **0.2 Create Sandbox Environment**

**File:** `tests/sandbox/sandbox_env.py`

```python
"""
Isolated sandbox environment for testing changes
Simulates production constraints without affecting live system
"""

import os
import tempfile
import shutil
from pathlib import Path
from contextlib import contextmanager

class SandboxEnvironment:
    """Isolated environment for safe testing"""
    
    def __init__(self):
        self.sandbox_dir = None
        self.original_cwd = None
        self.original_env = None
    
    @contextmanager
    def activate(self):
        """Context manager for sandbox activation"""
        try:
            # Create isolated directory
            self.sandbox_dir = tempfile.mkdtemp(prefix="insightswarm_sandbox_")
            self.original_cwd = os.getcwd()
            
            # Copy essential files
            self._setup_sandbox()
            
            # Switch to sandbox
            os.chdir(self.sandbox_dir)
            
            print(f"✅ Sandbox activated: {self.sandbox_dir}")
            yield self.sandbox_dir
            
        finally:
            # Restore original state
            if self.original_cwd:
                os.chdir(self.original_cwd)
            
            # Cleanup
            if self.sandbox_dir and os.path.exists(self.sandbox_dir):
                shutil.rmtree(self.sandbox_dir)
                print("✅ Sandbox cleaned up")
    
    def _setup_sandbox(self):
        """Set up sandbox with minimal required files"""
        # Copy .env (if exists)
        env_file = Path(self.original_cwd) / ".env"
        if env_file.exists():
            shutil.copy(env_file, self.sandbox_dir)
        
        # Create empty databases
        Path(self.sandbox_dir / "insightswarm.db").touch()
        Path(self.sandbox_dir / "insightswarm_graph.db").touch()
        
        print("✅ Sandbox environment ready")


# Usage:
if __name__ == "__main__":
    with SandboxEnvironment().activate() as sandbox:
        print(f"Working in: {sandbox}")
        
        # Test code here - completely isolated
        from src.llm.client import FreeLLMClient
        client = FreeLLMClient()
        print(f"Providers available: groq={client.groq_available}")
```

### **0.3 API Quota Simulator**

**File:** `tests/sandbox/api_simulator.py`

```python
"""
Simulates API quota exhaustion and failures
Tests system behavior under real constraints
"""

class APIQuotaSimulator:
    """Mock API that simulates quota limits and failures"""
    
    def __init__(self, quota_limit=10, failure_rate=0.2):
        self.quota_limit = quota_limit
        self.calls_made = 0
        self.failure_rate = failure_rate
    
    def call(self, prompt, **kwargs):
        """Simulate API call with quota and failure"""
        import random
        
        self.calls_made += 1
        
        # Simulate quota exhaustion
        if self.calls_made > self.quota_limit:
            raise RuntimeError("QUOTA_EXHAUSTED: Rate limit exceeded")
        
        # Simulate random failures
        if random.random() < self.failure_rate:
            raise RuntimeError("API_ERROR: Temporary failure")
        
        # Simulate slow response
        import time
        time.sleep(random.uniform(0.5, 2.0))
        
        return "Simulated response"
    
    def reset(self):
        """Reset quota counter"""
        self.calls_made = 0
```

**Run diagnostics:**

```bash
# Day 1, Step 1: Run full diagnostics
python tests/diagnostics/system_diagnostics.py

# This will output a detailed report showing EXACTLY what's broken
```

---

## **PHASE 1: MAKE OBSERVABLE** (Day 1-2: 6 hours)

### **Objective:** User sees exactly what's happening at all times

### **1.1 Real-Time Logging System**

**File:** `src/utils/observable_logger.py`

```python
"""
Observable logging system - streams logs to both file AND UI
"""

import logging
import queue
import threading
from datetime import datetime

class ObservableLogger:
    """Logger that streams to both file and UI in real-time"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.log_queue = queue.Queue(maxsize=1000)
            self.subscribers = []
            self.initialized = True
    
    def log(self, level, component, message, **metadata):
        """
        Log a message with full context
        
        Args:
            level: ERROR, WARN, INFO, DEBUG
            component: Which part of system (API, UI, Agent, etc.)
            message: Human-readable message
            metadata: Additional structured data
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'component': component,
            'message': message,
            **metadata
        }
        
        # Add to queue (non-blocking)
        try:
            self.log_queue.put_nowait(log_entry)
        except queue.Full:
            pass  # Drop log if queue full (prevents memory leak)
        
        # Notify subscribers
        for subscriber in self.subscribers:
            try:
                subscriber(log_entry)
            except:
                pass  # Don't let subscriber errors break logging
        
        # Also log to standard logger
        logger = logging.getLogger(component)
        getattr(logger, level.lower())(message)
    
    def subscribe(self, callback):
        """Subscribe to real-time log stream"""
        self.subscribers.append(callback)
    
    def get_recent_logs(self, n=100):
        """Get last N log entries"""
        logs = []
        temp_queue = queue.Queue()
        
        # Drain queue into list
        while not self.log_queue.empty() and len(logs) < n:
            try:
                log = self.log_queue.get_nowait()
                logs.append(log)
                temp_queue.put(log)
            except queue.Empty:
                break
        
        # Put logs back
        while not temp_queue.empty():
            try:
                self.log_queue.put_nowait(temp_queue.get_nowait())
            except queue.Full:
                break
        
        return logs[-n:]


# Global instance
_observable_logger = ObservableLogger()

def get_observable_logger():
    return _observable_logger
```

### **1.2 UI Progress Display**

**File:** `src/ui/progress_tracker.py`

```python
"""
Real-time progress tracking for UI
Shows exactly what's happening at each stage
"""

import time
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class Stage(Enum):
    INITIALIZING = "initializing"
    SEARCHING = "searching"
    ROUND_1_PRO = "round_1_pro"
    ROUND_1_CON = "round_1_con"
    ROUND_2_PRO = "round_2_pro"
    ROUND_2_CON = "round_2_con"
    ROUND_3_PRO = "round_3_pro"
    ROUND_3_CON = "round_3_con"
    FACT_CHECKING = "fact_checking"
    MODERATING = "moderating"
    COMPLETE = "complete"
    ERROR = "error"

@dataclass
class ProgressUpdate:
    stage: Stage
    message: str
    progress_pct: float  # 0.0 to 1.0
    metadata: Optional[dict] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class ProgressTracker:
    """Tracks debate progress for UI display"""
    
    def __init__(self):
        self.current_stage = Stage.INITIALIZING
        self.start_time = time.time()
        self.updates = []
        self.callbacks = []
    
    def update(self, stage: Stage, message: str, metadata: dict = None):
        """Update progress"""
        self.current_stage = stage
        
        # Calculate progress percentage
        stage_map = {
            Stage.INITIALIZING: 0.05,
            Stage.SEARCHING: 0.10,
            Stage.ROUND_1_PRO: 0.20,
            Stage.ROUND_1_CON: 0.30,
            Stage.ROUND_2_PRO: 0.45,
            Stage.ROUND_2_CON: 0.60,
            Stage.ROUND_3_PRO: 0.75,
            Stage.ROUND_3_CON: 0.85,
            Stage.FACT_CHECKING: 0.90,
            Stage.MODERATING: 0.95,
            Stage.COMPLETE: 1.0,
            Stage.ERROR: 0.0,
        }
        
        progress = ProgressUpdate(
            stage=stage,
            message=message,
            progress_pct=stage_map.get(stage, 0.0),
            metadata=metadata or {}
        )
        
        self.updates.append(progress)
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(progress)
            except:
                pass
    
    def subscribe(self, callback):
        """Subscribe to progress updates"""
        self.callbacks.append(callback)
    
    def get_elapsed(self):
        """Get elapsed time"""
        return time.time() - self.start_time
```

### **1.3 Enhanced Streamlit UI**

**File:** `src/ui/streamlit_observable.py`

```python
"""
Observable Streamlit components - shows real-time progress and logs
"""

import streamlit as st
from src.utils.observable_logger import get_observable_logger
from src.ui.progress_tracker import ProgressTracker, Stage

def render_progress_panel(tracker: ProgressTracker):
    """Render real-time progress panel"""
    
    # Progress bar
    progress_pct = 0.0
    status_text = "Initializing..."
    
    if tracker.updates:
        latest = tracker.updates[-1]
        progress_pct = latest.progress_pct
        status_text = latest.message
    
    st.progress(progress_pct, text=status_text)
    
    # Detailed stage view
    with st.expander("📊 Detailed Progress", expanded=True):
        for update in tracker.updates[-10:]:  # Last 10 updates
            elapsed = update.timestamp - tracker.start_time
            icon = {
                Stage.INITIALIZING: "⚙️",
                Stage.SEARCHING: "🔍",
                Stage.ROUND_1_PRO: "💬",
                Stage.FACT_CHECKING: "✅",
                Stage.MODERATING: "⚖️",
                Stage.COMPLETE: "🎉",
                Stage.ERROR: "❌",
            }.get(update.stage, "•")
            
            st.caption(f"{icon} {elapsed:.1f}s - {update.message}")

def render_log_panel():
    """Render real-time log panel"""
    logger = get_observable_logger()
    
    with st.expander("🔍 System Logs", expanded=False):
        logs = logger.get_recent_logs(50)
        
        for log in reversed(logs):  # Newest first
            level_icon = {
                "ERROR": "🔴",
                "WARN": "🟡",
                "INFO": "🔵",
                "DEBUG": "⚪"
            }.get(log['level'], "•")
            
            st.caption(
                f"{level_icon} [{log['component']}] {log['message']}"
            )

def render_resource_monitor():
    """Render resource usage monitor"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    mem_mb = process.memory_info().rss / 1024 / 1024
    cpu_pct = process.cpu_percent(interval=0.1)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Memory Usage", f"{mem_mb:.0f} MB")
    
    with col2:
        st.metric("CPU Usage", f"{cpu_pct:.1f}%")
```

---

## **PHASE 2: MAKE RESILIENT** (Day 2-3: 8 hours)

### **Objective:** System never crashes, always degrades gracefully

### **2.1 Circuit Breaker Pattern**

**File:** `src/resilience/circuit_breaker.py`

```python
"""
Circuit breaker pattern for API calls
Prevents cascade failures and provides fast-fail
"""

import time
from enum import Enum
from dataclasses import dataclass
from threading import Lock

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # seconds

class CircuitBreaker:
    """Circuit breaker for API calls"""
    
    def __init__(self, name: str, config: CircuitConfig = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._lock = Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker"""
        with self._lock:
            # Check if circuit should move to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.config.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise RuntimeError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry in {self.config.timeout - (time.time() - self.last_failure_time):.0f}s"
                    )
        
        # Try to execute
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    print(f"✅ Circuit breaker '{self.name}' recovered (CLOSED)")
    
    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                print(f"🔴 Circuit breaker '{self.name}' OPEN after {self.failure_count} failures")
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                print(f"🔴 Circuit breaker '{self.name}' reopened during recovery")
    
    def get_state(self):
        """Get current circuit state"""
        return self.state
    
    def reset(self):
        """Manually reset circuit"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
```

### **2.2 Fallback Strategy**

**File:** `src/resilience/fallback_handler.py`

```python
"""
3-tier fallback strategy for graceful degradation
"""

from enum import Enum
from typing import Optional, Dict, Any

class FallbackTier(Enum):
    PRIMARY = 1      # Full functionality
    DEGRADED = 2     # Reduced functionality
    MINIMAL = 3      # Bare minimum

class FallbackHandler:
    """Manages graceful degradation across fallback tiers"""
    
    def __init__(self):
        self.current_tier = FallbackTier.PRIMARY
        self.fallback_reasons = []
    
    def execute_with_fallback(self, claim: str, orchestrator):
        """Execute debate with automatic fallback"""
        
        # Tier 1: Full debate with all providers
        if self.current_tier == FallbackTier.PRIMARY:
            try:
                return self._full_debate(claim, orchestrator)
            except Exception as e:
                print(f"⚠️  Primary tier failed: {e}")
                self.current_tier = FallbackTier.DEGRADED
                self.fallback_reasons.append(("PRIMARY_FAIL", str(e)))
        
        # Tier 2: Degraded mode (skip verification)
        if self.current_tier == FallbackTier.DEGRADED:
            try:
                return self._degraded_debate(claim, orchestrator)
            except Exception as e:
                print(f"⚠️  Degraded tier failed: {e}")
                self.current_tier = FallbackTier.MINIMAL
                self.fallback_reasons.append(("DEGRADED_FAIL", str(e)))
        
        # Tier 3: Minimal mode (cache only or simple response)
        return self._minimal_response(claim)
    
    def _full_debate(self, claim: str, orchestrator):
        """Full 3-round debate with verification"""
        return orchestrator.run(claim)
    
    def _degraded_debate(self, claim: str, orchestrator):
        """Simplified debate - 1 round, no verification"""
        from src.core.models import DebateState
        
        state = DebateState(claim=claim, num_rounds=1)
        
        # Single round only
        pro_resp = orchestrator.pro_agent.generate(state)
        state.pro_arguments.append(pro_resp.argument)
        
        con_resp = orchestrator.con_agent.generate(state)
        state.con_arguments.append(con_resp.argument)
        
        # Skip verification, go straight to moderator
        mod_resp = orchestrator.moderator.generate(state)
        state.verdict = mod_resp.verdict
        state.confidence = mod_resp.confidence * 0.7  # Lower confidence in degraded mode
        state.moderator_reasoning = f"DEGRADED MODE: {mod_resp.reasoning}"
        
        return state
    
    def _minimal_response(self, claim: str):
        """Minimal response when all else fails"""
        from src.core.models import DebateState
        
        state = DebateState(claim=claim)
        state.verdict = "INSUFFICIENT EVIDENCE"
        state.confidence = 0.0
        state.moderator_reasoning = (
            "System operating in minimal mode due to API limitations. "
            "Unable to perform full fact-checking analysis. "
            f"Fallback reasons: {', '.join(r[0] for r in self.fallback_reasons)}"
        )
        
        return state
    
    def get_status(self) -> Dict[str, Any]:
        """Get current fallback status"""
        return {
            "tier": self.current_tier.name,
            "tier_number": self.current_tier.value,
            "reasons": self.fallback_reasons
        }
```

### **2.3 Retry with Exponential Backoff**

**File:** `src/resilience/retry_handler.py`

```python
"""
Smart retry logic with exponential backoff
"""

import time
import random
from typing import Callable, Any

class RetryHandler:
    """Exponential backoff retry handler"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    break  # Don't sleep on last attempt
                
                # Calculate delay
                delay = min(
                    self.base_delay * (self.exponential_base ** attempt),
                    self.max_delay
                )
                
                # Add jitter to prevent thundering herd
                if self.jitter:
                    delay *= (0.5 + random.random())
                
                print(f"⚠️  Attempt {attempt + 1}/{self.max_retries + 1} failed: {e}")
                print(f"   Retrying in {delay:.1f}s...")
                time.sleep(delay)
        
        # All retries exhausted
        raise last_exception
```

---

## **PHASE 3: MAKE LIGHTWEIGHT** (Day 3-4: 8 hours)

### **Objective:** <500MB RAM, instant startup, no resource leaks

### **3.1 Resource Manager**

**File:** `src/resource/manager.py`

```python
"""
Central resource management with limits and cleanup
"""

import gc
import psutil
import os
from contextlib import contextmanager

class ResourceManager:
    """Manages system resources with hard limits"""
    
    def __init__(self, memory_limit_mb: int = 500):
        self.memory_limit_mb = memory_limit_mb
        self.process = psutil.Process(os.getpid())
    
    def check_memory(self):
        """Check if within memory limits"""
        mem_mb = self.process.memory_info().rss / 1024 / 1024
        
        if mem_mb > self.memory_limit_mb:
            print(f"⚠️  Memory limit exceeded: {mem_mb:.0f}MB / {self.memory_limit_mb}MB")
            self.force_cleanup()
            return False
        
        return True
    
    def force_cleanup(self):
        """Force garbage collection and cleanup"""
        print("🧹 Forcing cleanup...")
        gc.collect()
        
        # Clear caches
        from src.orchestration.cache import get_cache
        cache = get_cache()
        cache.cleanup_old_entries()
        
        mem_after = self.process.memory_info().rss / 1024 / 1024
        print(f"✅ Cleanup complete. Memory: {mem_after:.0f}MB")
    
    @contextmanager
    def resource_limit(self):
        """Context manager for resource-limited execution"""
        mem_before = self.process.memory_info().rss / 1024 / 1024
        
        try:
            yield
        finally:
            mem_after = self.process.memory_info().rss / 1024 / 1024
            mem_used = mem_after - mem_before
            
            if mem_used > 100:  # More than 100MB used
                print(f"⚠️  High memory usage detected: {mem_used:.0f}MB")
                self.force_cleanup()
```

### **3.2 Bounded Cache**

**File:** `src/orchestration/bounded_cache.py`

```python
"""
Cache with hard size limits and LRU eviction
"""

from collections import OrderedDict
import time

class BoundedCache:
    """LRU cache with size limits"""
    
    def __init__(self, max_entries: int = 1000, max_age_hours: int = 24):
        self.cache = OrderedDict()
        self.max_entries = max_entries
        self.max_age_seconds = max_age_hours * 3600
    
    def get(self, key: str):
        """Get from cache, return None if missing or expired"""
        if key in self.cache:
            entry = self.cache[key]
            
            # Check expiration
            if time.time() - entry['timestamp'] > self.max_age_seconds:
                del self.cache[key]
                return None
            
            # Move to end (LRU)
            self.cache.move_to_end(key)
            return entry['value']
        
        return None
    
    def set(self, key: str, value):
        """Set in cache with LRU eviction"""
        # Remove oldest if at limit
        if len(self.cache) >= self.max_entries:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def cleanup(self):
        """Remove expired entries"""
        now = time.time()
        expired_keys = [
            k for k, v in self.cache.items()
            if now - v['timestamp'] > self.max_age_seconds
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
```

### **3.3 Lazy Initialization**

**File:** `src/lazy/client_pool.py`

```python
"""
Lazy client initialization - create only when needed
"""

class LazyClientPool:
    """Client pool with lazy initialization"""
    
    def __init__(self):
        self._clients = {}
        self._initialized = set()
    
    def get_client(self, provider: str):
        """Get client for provider, initialize only if needed"""
        if provider not in self._initialized:
            print(f"🔧 Lazy-initializing {provider} client...")
            self._init_provider(provider)
            self._initialized.add(provider)
        
        return self._clients.get(provider)
    
    def _init_provider(self, provider: str):
        """Initialize specific provider"""
        from src.llm.client import FreeLLMClient
        
        if provider == "shared":
            self._clients["shared"] = FreeLLMClient()
        # Add other providers as needed
```

---

## **PHASE 4: ASYNC & NON-BLOCKING** (Day 4-5: 8 hours)

### **Objective:** UI never freezes, all operations non-blocking

### **4.1 Background Task Queue**

**File:** `src/async/task_queue.py`

```python
"""
Background task queue for non-blocking operations
"""

import threading
import queue
from typing import Callable, Any
from dataclasses import dataclass
import uuid

@dataclass
class Task:
    id: str
    func: Callable
    args: tuple
    kwargs: dict
    callback: Callable = None

class TaskQueue:
    """Background task queue with worker threads"""
    
    def __init__(self, num_workers: int = 1):
        self.queue = queue.Queue()
        self.results = {}
        self.workers = []
        
        # Start workers
        for _ in range(num_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)
    
    def submit(self, func: Callable, *args, callback: Callable = None, **kwargs) -> str:
        """Submit task to queue, returns task ID"""
        task_id = str(uuid.uuid4())
        
        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback
        )
        
        self.queue.put(task)
        return task_id
    
    def _worker(self):
        """Worker thread that processes tasks"""
        while True:
            try:
                task = self.queue.get()
                
                try:
                    result = task.func(*task.args, **task.kwargs)
                    self.results[task.id] = {"status": "success", "result": result}
                    
                    if task.callback:
                        task.callback(result)
                        
                except Exception as e:
                    self.results[task.id] = {"status": "error", "error": str(e)}
                
            except Exception as e:
                print(f"Worker error: {e}")
    
    def get_result(self, task_id: str):
        """Get result of completed task"""
        return self.results.get(task_id)


# Global task queue
_task_queue = TaskQueue(num_workers=2)

def get_task_queue():
    return _task_queue
```

### **4.2 Non-Blocking Streamlit Integration**

**File:** `src/ui/async_streamlit.py`

```python
"""
Async Streamlit integration using task queue
"""

import streamlit as st
import time
from src.async.task_queue import get_task_queue

def run_debate_async(claim: str, orchestrator):
    """Run debate in background, return task ID"""
    task_queue = get_task_queue()
    
    task_id = task_queue.submit(
        func=orchestrator.run,
        claim=claim
    )
    
    return task_id

def poll_task_result(task_id: str, timeout: int = 120):
    """Poll for task completion"""
    task_queue = get_task_queue()
    start_time = time.time()
    
    placeholder = st.empty()
    
    while time.time() - start_time < timeout:
        result = task_queue.get_result(task_id)
        
        if result:
            if result['status'] == 'success':
                placeholder.success("✅ Analysis complete!")
                return result['result']
            else:
                placeholder.error(f"❌ Error: {result['error']}")
                return None
        
        # Update progress
        elapsed = int(time.time() - start_time)
        placeholder.info(f"⏳ Processing... ({elapsed}s)")
        time.sleep(1)
    
    placeholder.warning("⏱️ Timeout - analysis took too long")
    return None
```

---

## **PHASE 5: VALIDATION** (Day 5: 4 hours)

### **Objective:** Comprehensive E2E testing before production

### **5.1 Integration Test Suite**

**File:** `tests/integration/test_full_system.py`

```python
"""
End-to-end integration tests
"""

import pytest
from src.orchestration.debate import DebateOrchestrator

def test_simple_claim():
    """Test with simple hardcoded claim"""
    orch = DebateOrchestrator()
    result = orch.run("The Earth is round")
    
    assert result.verdict == "TRUE"
    assert result.confidence > 0.9

def test_api_failure_recovery():
    """Test system recovers from API failures"""
    # This would use mocked API that fails
    pass

def test_memory_stability():
    """Test no memory leak over 10 consecutive runs"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    mem_readings = []
    
    orch = DebateOrchestrator()
    
    for i in range(10):
        result = orch.run(f"Test claim {i}")
        mem_mb = process.memory_info().rss / 1024 / 1024
        mem_readings.append(mem_mb)
    
    # Memory should not grow more than 100MB
    growth = mem_readings[-1] - mem_readings[0]
    assert growth < 100, f"Memory leak detected: {growth}MB growth"

def test_concurrent_requests():
    """Test handling multiple concurrent requests"""
    # This would test the task queue
    pass
```

---

## 📊 IMPLEMENTATION TIMELINE

| **Phase** | **Duration** | **Outcome** |
|-----------|-------------|------------|
| Phase 0: Diagnostics | 4 hours | Exact root causes identified |
| Phase 1: Observable | 6 hours | Full visibility into system |
| Phase 2: Resilient | 8 hours | Never crashes, graceful degradation |
| Phase 3: Lightweight | 8 hours | <500MB RAM, fast startup |
| Phase 4: Async | 8 hours | UI never freezes |
| Phase 5: Validation | 4 hours | Production-ready confidence |
| **TOTAL** | **38 hours** | **~5 days** |

---

## 🎯 SUCCESS CRITERIA

After completion, the system must pass ALL of these:

### **Functional Tests:**
- ✅ All diagnostics pass (no FAIL results)
- ✅ Simple claim completes in <30s
- ✅ Complex claim completes in <90s
- ✅ 10 consecutive claims complete without error
- ✅ System recovers from simulated API failure
- ✅ Degraded mode works when primary fails

### **Performance Tests:**
- ✅ Startup time <2 seconds
- ✅ Memory usage <500MB stable
- ✅ No memory growth over 10 runs
- ✅ UI responsive during processing

### **Observability Tests:**
- ✅ Progress updates every 5 seconds
- ✅ Logs visible in UI
- ✅ Error messages are actionable
- ✅ Resource usage visible

---

## 🚀 NEXT STEPS

**Day 1 Morning:**
1. Run diagnostics: `python tests/diagnostics/system_diagnostics.py`
2. Document ALL failures in detail
3. Set up sandbox environment
4. Create test cases for failures

**Day 1 Afternoon:**
5. Implement observable logging
6. Add progress tracking
7. Update UI with real-time feedback

**Day 2:**
8. Implement circuit breakers
9. Add fallback tiers
10. Test failure recovery

**Day 3:**
11. Add resource limits
12. Implement bounded caches
13. Profile memory usage

**Day 4:**
14. Implement task queue
15. Make UI non-blocking
16. Test concurrent operations

**Day 5:**
17. Run full test suite
18. Load testing
19. Production validation
20. Deploy

---

## 📝 DOCUMENTATION REQUIREMENTS

Each phase must include:
1. Code changes with git commits
2. Test results documented
3. Performance measurements
4. Before/after comparisons

---

**This is a COMPLETE SYSTEM REDESIGN, not a bug fix. It addresses the ROOT ARCHITECTURAL ISSUES that cause the problems you're experiencing.**

**Total effort: ~5 days for one developer working full-time, or ~10 days part-time.**

**The result: A production-ready, observable, resilient, lightweight fact-checking system.** ✅
