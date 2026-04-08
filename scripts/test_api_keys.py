#!/usr/bin/env python3
"""
scripts/test_api_keys.py  —  InsightSwarm API Key Health Report
================================================================
REALISTIC rate-limit-aware provider test suite.

RESEARCH-BACKED LIMITS (April 2026):
  Groq  llama-3.3-70b-versatile   Free tier: 30 RPM, 14 400 RPD, 6 000 TPM
  Gemini 2.5 Flash                Free tier:  10 RPM,    250 RPD, 250 000 TPM
         (gemini-2.0-flash RETIRED March 3 2026 — do NOT use)
  Gemini 2.5 Flash-Lite           Free tier:  15 RPM,  1 000 RPD
  Cerebras llama3.1-8b            Free tier: ~30 RPM (similar to Groq)
  OpenRouter (free models)        Free tier: ~20 RPM, varies by model
  Tavily                          Free tier:  1 000 searches/month (~33/day)

DESIGN PHILOSOPHY:
  • ONE API call per provider (ping only) — no wasted quota from duplicate tests
  • Structured-output test is SKIPPED by default; use --structured to enable it
    (costs 1 extra call per LLM provider — use sparingly on Gemini/Tavily)
  • Rate-limit headers (x-ratelimit-remaining-*) are read when available
  • Keys can be valid format but exhausted/revoked — we distinguish gracefully
  • Smoke test costs ~2–4 Groq calls (consensus check, debate skipped on settled claims)

Usage:
    python scripts/test_api_keys.py                   # ping all providers
    python scripts/test_api_keys.py --format-only      # no API calls
    python scripts/test_api_keys.py --providers groq,gemini
    python scripts/test_api_keys.py --structured       # +1 call per LLM provider
    python scripts/test_api_keys.py --smoke-test       # +consensus debate call
    python scripts/test_api_keys.py --verbose          # show raw responses & headers

Exit codes:
    0  all required providers passed
    1  at least one required provider failed
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.ERROR)
for noisy in ("httpx", "groq", "google", "urllib3", "requests"):
    logging.getLogger(noisy).setLevel(logging.ERROR)


# ── ANSI colour helpers ───────────────────────────────────────────────────────

class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

def _ok(msg):   return f"{C.GREEN}✓{C.RESET} {msg}"
def _warn(msg): return f"{C.YELLOW}⚠{C.RESET} {msg}"
def _fail(msg): return f"{C.RED}✗{C.RESET} {msg}"
def _info(msg): return f"{C.CYAN}·{C.RESET} {msg}"


# ── Provider registry ─────────────────────────────────────────────────────────
# Accurate free-tier limits as of April 2026 (post Dec-2025 Gemini cuts)

PROVIDERS = {
    "groq": {
        "env_var":    "GROQ_API_KEY",
        "prefix":     "gsk_",
        "min_length": 50,
        "required":   True,
        "used_by":    ["ProAgent", "FactChecker"],
        "rpm_limit":  30,
        "rpd_limit":  14_400,
        "tpm_limit":  6_000,
        "note":       "30 RPM / 14 400 RPD / 6 000 TPM (llama-3.3-70b-versatile)",
    },
    "gemini": {
        "env_var":    "GEMINI_API_KEY",
        "prefix":     "AIza",
        "min_length": 35,
        "required":   False,
        "used_by":    ["ConAgent", "Moderator", "ConsensusCheck"],
        "rpm_limit":  10,
        "rpd_limit":  250,
        "tpm_limit":  250_000,
        "note":       "10 RPM / 250 RPD (gemini-2.5-flash; 2.0-flash RETIRED March 2026)",
    },
    "cerebras": {
        "env_var":    "CEREBRAS_API_KEY",
        "prefix":     "csk-",
        "min_length": 30,
        "required":   False,
        "used_by":    ["ProAgent (optional)"],
        "rpm_limit":  30,
        "rpd_limit":  None,  # not publicly documented
        "tpm_limit":  None,
        "note":       "~30 RPM (llama3.1-8b, fast inference)",
    },
    "openrouter": {
        "env_var":    "OPENROUTER_API_KEY",
        "prefix":     "sk-or-",
        "min_length": 60,
        "required":   False,
        "used_by":    ["ConAgent (alternative)", "Moderator (alternative)"],
        "rpm_limit":  20,
        "rpd_limit":  None,
        "tpm_limit":  None,
        "note":       "~20 RPM (varies by model; free tier on select models)",
    },
    "tavily": {
        "env_var":    "TAVILY_API_KEY",
        "prefix":     None,
        "min_length": 20,
        "required":   False,
        "used_by":    ["Evidence retrieval"],
        "rpm_limit":  None,
        "rpd_limit":  33,    # ~1 000/month ÷ 30 days
        "tpm_limit":  None,
        "note":       "1 000 searches/month free (~33/day)",
    },
}


# ── Per-provider ping functions (1 call each) ─────────────────────────────────

def _ping_groq(key: str, verbose: bool) -> Tuple[bool, float, str, dict]:
    """
    Single tiny call to Groq. Reads remaining-request headers when present.
    Returns (success, latency_s, detail, quota_headers).
    """
    try:
        from groq import Groq
        client = Groq(api_key=key)
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with one word: PONG"}],
            max_tokens=4,
            temperature=0.0,
        )
        latency = time.perf_counter() - t0
        text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        if verbose:
            print(f"     raw: {text!r}")
        # Groq exposes headers via resp.model_extra or the raw response object
        headers = {}
        if hasattr(resp, "_raw_response") and hasattr(resp._raw_response, "headers"):
            h = resp._raw_response.headers
            for k in ("x-ratelimit-remaining-requests", "x-ratelimit-reset-requests",
                       "x-ratelimit-remaining-tokens"):
                if k in h:
                    headers[k] = h[k]
        return bool(text), latency, text[:40] or "empty", headers
    except Exception as e:
        err = str(e)
        # Distinguish expired/invalid key from rate limit
        if "401" in err or "invalid_api_key" in err.lower() or "authentication" in err.lower():
            return False, 0.0, "AUTH_FAILED: key invalid or revoked", {}
        if "429" in err or "rate" in err.lower() or "quota" in err.lower():
            return False, 0.0, f"RATE_LIMITED: {err[:80]}", {}
        return False, 0.0, err[:100], {}


def _ping_gemini(key: str, verbose: bool) -> Tuple[bool, float, str, dict]:
    """
    Single call to Gemini 2.5 Flash (NOT 2.0 Flash — retired March 2026).
    Free tier: 10 RPM, 250 RPD. Fails immediately on invalid key.
    """
    try:
        from google import genai
        from google.genai import types as gt
        client = genai.Client(api_key=key)
        t0 = time.perf_counter()
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Reply with one word: PONG",
            config=gt.GenerateContentConfig(max_output_tokens=4, temperature=0.0),
        )
        latency = time.perf_counter() - t0
        text = (resp.text or "").strip()
        if verbose:
            print(f"     raw: {text!r}")
        return bool(text), latency, text[:40] or "empty", {}
    except Exception as e:
        err = str(e)
        if "401" in err or "API_KEY_INVALID" in err or "invalid" in err.lower():
            return False, 0.0, "AUTH_FAILED: key invalid or revoked", {}
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            return False, 0.0, "RATE_LIMITED / QUOTA_EXHAUSTED (250 RPD free tier)", {}
        if "deprecated" in err.lower() or "not found" in err.lower():
            return False, 0.0, "MODEL_ERROR: check model name (2.0-flash retired)", {}
        return False, 0.0, err[:100], {}


def _ping_cerebras(key: str, verbose: bool) -> Tuple[bool, float, str, dict]:
    try:
        import requests as _req
        t0 = time.perf_counter()
        r = _req.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "llama3.1-8b",
                  "messages": [{"role": "user", "content": "Reply with one word: PONG"}],
                  "max_tokens": 4, "temperature": 0.0},
            timeout=15,
        )
        latency = time.perf_counter() - t0
        if r.status_code == 401:
            return False, latency, "AUTH_FAILED: key invalid or revoked", {}
        if r.status_code == 429:
            return False, latency, "RATE_LIMITED (30 RPM free tier)", {}
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        if verbose:
            print(f"     raw: {text!r}")
        return bool(text), latency, text[:40], {}
    except Exception as e:
        err = str(e)
        return False, 0.0, err[:100], {}


def _ping_openrouter(key: str, verbose: bool) -> Tuple[bool, float, str, dict]:
    try:
        import requests as _req
        t0 = time.perf_counter()
        r = _req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://insightswarm.ai", "X-Title": "InsightSwarm-Test"},
            json={"model": "meta-llama/llama-3.1-8b-instruct",
                  "messages": [{"role": "user", "content": "Reply with one word: PONG"}],
                  "max_tokens": 4, "temperature": 0.0},
            timeout=20,
        )
        latency = time.perf_counter() - t0
        if r.status_code == 401:
            return False, latency, "AUTH_FAILED: key invalid or revoked", {}
        if r.status_code == 402:
            return False, latency, "PAYMENT_REQUIRED: add credits to OpenRouter account", {}
        if r.status_code == 429:
            return False, latency, "RATE_LIMITED (~20 RPM)", {}
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        if verbose:
            print(f"     raw: {text!r}")
        return bool(text), latency, text[:40], {}
    except Exception as e:
        return False, 0.0, str(e)[:100], {}


def _ping_tavily(key: str, verbose: bool) -> Tuple[bool, float, str, dict]:
    """
    Tavily: 1 000 searches/month free. This costs 1 search — use sparingly.
    """
    try:
        import requests as _req
        t0 = time.perf_counter()
        r = _req.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": key, "query": "InsightSwarm health check", "max_results": 1},
            timeout=10,
        )
        latency = time.perf_counter() - t0
        if r.status_code == 401:
            return False, latency, "AUTH_FAILED: key invalid or revoked", {}
        if r.status_code == 429:
            return False, latency, "QUOTA_EXHAUSTED: 1 000/month free tier limit hit", {}
        r.raise_for_status()
        data = r.json()
        n = len(data.get("results", []))
        detail = f"{n} result(s) returned"
        if verbose:
            print(f"     keys: {list(data.keys())}")
        return True, latency, detail, {}
    except Exception as e:
        return False, 0.0, str(e)[:100], {}


PING_FNS = {
    "groq":       _ping_groq,
    "gemini":     _ping_gemini,
    "cerebras":   _ping_cerebras,
    "openrouter": _ping_openrouter,
    "tavily":     _ping_tavily,
}


# ── Optional structured-output test (costs 1 extra call per LLM) ─────────────

def _test_structured_output(provider: str, verbose: bool) -> Tuple[bool, str]:
    """
    Tests that call_structured returns a valid Pydantic object.
    Costs 1 API call. Only run when --structured flag is passed.
    """
    try:
        from pydantic import BaseModel
        from src.llm.client import FreeLLMClient

        class _Schema(BaseModel):
            answer: str
            confidence: float

        client = FreeLLMClient()
        result = client.call_structured(
            prompt='Return JSON only: {"answer": "PONG", "confidence": 1.0}',
            output_schema=_Schema,
            temperature=0.0,
            max_tokens=40,
            preferred_provider=provider,
        )
        msg = f"answer={result.answer!r}  confidence={result.confidence}"
        if verbose:
            print(f"     structured: {msg}")
        return True, msg
    except Exception as e:
        return False, str(e)[:120]


# ── Optional smoke test ───────────────────────────────────────────────────────

def _run_smoke_test(verbose: bool) -> bool:
    """
    Run a single consensus-shortcut claim (Earth is round → TRUE without full debate).
    Costs ~1–2 Groq calls (consensus check only, debate skipped).
    """
    print(f"\n{C.BOLD}{'─'*60}{C.RESET}")
    print(f"{C.BOLD}🧪  Smoke Test — Consensus shortcut{C.RESET}")
    print(f"    Claim: \"The Earth is round\"")
    print(f"    Expected: TRUE, confidence ≥ 0.90, is_cached=False (first run)\n")
    try:
        from src.orchestration.debate import DebateOrchestrator
        orch = DebateOrchestrator()
        t0   = time.perf_counter()
        result = orch.run("The Earth is round")
        elapsed = time.perf_counter() - t0
        orch.close()

        v, c, cached = result.verdict, result.confidence, result.is_cached
        if v == "TRUE" and c >= 0.9:
            print(_ok(f"Verdict={v}  conf={c:.0%}  "
                      f"{'(cached)' if cached else f'({elapsed:.1f}s)'}"))
            return True
        else:
            print(_fail(f"Unexpected verdict={v}  conf={c:.0%}"))
            return False
    except Exception as e:
        print(_fail(f"Smoke test crashed: {e}"))
        if verbose:
            import traceback; traceback.print_exc()
        return False


# ── Per-provider test orchestrator ────────────────────────────────────────────

def test_provider(
    name: str,
    cfg: dict,
    format_only: bool,
    run_structured: bool,
    verbose: bool,
) -> dict:
    result = {
        "name":          name,
        "required":      cfg["required"],
        "used_by":       cfg["used_by"],
        "note":          cfg["note"],
        "key_found":     False,
        "format_ok":     False,
        "ping_ok":       False,
        "structured_ok": None,   # None = not tested
        "latency_ms":    None,
        "quota_headers": {},
        "detail":        "",
        "overall":       "SKIP",
    }

    # ── Step 1: key present ───────────────────────────────────────────────────
    key = os.getenv(cfg["env_var"], "").strip().strip("\"'")
    if not key:
        result["detail"]  = f"{cfg['env_var']} not set in .env"
        result["overall"] = "MISSING"
        return result
    result["key_found"] = True

    # ── Step 2: format check ──────────────────────────────────────────────────
    prefix  = cfg.get("prefix")
    min_len = cfg["min_length"]
    if len(key) < min_len or (prefix and not key.startswith(prefix)):
        result["detail"]  = (
            f"Bad format: len={len(key)} (min {min_len}), "
            f"prefix={key[:8]!r} (expected {prefix!r})"
        )
        result["overall"] = "BAD_FORMAT"
        return result
    result["format_ok"] = True

    if format_only:
        result["overall"] = "FORMAT_OK"
        return result

    # ── Step 3: live ping (1 call) ────────────────────────────────────────────
    print(f"  {C.DIM}pinging {name}…{C.RESET}", end=" ", flush=True)
    ping_fn = PING_FNS[name]
    success, latency, detail, quota_hdrs = ping_fn(key, verbose)

    result["latency_ms"]    = round(latency * 1000, 1)
    result["detail"]        = detail
    result["quota_headers"] = quota_hdrs

    if success:
        result["ping_ok"] = True
        hdr_str = ""
        if quota_hdrs:
            rem = quota_hdrs.get("x-ratelimit-remaining-requests", "?")
            hdr_str = f"  [remaining-req: {rem}]"
        print(_ok(f"{latency*1000:.0f}ms  →  {detail}{hdr_str}"))
    else:
        print(_fail(detail))
        result["overall"] = "PING_FAILED"
        return result

    # ── Step 4: structured output (optional, LLM only) ───────────────────────
    if run_structured and name != "tavily":
        print(f"  {C.DIM}structured output…{C.RESET}", end=" ", flush=True)
        s_ok, s_detail = _test_structured_output(name, verbose)
        result["structured_ok"] = s_ok
        if s_ok:
            print(_ok(s_detail))
        else:
            print(_warn(f"PARTIAL: {s_detail}"))
    else:
        result["structured_ok"] = True  # not tested / N/A

    result["overall"] = (
        "PASS" if (result["ping_ok"] and result["structured_ok"]) else "PARTIAL"
    )
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="InsightSwarm API Key Health Report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--providers",   type=str, default=None,
                        help="Comma-separated providers (default: all)")
    parser.add_argument("--format-only", action="store_true",
                        help="Key format check only — no API calls")
    parser.add_argument("--structured",  action="store_true",
                        help="Also run structured-output test (+1 call per LLM)")
    parser.add_argument("--smoke-test",  action="store_true",
                        help="Run consensus smoke test at the end (+1–2 Groq calls)")
    parser.add_argument("--verbose",     action="store_true",
                        help="Show raw API responses and quota headers")
    args = parser.parse_args()

    chosen = (
        [p.strip() for p in args.providers.split(",")]
        if args.providers
        else list(PROVIDERS.keys())
    )

    print(f"\n{C.BOLD}{'═'*62}{C.RESET}")
    print(f"{C.BOLD}🦅  InsightSwarm — API Key Health Report  (April 2026){C.RESET}")
    print(f"    Mode: {'format-only' if args.format_only else 'live ping'}"
          f"{' + structured' if args.structured else ''}")
    print(f"    Providers: {', '.join(chosen)}")
    print(f"\n    Free-tier budget notes:")
    print(f"      Groq   30 RPM / 14 400 RPD / 6 000 TPM")
    print(f"      Gemini  10 RPM /     250 RPD (2.5-flash, post-Dec-2025)")
    print(f"      Tavily  ~33 searches/day  (1 000/month)")
    print(f"{'═'*62}{C.RESET}\n")

    results: List[dict] = []

    for name in chosen:
        if name not in PROVIDERS:
            print(_warn(f"Unknown provider '{name}' — skipping"))
            continue
        cfg = PROVIDERS[name]
        req_label = f"{C.YELLOW}(required){C.RESET}" if cfg["required"] else f"{C.DIM}(optional){C.RESET}"
        print(f"{C.BOLD}▸ {name.upper()}{C.RESET}  {req_label}  "
              f"{C.DIM}{', '.join(cfg['used_by'])}{C.RESET}")

        r = test_provider(name, cfg, args.format_only, args.structured, args.verbose)
        results.append(r)

        overall = r["overall"]
        if overall == "PASS":
            print(_ok(f"All checks passed  [{r['latency_ms']}ms]\n"))
        elif overall == "FORMAT_OK":
            print(_ok("Key format valid (ping skipped)\n"))
        elif overall == "MISSING":
            lbl = _fail if cfg["required"] else _warn
            print(lbl(f"{r['detail']}\n"))
        elif overall == "PARTIAL":
            print(_warn(f"Ping OK but structured output failed\n"))
        elif overall == "BAD_FORMAT":
            print(_fail(f"Bad key format: {r['detail']}\n"))
        else:
            lbl = _fail if cfg["required"] else _warn
            print(lbl(f"{r['detail']}\n"))

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{C.BOLD}{'─'*62}")
    print(f"  SUMMARY{C.RESET}")
    print(f"{'─'*62}")
    header = f"  {'Provider':<13} {'Status':<16} {'Latency':>8}  {'Note'}"
    print(header)
    print(f"  {'─'*11} {'─'*14} {'─'*8}  {'─'*28}")

    any_required_failed = False
    for r in results:
        status  = r["overall"]
        latency = f"{r['latency_ms']}ms" if r["latency_ms"] else "—"
        colour  = (C.GREEN  if status in ("PASS", "FORMAT_OK") else
                   C.YELLOW if status in ("PARTIAL", "MISSING") and not r["required"] else
                   C.RED)
        req_star = " *" if r["required"] else ""
        note_short = r["note"][:35]
        print(f"  {colour}{r['name']:<13} {status:<16}{C.RESET} {latency:>8}  {note_short}{req_star}")
        if status not in ("PASS", "FORMAT_OK", "PARTIAL") and r["required"]:
            any_required_failed = True

    print(f"\n  * = required for system to function")

    # ── Quota notes ───────────────────────────────────────────────────────────
    quota_warnings = []
    for r in results:
        if r.get("quota_headers"):
            rem = r["quota_headers"].get("x-ratelimit-remaining-requests")
            if rem is not None:
                try:
                    if int(rem) < 100:
                        quota_warnings.append(
                            f"  ⚠  {r['name']}: only {rem} requests remaining today"
                        )
                except ValueError:
                    pass
    if quota_warnings:
        print(f"\n{C.YELLOW}Quota Warnings:{C.RESET}")
        for w in quota_warnings:
            print(w)

    # ── Smoke test ────────────────────────────────────────────────────────────
    smoke_passed = True
    if args.smoke_test:
        smoke_passed = _run_smoke_test(args.verbose)

    # ── Final verdict ─────────────────────────────────────────────────────────
    print(f"\n{'═'*62}")
    if any_required_failed:
        print(f"{C.RED}{C.BOLD}  ❌  Required providers failed — system will not start.{C.RESET}")
        print(f"      Check .env and rerun.")
        print(f"{'═'*62}\n")
        sys.exit(1)
    elif not smoke_passed:
        print(f"{C.YELLOW}{C.BOLD}  ⚠   Keys OK but smoke test failed.{C.RESET}")
        print(f"{'═'*62}\n")
        sys.exit(1)
    else:
        print(f"{C.GREEN}{C.BOLD}  ✅  All required keys are healthy. System is ready.{C.RESET}")
        print(f"{'═'*62}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
