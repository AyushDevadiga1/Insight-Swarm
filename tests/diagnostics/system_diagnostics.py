#!/usr/bin/env python3
"""
System Diagnostics - Run this FIRST to understand what's broken.
Covers: API keys, client init speed, memory leak, orchestrator perf, live provider test.

Usage:
    python tests/diagnostics/system_diagnostics.py
"""

import os
import sys
import time
import gc
import tracemalloc
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class SystemDiagnostics:
    """Comprehensive system health and performance diagnostics."""

    def __init__(self):
        try:
            import psutil
            self._proc = psutil.Process(os.getpid())
            self._has_psutil = True
        except ImportError:
            self._has_psutil = False
        self.results: dict = {}
        self.issues: list = []

    # ── helpers ──────────────────────────────────────────────────────────────

    def _mem_mb(self) -> float:
        if self._has_psutil:
            return self._proc.memory_info().rss / 1024 / 1024
        return 0.0

    def _sep(self, title: str) -> None:
        print(f"\n{'─'*70}")
        print(f"  {title}")
        print(f"{'─'*70}")

    # ── tests ─────────────────────────────────────────────────────────────────

    def test_environment(self) -> None:
        self._sep("Test 0: Environment")
        print(f"Python  : {sys.version.split()[0]}")
        print(f"CWD     : {os.getcwd()}")
        if self._has_psutil:
            import psutil
            ram_gb = psutil.virtual_memory().available / 1024**3
            print(f"Free RAM: {ram_gb:.1f} GB")
        else:
            print("psutil  : not installed (pip install psutil for memory info)")

    def test_api_keys(self) -> None:
        self._sep("Test 1: API Key Validation")
        from dotenv import load_dotenv
        load_dotenv()

        key_specs = {
            "GROQ_API_KEY":       ("gsk_",   30),
            "CEREBRAS_API_KEY":   ("csk-",   30),
            "OPENROUTER_API_KEY": ("sk-or-", 30),
            "TAVILY_API_KEY":     ("tvly-",  20),
            "GEMINI_API_KEY":     ("AIza",   20),
        }

        for key_name, (prefix, min_len) in key_specs.items():
            value = os.getenv(key_name, "")
            if not value:
                print(f"  ❌  {key_name:25}: MISSING")
                self.issues.append(f"Missing key: {key_name}")
                self.results[key_name] = "MISSING"
            elif not value.startswith(prefix):
                print(f"  ❌  {key_name:25}: WRONG FORMAT (expected '{prefix}...')")
                self.issues.append(f"Bad format: {key_name}")
                self.results[key_name] = "BAD_FORMAT"
            elif len(value) < min_len:
                print(f"  ⚠️   {key_name:25}: TOO SHORT ({len(value)} chars)")
                self.issues.append(f"Short key: {key_name}")
                self.results[key_name] = "SHORT"
            else:
                print(f"  ✅  {key_name:25}: OK ({len(value)} chars, {value[:12]}...)")
                self.results[key_name] = "OK"

    def test_imports(self) -> None:
        self._sep("Test 2: Critical Imports")
        modules = ["groq", "google.generativeai", "langgraph", "pydantic",
                   "streamlit", "requests", "dotenv", "sentence_transformers"]
        for mod in modules:
            try:
                __import__(mod)
                print(f"  ✅  {mod}")
            except ImportError as exc:
                print(f"  ❌  {mod}: {exc}")
                self.issues.append(f"Missing import: {mod}")

    def test_client_speed(self) -> None:
        self._sep("Test 3: LLM Client Init Speed")
        try:
            from src.llm.client import FreeLLMClient

            tracemalloc.start()
            mb_before = self._mem_mb()
            t0 = time.time()
            client = FreeLLMClient()
            elapsed = time.time() - t0
            mb_after = self._mem_mb()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            print(f"  Time   : {elapsed:.2f}s")
            print(f"  RSS Δ  : +{mb_after - mb_before:.1f} MB")
            print(f"  Peak   : {peak / 1024 / 1024:.1f} MB")
            print(f"  Groq   : {'✅' if client.groq_available else '❌'}")
            print(f"  Gemini : {'✅' if client.gemini_available else '❌'}")
            print(f"  Cerebras: {'✅' if client.cerebras_available else '❌'}")
            print(f"  OpenRouter: {'✅' if client.openrouter_available else '❌'}")

            if elapsed > 5.0:
                print(f"\n  ⚠️  SLOW ({elapsed:.1f}s) — check ENABLE_API_LIVENESS_PROBES=false in .env")
                self.results["client_init"] = "SLOW"
                self.issues.append("Slow client init (>5s)")
            else:
                print(f"\n  ✅  Fast init ({elapsed:.2f}s)")
                self.results["client_init"] = "OK"
        except Exception as exc:
            print(f"  ❌  FAILED: {exc}")
            self.results["client_init"] = "FAIL"
            self.issues.append(f"Client init failed: {exc}")

    def test_memory_leak(self) -> None:
        self._sep("Test 4: Memory Leak Detection (5 client inits)")
        try:
            from src.llm.client import FreeLLMClient
            readings = []
            for i in range(5):
                gc.collect()
                client = FreeLLMClient()
                readings.append(self._mem_mb())
                del client

            growth = readings[-1] - readings[0]
            print(f"  Readings: {[f'{r:.0f}MB' for r in readings]}")
            print(f"  Growth  : {growth:+.1f} MB over 5 iterations")

            if growth > 50:
                print(f"  ❌  LEAK DETECTED (>{growth:.0f}MB growth)")
                self.results["memory_leak"] = "FAIL"
                self.issues.append(f"Memory leak: +{growth:.0f}MB")
            else:
                print(f"  ✅  No significant leak")
                self.results["memory_leak"] = "OK"
        except Exception as exc:
            print(f"  ❌  FAILED: {exc}")
            self.results["memory_leak"] = "FAIL"

    def test_orchestrator(self) -> None:
        self._sep("Test 5: Orchestrator Init + Simple Claim")
        try:
            from src.orchestration.debate import DebateOrchestrator

            t0 = time.time()
            orch = DebateOrchestrator()
            init_time = time.time() - t0
            print(f"  Init time: {init_time:.2f}s")

            if init_time > 10:
                print(f"  ❌  CRITICAL: init >10s")
                self.results["orch_init"] = "SLOW"
                self.issues.append("Orchestrator init >10s")
            else:
                print(f"  ✅  Init OK")
                self.results["orch_init"] = "OK"

            print("  Running 'The Earth is round'...")
            t0 = time.time()
            result = orch.run("The Earth is round")
            run_time = time.time() - t0
            print(f"  Verdict : {getattr(result, 'verdict', result)}")
            print(f"  Run time: {run_time:.1f}s")

            if run_time > 90:
                self.results["orch_run"] = "SLOW"
                self.issues.append(f"Claim took {run_time:.0f}s")
            else:
                self.results["orch_run"] = "OK"

        except Exception as exc:
            print(f"  ❌  FAILED: {exc}")
            self.results["orch_init"] = "FAIL"
            self.results["orch_run"] = "FAIL"
            self.issues.append(f"Orchestrator failed: {exc}")

    def test_api_live(self) -> None:
        self._sep("Test 6: Live API Provider Smoke Test")
        try:
            from src.llm.client import FreeLLMClient
            client = FreeLLMClient()
            providers = []
            if client.groq_available:       providers.append("groq")
            if client.cerebras_available:   providers.append("cerebras")
            if client.openrouter_available: providers.append("openrouter")

            for p in providers:
                try:
                    t0 = time.time()
                    resp = client.call("Say only the word: OK",
                                      max_tokens=15,
                                      preferred_provider=p,
                                      timeout=15)
                    elapsed = time.time() - t0
                    snippet = str(resp)[:30].strip()
                    print(f"  ✅  {p:12}: {elapsed:.2f}s → '{snippet}'")
                    self.results[f"live_{p}"] = "OK"
                except Exception as exc:
                    print(f"  ❌  {p:12}: {str(exc)[:60]}")
                    self.results[f"live_{p}"] = "FAIL"
                    self.issues.append(f"Live call failed ({p}): {exc}")
        except Exception as exc:
            print(f"  ❌  Could not run live test: {exc}")

    # ── summary ───────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        print(f"\n{'='*70}")
        print("  DIAGNOSTIC SUMMARY")
        print(f"{'='*70}")

        ok   = sum(1 for v in self.results.values() if v == "OK")
        fail = sum(1 for v in self.results.values() if v == "FAIL")
        slow = sum(1 for v in self.results.values() if v == "SLOW")

        print(f"\n  ✅  Passed : {ok}")
        print(f"  ❌  Failed : {fail}")
        print(f"  ⚠️   Slow   : {slow}")

        if self.issues:
            print(f"\n  Issues found ({len(self.issues)}):")
            for i, iss in enumerate(self.issues, 1):
                print(f"    {i}. {iss}")
        else:
            print("\n  🎉 No issues found!")

        print(f"\n{'='*70}\n")

    def run(self, skip_live=False, skip_orchestrator=False) -> dict:
        print("\n" + "="*70)
        print("  🔍 INSIGHTSWARM SYSTEM DIAGNOSTICS")
        print("="*70)

        self.test_environment()
        self.test_api_keys()
        self.test_imports()
        self.test_client_speed()
        self.test_memory_leak()

        if not skip_orchestrator:
            self.test_orchestrator()
        if not skip_live:
            self.test_api_live()

        self.print_summary()
        return self.results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="InsightSwarm System Diagnostics")
    parser.add_argument("--skip-live",         action="store_true", help="Skip live API calls")
    parser.add_argument("--skip-orchestrator", action="store_true", help="Skip orchestrator test")
    args = parser.parse_args()

    diag = SystemDiagnostics()
    results = diag.run(skip_live=args.skip_live, skip_orchestrator=args.skip_orchestrator)

    failed = sum(1 for v in results.values() if v == "FAIL")
    sys.exit(0 if failed == 0 else 1)
