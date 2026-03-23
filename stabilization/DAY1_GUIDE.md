# 🚀 DAY 1 IMPLEMENTATION GUIDE
## Start Here: Diagnostic Phase & Quick Wins

**Date:** March 22, 2026  
**Timeline:** 4-6 hours  
**Objective:** Understand EXACTLY what's broken + Get quick visibility

---

## 🎯 TODAY'S GOALS

By end of today, you will have:

1. ✅ **Complete diagnostic report** showing all bottlenecks
2. ✅ **Observable logging** so you can see what's happening
3. ✅ **Quick fixes** for immediate relief
4. ✅ **Baseline metrics** to measure improvement

---

## ⏰ HOUR-BY-HOUR SCHEDULE

### **Hour 1: Set Up Diagnostics (9:00 AM - 10:00 AM)**

**Create the diagnostic infrastructure**

**Step 1.1: Create test directory structure** (5 min)

```bash
cd C:\Users\hp\Desktop\InsightSwarm

# Create test directories
mkdir -p tests\diagnostics
mkdir -p tests\sandbox
mkdir -p tests\integration

# Create __init__.py files
echo. > tests\__init__.py
echo. > tests\diagnostics\__init__.py
echo. > tests\sandbox\__init__.py
```

**Step 1.2: Create system diagnostics script** (25 min)

Save this as `tests\diagnostics\system_diagnostics.py`:

```python
#!/usr/bin/env python3
"""
System Diagnostics - Run this FIRST to understand what's broken
"""

import os
import sys
import time
import psutil
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class QuickDiagnostics:
    """Fast diagnostic tests"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.issues_found = []
    
    def run(self):
        print("\n" + "="*70)
        print("🔍 INSIGHTSWARM QUICK DIAGNOSTICS")
        print("="*70 + "\n")
        
        self.test_environment()
        self.test_imports()
        self.test_api_keys()
        self.test_client_speed()
        self.test_memory_baseline()
        
        self.print_summary()
    
    def test_environment(self):
        print("📦 Environment Check")
        print("-" * 70)
        
        print(f"Python: {sys.version.split()[0]}")
        print(f"Working Dir: {os.getcwd()}")
        print(f"RAM Available: {psutil.virtual_memory().available / 1024 / 1024 / 1024:.1f}GB")
        print()
    
    def test_imports(self):
        print("📚 Import Tests")
        print("-" * 70)
        
        imports_to_test = [
            "streamlit",
            "groq",
            "google.generativeai",
            "langgraph",
            "pydantic",
            "requests"
        ]
        
        for module in imports_to_test:
            try:
                __import__(module)
                print(f"✅ {module}")
            except ImportError as e:
                print(f"❌ {module}: {e}")
                self.issues_found.append(f"Missing dependency: {module}")
        
        print()
    
    def test_api_keys(self):
        print("🔑 API Key Check")
        print("-" * 70)
        
        from dotenv import load_dotenv
        load_dotenv()
        
        keys = {
            "GROQ_API_KEY": ("gsk_", 30),
            "CEREBRAS_API_KEY": ("csk-", 30),
            "OPENROUTER_API_KEY": ("sk-or-", 30),
            "TAVILY_API_KEY": ("tvly-", 20),
        }
        
        for key_name, (prefix, min_len) in keys.items():
            value = os.getenv(key_name)
            
            if not value:
                print(f"❌ {key_name}: NOT FOUND")
                self.issues_found.append(f"Missing API key: {key_name}")
            elif not value.startswith(prefix):
                print(f"❌ {key_name}: WRONG PREFIX (expected {prefix})")
                self.issues_found.append(f"Invalid API key format: {key_name}")
            elif len(value) < min_len:
                print(f"❌ {key_name}: TOO SHORT ({len(value)} chars)")
                self.issues_found.append(f"Invalid API key length: {key_name}")
            else:
                print(f"✅ {key_name}: OK ({len(value)} chars)")
        
        print()
    
    def test_client_speed(self):
        print("⚡ Client Initialization Speed")
        print("-" * 70)
        
        try:
            from src.llm.client import FreeLLMClient
            
            mem_before = self.process.memory_info().rss / 1024 / 1024
            
            start = time.time()
            client = FreeLLMClient()
            elapsed = time.time() - start
            
            mem_after = self.process.memory_info().rss / 1024 / 1024
            mem_used = mem_after - mem_before
            
            print(f"Time: {elapsed:.2f}s")
            print(f"Memory: +{mem_used:.1f}MB")
            
            if elapsed > 5.0:
                print(f"⚠️  SLOW: >5s (likely liveness probes enabled)")
                self.issues_found.append("Slow client initialization")
            else:
                print(f"✅ FAST: <5s")
            
            # Check provider availability
            providers = {
                "Groq": client.groq_available,
                "Cerebras": client.cerebras_available,
                "OpenRouter": client.openrouter_available,
            }
            
            print("\nProvider Status:")
            for name, available in providers.items():
                status = "✅ Available" if available else "❌ Not available"
                print(f"  {name:12}: {status}")
                
                if not available:
                    self.issues_found.append(f"Provider unavailable: {name}")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.issues_found.append(f"Client init failed: {str(e)[:50]}")
        
        print()
    
    def test_memory_baseline(self):
        print("💾 Memory Baseline")
        print("-" * 70)
        
        mem_mb = self.process.memory_info().rss / 1024 / 1024
        print(f"Current usage: {mem_mb:.1f}MB")
        
        if mem_mb > 500:
            print(f"⚠️  HIGH: Process using >{mem_mb:.0f}MB")
            self.issues_found.append("High baseline memory usage")
        else:
            print(f"✅ OK: Within normal range")
        
        print()
    
    def print_summary(self):
        print("="*70)
        print("📊 DIAGNOSTIC SUMMARY")
        print("="*70)
        
        if not self.issues_found:
            print("\n🎉 NO CRITICAL ISSUES FOUND\n")
        else:
            print(f"\n❌ {len(self.issues_found)} ISSUE(S) FOUND:\n")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"{i}. {issue}")
            print()
        
        print("Next steps:")
        print("1. Fix any issues found above")
        print("2. Run full diagnostics: python tests/diagnostics/full_diagnostics.py")
        print("3. Implement observability features")
        print()

if __name__ == "__main__":
    diag = QuickDiagnostics()
    diag.run()
```

**Step 1.3: Run diagnostics** (5 min)

```bash
python tests\diagnostics\system_diagnostics.py
```

**IMPORTANT:** Save the output! This is your baseline.

**Step 1.4: Document findings** (25 min)

Create `DIAGNOSTIC_RESULTS.txt` with the output and your observations:

```
Date: [Today's date]
Time: [Current time]

=== DIAGNOSTIC OUTPUT ===
[Paste full output here]

=== KEY FINDINGS ===
1. [Issue 1]
2. [Issue 2]
...

=== PRIORITY FIXES ===
1. [Fix 1 - why it's needed]
2. [Fix 2 - why it's needed]
...
```

---

### **Hour 2: Implement Observable Logging (10:00 AM - 11:00 AM)**

**Add real-time logging so you can see what's happening**

**Step 2.1: Create observable logger** (30 min)

Save as `src\utils\simple_logger.py`:

```python
"""
Simple observable logger - streams to both file and console
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

class ObservableLogger:
    """Logger that outputs to both file and console clearly"""
    
    def __init__(self, name="InsightSwarm", log_file="debug.log"):
        self.name = name
        self.log_file = Path(log_file)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler (INFO level)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console_fmt = logging.Formatter(
            '%(levelname)s [%(name)s] %(message)s'
        )
        console.setFormatter(console_fmt)
        
        # File handler (DEBUG level)
        file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
        )
        file_handler.setFormatter(file_fmt)
        
        self.logger.addHandler(console)
        self.logger.addHandler(file_handler)
    
    def info(self, message):
        self.logger.info(message)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)

# Global instance
_logger = None

def get_logger():
    global _logger
    if _logger is None:
        _logger = ObservableLogger()
    return _logger
```

**Step 2.2: Add logging to critical points** (30 min)

Open `src\llm\client.py` and add logging at the start of `__init__`:

```python
def __init__(self):
    from src.utils.simple_logger import get_logger
    logger = get_logger()
    logger.info("🔧 Initializing LLM Client...")
    
    # ... existing code ...
    
    logger.info(f"✅ LLM Client ready (Groq: {self.groq_available}, Cerebras: {self.cerebras_available})")
```

Open `src\orchestration\debate.py` and add logging:

```python
def __init__(self, ...):
    from src.utils.simple_logger import get_logger
    logger = get_logger()
    logger.info("🎬 Initializing Debate Orchestrator...")
    
    # ... existing code ...
    
    logger.info("✅ Orchestrator ready")

def run(self, claim: str, thread_id: str = "default"):
    from src.utils.simple_logger import get_logger
    logger = get_logger()
    logger.info(f"🔍 Starting debate: '{claim[:50]}...'")
    
    # ... existing code ...
    
    logger.info(f"✅ Debate complete: {result.verdict}")
    return result
```

---

### **Hour 3: Quick Performance Fixes (11:00 AM - 12:00 PM)**

**Apply the most impactful fixes from earlier analysis**

**Step 3.1: Fix .env file** (5 min)

Open `.env` and remove ALL spaces around `=`:

```bash
# Before (BROKEN):
GROQ_API_KEY = gsk_...

# After (FIXED):
GROQ_API_KEY=gsk_...
```

Also add:
```bash
ENABLE_API_LIVENESS_PROBES=false
```

**Step 3.2: Fix Cerebras model** (5 min)

In `src\llm\client.py`, line ~580:

```python
# Change from:
"model": "llama3.1-8b"

# To:
"model": self.CEREBRAS_MODEL
```

**Step 3.3: Add connection pool** (20 min)

In `src\orchestration\debate.py`, add at top (after imports):

```python
import sqlite3
from pathlib import Path

# Global connection pool
_db_connection = None

def get_db_connection():
    global _db_connection
    if _db_connection is None:
        _db_connection = sqlite3.connect(
            "insightswarm_graph.db",
            check_same_thread=False,
            timeout=10.0
        )
    return _db_connection
```

Then in `__init__`, change:

```python
# From:
self.conn = sqlite3.connect("insightswarm_graph.db", check_same_thread=False)

# To:
self.conn = get_db_connection()
```

**Step 3.4: Test fixes** (30 min)

```bash
# Run diagnostics again
python tests\diagnostics\system_diagnostics.py

# Compare with earlier results
# Startup should be faster now
```

---

### **LUNCH BREAK (12:00 PM - 1:00 PM)**

---

### **Hour 4: Enhanced UI Feedback (1:00 PM - 2:00 PM)**

**Make the UI show what's happening**

**Step 4.1: Create progress tracker** (30 min)

Save as `src\ui\progress.py`:

```python
"""
Simple progress tracker for UI
"""

import time
from dataclasses import dataclass

@dataclass
class Progress:
    stage: str
    message: str
    percent: float
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class ProgressTracker:
    def __init__(self):
        self.updates = []
        self.start_time = time.time()
    
    def update(self, stage: str, message: str, percent: float):
        """Add progress update"""
        progress = Progress(stage, message, percent)
        self.updates.append(progress)
        
        # Log it
        from src.utils.simple_logger import get_logger
        logger = get_logger()
        logger.info(f"[{stage}] {percent:.0f}% - {message}")
    
    def get_latest(self):
        """Get most recent update"""
        return self.updates[-1] if self.updates else None
    
    def get_elapsed(self):
        """Get elapsed time"""
        return time.time() - self.start_time
```

**Step 4.2: Integrate with orchestrator** (30 min)

In `src\orchestration\debate.py`, add progress tracking:

```python
def run(self, claim: str, thread_id: str = "default"):
    from src.ui.progress import ProgressTracker
    from src.utils.simple_logger import get_logger
    
    logger = get_logger()
    tracker = ProgressTracker()
    
    tracker.update("INIT", "Initializing debate system", 0.0)
    logger.info(f"🔍 Starting debate: '{claim}'")
    
    # ... existing cache check ...
    
    tracker.update("SEARCH", "Searching for evidence", 0.1)
    
    # ... existing evidence retrieval ...
    
    tracker.update("ROUND1", "Round 1: ProAgent arguing", 0.3)
    
    # Store tracker in state for agents to use
    initial_state.metadata = {"tracker": tracker}
    
    # ... rest of method ...
```

---

### **Hour 5: Memory Profiling (2:00 PM - 3:00 PM)**

**Understand where memory is going**

**Step 5.1: Create memory profiler** (30 min)

Save as `tests\diagnostics\memory_profile.py`:

```python
"""
Memory profiling to find leaks
"""

import psutil
import os
import gc
from src.orchestration.debate import DebateOrchestrator

def profile_memory():
    process = psutil.Process(os.getpid())
    
    print("Memory Profile Test")
    print("=" * 70)
    
    readings = []
    
    # Baseline
    gc.collect()
    baseline = process.memory_info().rss / 1024 / 1024
    print(f"Baseline: {baseline:.1f}MB")
    readings.append(("Baseline", baseline))
    
    # Create orchestrator
    orch = DebateOrchestrator()
    mem = process.memory_info().rss / 1024 / 1024
    print(f"After init: {mem:.1f}MB (+{mem - baseline:.1f}MB)")
    readings.append(("Init", mem))
    
    # Run 5 claims
    claims = [
        "Coffee is healthy",
        "Exercise prevents disease",
        "Water is H2O",
        "The Earth is round",
        "Smoking causes cancer"
    ]
    
    for i, claim in enumerate(claims, 1):
        result = orch.run(claim)
        gc.collect()
        mem = process.memory_info().rss / 1024 / 1024
        print(f"After claim {i}: {mem:.1f}MB (+{mem - baseline:.1f}MB)")
        readings.append((f"Claim {i}", mem))
    
    print("\n" + "=" * 70)
    print("Analysis:")
    
    growth_per_claim = (readings[-1][1] - readings[1][1]) / 5
    print(f"Average growth per claim: {growth_per_claim:.1f}MB")
    
    if growth_per_claim > 20:
        print("❌ LEAK DETECTED: >20MB per claim")
    else:
        print("✅ No significant leak detected")

if __name__ == "__main__":
    profile_memory()
```

**Step 5.2: Run profiler** (30 min)

```bash
python tests\diagnostics\memory_profile.py
```

Save the output. If you see growth >20MB per claim, that's a leak.

---

### **Hour 6: Document & Plan Tomorrow (3:00 PM - 4:00 PM)**

**Step 6.1: Create progress report** (30 min)

Create `DAY1_REPORT.md`:

```markdown
# Day 1 Progress Report

Date: [Today's date]

## What We Accomplished

1. ✅ Set up diagnostic infrastructure
2. ✅ Identified specific bottlenecks
3. ✅ Added observable logging
4. ✅ Fixed critical environment issues
5. ✅ Measured memory baseline

## Key Findings

### Performance Issues
- [List issues from diagnostics]

### Memory Issues
- [List from memory profile]

### API Issues
- [List from testing]

## Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Startup Time | Xs | Ys | <2s |
| Memory Usage | XMB | YMB | <500MB |
| API Keys Working | X/4 | Y/4 | 4/4 |

## Tomorrow's Plan

1. [Top priority issue from today]
2. [Second priority]
3. [Third priority]

## Blockers

[Any issues preventing progress]
```

**Step 6.2: Plan tomorrow** (30 min)

Based on what you found today, prioritize tomorrow's work:

1. If APIs not working → Fix API key loading
2. If slow startup → Implement lazy initialization
3. If memory leak → Add resource limits
4. If UI freezing → Start async implementation

---

## 📊 END OF DAY CHECKLIST

- [ ] Diagnostics run and saved
- [ ] Observable logging implemented
- [ ] Quick fixes applied (.env, model, connection pool)
- [ ] Memory profile completed
- [ ] Progress report written
- [ ] Tomorrow's priorities set

---

## 🎯 SUCCESS CRITERIA FOR DAY 1

You should now have:

1. ✅ **Concrete data** about what's broken (not guesses)
2. ✅ **Visibility** into system behavior (logging)
3. ✅ **Baseline metrics** to measure improvement
4. ✅ **Quick wins** applied (faster startup, less leaking)
5. ✅ **Clear plan** for tomorrow

---

## 📝 NOTES

### If Diagnostics Show:

**"API Keys Not Loading":**
- Double-check .env file has NO spaces around `=`
- Verify file is in project root
- Check env vars loaded: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GROQ_API_KEY'))"`

**"Slow Startup (>5s)":**
- Check `ENABLE_API_LIVENESS_PROBES=false` in .env
- If still slow, liveness probes might be hardcoded somewhere

**"Memory Leak":**
- Tomorrow priority: Implement bounded caches
- Add resource limits
- Profile with tracemalloc for details

**"Providers Not Available":**
- Check API keys are valid
- Test with curl/requests directly
- May be quota exhausted

---

## 🚀 READY FOR DAY 2

Tomorrow you'll build on today's foundation:
- Circuit breakers for reliability
- Fallback strategies
- Resource limits
- Better UI feedback

**Good work! You now have REAL DATA about your system instead of guessing.** 🎉
