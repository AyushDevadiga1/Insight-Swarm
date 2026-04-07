#!/usr/bin/env python3
"""
scripts/test_api_keys.py  —  InsightSwarm API Key Robustness Test Suite
========================================================================
Researched free-tier limits (April 2026):

  GROQ (free tier)
  ─────────────────
  llama-3.3-70b-versatile : 30 RPM | 14 400 RPD | 6 000 TPM
  llama-3.1-8b-instant    : 30 RPM | 14 400 RPD | 6 000 TPM
  Note: TPM is the most common bottleneck with 70B models because
        one debate round ≈ 1 500-3 000 tokens in + out.

  GEMINI (free tier — after Dec 2025 cuts)
  ─────────────────────────────────────────
  gemini-2.0-flash     : 10 RPM | 1 500 RPD | 1 000 000 TPD
  gemini-2.5-flash     : 10 RPM |   250 RPD |   250 000 TPM
  gemini-2.5-flash-lite: 15 RPM | 1 000 RPD |   250 000 TPM
  gemini-2.5-pro       :  5 RPM |   100 RPD |   250 000 TPM
  Warning: limits are project-scoped, not per API key. Limits reset
  midnight Pacific time. Do NOT rotate keys to bypass — ToS violation.

  CEREBRAS (free tier)
  ─────────────────────
  All models: 30 RPM | 60 000 TPM | 1 000 000 TPD (tokens)
  Context window: 8 192 tokens on free tier (128K on paid)
  Speed: ~1 800 tok/s on Llama3.1-8b, ~450 tok/s on 70B

  OPENROUTER (free-tier models)
  ──────────────────────────────
  Free models rotate. Common limits: 10-20 RPM, 200 RPD per model.
  Credits required for non-free models. Budget $0 → free models only.

  TAVILY (free tier)
  ───────────────────
  1 000 searches/month (≈ 33/day). Searches are expensive — each
  InsightSwarm debate uses ~2 searches (pro + con evidence).
  That gives ≈ 500 full debates/month on the free tier.

Test strategy
─────────────
  1. Format-check — instant, no network
  2. Liveness ping — 1 tiny call, measures latency and detects:
       · Invalid key       (401 / 403)
       · Rate limit NOW    (429 — key may be exhausted)
       · Model unavailable (404 / 503)
  3. Structured output round-trip — real JSON schema call
  4. Token budget probe — sends a ~500-token prompt to check
     TPM headroom on the key
  5. InsightSwarm debate smoke test (optional, --smoke-test)

Usage
─────
  python scripts/test_api_keys.py               # all providers, live
  python scripts/test_api_keys.py --format-only # no network calls
  python scripts/test_api_keys.py --providers groq,gemini
  python scripts/test_api_keys.py --smoke-test  # + full debate
  python scripts/test_api_keys.py --verbose     # show raw responses
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
for noisy in ("httpx", "groq", "urllib3", "requests"):
    logging.getLogger(noisy).setLevel(logging.ERROR)


# ── ANSI colours ──────────────────────────────────────────────────────────────
class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

def ok(msg):   return f"{C.GREEN}✓{C.RESET}  {msg}"
def warn(msg): return f"{C.YELLOW}⚠{C.RESET}  {msg}"
def fail(msg): return f"{C.RED}✗{C.RESET}  {msg}"
def info(msg): return f"{C.CYAN}·{C.RESET}  {msg}"


# ── Provider meta ─────────────────────────────────────────────────────────────

PROVIDERS = {
    "groq": {
        "env_var":    "GROQ_API_KEY",
        "prefix":     "gsk_",
        "min_length": 30,
        "required":   True,
        "role":       "FactChecker + fallback for all agents",
        # Realistic free-tier budgets
        "rpm_limit":  30,
        "rpd_limit":  14_400,
        "tpm_limit":  6_000,
        "reset_desc": "TPM resets every 60 s; RPD at midnight UTC",
    },
    "gemini": {
        "env_var":    "GEMINI_API_KEY",
        "prefix":     "AIza",
        "min_length": 30,
        "required":   False,
        "role":       "ConAgent + Moderator + ConsensusCheck",
        "rpm_limit":  10,
        "rpd_limit":  250,       # gemini-2.5-flash (most conservative post-Dec-2025)
        "tpm_limit":  250_000,
        "reset_desc": "RPD resets midnight Pacific Time",
    },
    "cerebras": {
        "env_var":    "CEREBRAS_API_KEY",
        "prefix":     "csk-",
        "min_length": 30,
        "required":   False,
        "role":       "ProAgent (preferred, ultra-fast)",
        "rpm_limit":  30,
        "rpd_limit":  None,      # token-budget based (1M tok/day)
        "tpm_limit":  60_000,
        "reset_desc": "1 M tokens/day; TPM refills continuously",
    },
    "openrouter": {
        "env_var":    "OPENROUTER_API_KEY",
        "prefix":     "sk-or-",
        "min_length": 30,
        "required":   False,
        "role":       "ConAgent + Moderator (alternative route)",
        "rpm_limit":  10,        # conservative — free models vary
        "rpd_limit":  200,
        "tpm_limit":  None,
        "reset_desc": "Free-model limits rotate without notice",
    },
    "tavily": {
        "env_var":    "TAVILY_API_KEY",
        "prefix":     None,
        "min_length": 20,
        "required":   False,
        "role":       "Evidence retrieval (2 calls/debate)",
        "rpm_limit":  None,
        "rpd_limit":  33,        # ~1 000/month ÷ 30
        "tpm_limit":  None,
        "reset_desc": "1 000 searches/month reset on billing cycle",
    },
}


# ── Per-provider ping ─────────────────────────────────────────────────────────

TINY_PROMPT = "Reply with exactly one word: PONG"

def _ping_groq(key: str, verbose: bool) -> Tuple[bool, float, str, Optional[dict]]:
    try:
        from groq import Groq
        t0   = time.perf_counter()
        resp = Groq(api_key=key).chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": TINY_PROMPT}],
            max_tokens=8,
            temperature=0.0,
        )
        latency = time.perf_counter() - t0
        text    = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        # Extract rate-limit headers if available
        headers = {}
        if hasattr(resp, "_response") and hasattr(resp._response, "headers"):
            h = resp._response.headers
            headers = {
                "remaining_requests": h.get("x-ratelimit-remaining-requests"),
                "remaining_tokens":   h.get("x-ratelimit-remaining-tokens"),
                "reset_tokens":       h.get("x-ratelimit-reset-tokens"),
            }
        if verbose:
            print(f"     raw: {text!r}  headers: {headers}")
        return bool(text), latency, text[:40] or "empty", headers if headers else None
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower():
            return False, 0.0, f"RATE LIMITED — {msg[:80]}", None
        if "401" in msg or "invalid" in msg.lower():
            return False, 0.0, f"INVALID KEY — {msg[:80]}", None
        return False, 0.0, msg[:100], None


def _ping_gemini(key: str, verbose: bool) -> Tuple[bool, float, str, Optional[dict]]:
    try:
        from google import genai
        from google.genai import types as gt
        client  = genai.Client(api_key=key)
        t0      = time.perf_counter()
        resp    = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=TINY_PROMPT,
            config=gt.GenerateContentConfig(max_output_tokens=8, temperature=0.0),
        )
        latency = time.perf_counter() - t0
        text    = (resp.text or "").strip()
        if verbose:
            print(f"     raw: {text!r}")
        return bool(text), latency, text[:40] or "empty", None
    except Exception as e:
        msg = str(e)
        if "429" in msg or "quota" in msg.lower() or "resource_exhausted" in msg.lower():
            return False, 0.0, f"RATE LIMITED / QUOTA EXHAUSTED — {msg[:80]}", None
        if "401" in msg or "403" in msg or "api_key" in msg.lower():
            return False, 0.0, f"INVALID KEY — {msg[:80]}", None
        return False, 0.0, msg[:100], None


def _ping_cerebras(key: str, verbose: bool) -> Tuple[bool, float, str, Optional[dict]]:
    try:
        import requests as _req
        t0   = time.perf_counter()
        resp = _req.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama3.1-8b",
                "messages": [{"role": "user", "content": TINY_PROMPT}],
                "max_tokens": 8, "temperature": 0.0,
            },
            timeout=20,
        )
        latency = time.perf_counter() - t0
        headers = {}
        if hasattr(resp, "headers"):
            h = resp.headers
            headers = {
                "remaining_requests_day": h.get("x-ratelimit-remaining-requests-day"),
                "remaining_tokens_min":   h.get("x-ratelimit-remaining-tokens-minute"),
            }
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if verbose:
            print(f"     raw: {text!r}  headers: {headers}")
        return bool(text), latency, text[:40], headers if any(headers.values()) else None
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower():
            return False, 0.0, f"RATE LIMITED — {msg[:80]}", None
        if "401" in msg or "403" in msg:
            return False, 0.0, f"INVALID KEY — {msg[:80]}", None
        return False, 0.0, msg[:100], None


def _ping_openrouter(key: str, verbose: bool) -> Tuple[bool, float, str, Optional[dict]]:
    try:
        import requests as _req
        # Use a free model to avoid charging credits
        t0   = time.perf_counter()
        resp = _req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization":  f"Bearer {key}",
                "Content-Type":   "application/json",
                "HTTP-Referer":   "https://insightswarm.ai",
                "X-Title":        "InsightSwarm-Test",
            },
            json={
                "model":    "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": TINY_PROMPT}],
                "max_tokens": 8, "temperature": 0.0,
            },
            timeout=25,
        )
        latency = time.perf_counter() - t0
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if verbose:
            print(f"     raw: {text!r}")
        return bool(text), latency, text[:40], None
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower():
            return False, 0.0, f"RATE LIMITED — {msg[:80]}", None
        if "401" in msg or "403" in msg or "no auth" in msg.lower():
            return False, 0.0, f"INVALID KEY — {msg[:80]}", None
        return False, 0.0, msg[:100], None


def _ping_tavily(key: str, verbose: bool) -> Tuple[bool, float, str, Optional[dict]]:
    try:
        import requests as _req
        t0   = time.perf_counter()
        resp = _req.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": key, "query": "InsightSwarm test ping", "max_results": 1},
            timeout=12,
        )
        latency = time.perf_counter() - t0
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("results", [])
        detail  = f"{len(results)} result(s)"
        if verbose:
            print(f"     keys: {list(data.keys())}")
        return True, latency, detail, None
    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg or "invalid" in msg.lower():
            return False, 0.0, f"INVALID KEY — {msg[:80]}", None
        if "429" in msg:
            return False, 0.0, f"QUOTA EXHAUSTED — {msg[:80]}", None
        return False, 0.0, msg[:100], None


PING_FNS = {
    "groq":       _ping_groq,
    "gemini":     _ping_gemini,
    "cerebras":   _ping_cerebras,
    "openrouter": _ping_openrouter,
    "tavily":     _ping_tavily,
}


# ── Token budget probe ────────────────────────────────────────────────────────

def _probe_token_budget(provider: str, key: str, verbose: bool) -> Tuple[bool, str]:
    """
    Send a ~500-token prompt to check if the provider still has TPM headroom.
    This catches keys that are alive but have their per-minute token bucket near zero.
    """
    if provider == "tavily":
        return True, "N/A"

    MEDIUM_PROMPT = (
        "You are evaluating a claim for a fact-checking system. "
        "The claim is: 'Regular aerobic exercise improves cardiovascular health in adults.' "
        "List three key scientific arguments in favour of this claim, each in one sentence. "
        "Then list two counter-arguments or limitations. Reply in plain prose, no JSON needed."
    )  # ≈ 70 tokens prompt; expect ≈ 150 tokens output = ~220 total

    try:
        from src.llm.client import FreeLLMClient
        client = FreeLLMClient()
        t0     = time.perf_counter()
        result = client.call(
            MEDIUM_PROMPT,
            max_tokens=200,
            temperature=0.3,
            preferred_provider=provider,
        )
        elapsed = time.perf_counter() - t0
        snippet = result[:80].replace("\n", " ")
        detail  = f"~220 tok in {elapsed:.1f}s → {snippet}…"
        if verbose:
            print(f"     token probe: {detail}")
        return True, detail
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower() or "tpm" in msg.lower():
            return False, f"TPM LIMIT HIT — {msg[:80]}"
        return False, msg[:100]


# ── Structured output test ────────────────────────────────────────────────────

def _test_structured_output(provider: str, verbose: bool) -> Tuple[bool, str]:
    if provider == "tavily":
        return True, "N/A"
    try:
        from pydantic import BaseModel
        from src.llm.client import FreeLLMClient

        class _Ping(BaseModel):
            status: str
            ok:     bool

        client = FreeLLMClient()
        result = client.call_structured(
            prompt='Return valid JSON only: {"status": "PONG", "ok": true}',
            output_schema=_Ping,
            temperature=0.0,
            max_tokens=40,
            preferred_provider=provider,
        )
        detail = f"status={result.status!r}  ok={result.ok}"
        if verbose:
            print(f"     structured: {detail}")
        return True, detail
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower():
            return False, f"RATE LIMITED — {msg[:80]}"
        return False, msg[:100]


# ── Main test runner ──────────────────────────────────────────────────────────

def test_provider(name: str, cfg: dict, format_only: bool, verbose: bool) -> dict:
    result = {
        "name":          name,
        "required":      cfg["required"],
        "role":          cfg["role"],
        "key_found":     False,
        "format_ok":     False,
        "ping_ok":       False,
        "token_probe_ok": False,
        "structured_ok": False,
        "latency_ms":    None,
        "rate_headers":  None,
        "detail":        "",
        "overall":       "SKIP",
    }

    # Step 1: key present?
    key = os.getenv(cfg["env_var"], "").strip().strip("\"'")
    if not key:
        result["detail"]  = f"{cfg['env_var']} not set"
        result["overall"] = "MISSING"
        return result
    result["key_found"] = True

    # Step 2: format check
    prefix  = cfg.get("prefix")
    min_len = cfg["min_length"]
    bad_fmt = len(key) < min_len or (prefix and not key.startswith(prefix))
    if bad_fmt:
        result["detail"]  = f"Bad format — length={len(key)}, prefix={key[:8]!r}"
        result["overall"] = "BAD_FORMAT"
        return result
    result["format_ok"] = True

    if format_only:
        result["overall"] = "FORMAT_OK"
        return result

    # Step 3: liveness ping
    print(f"  {C.DIM}pinging {name}…{C.RESET}", end=" ", flush=True)
    ping_fn = PING_FNS[name]
    ok_flag, latency, detail, headers = ping_fn(key, verbose)
    result["latency_ms"]   = round(latency * 1000, 1)
    result["rate_headers"] = headers
    result["detail"]       = detail

    if ok_flag:
        result["ping_ok"] = True
        print(ok(f"{latency*1000:.0f}ms  →  {detail}"))
        if headers:
            hstr = "  ".join(f"{k}={v}" for k, v in headers.items() if v is not None)
            print(f"     {C.DIM}rate headers: {hstr}{C.RESET}")
    else:
        print(fail(detail))
        result["overall"] = "PING_FAILED"
        return result

    # Step 4: token budget probe
    if name != "tavily":
        print(f"  {C.DIM}token budget probe…{C.RESET}", end=" ", flush=True)
        tok_ok, tok_detail = _probe_token_budget(name, key, verbose)
        result["token_probe_ok"] = tok_ok
        if tok_ok:
            print(ok(tok_detail[:80]))
        else:
            print(warn(f"token probe: {tok_detail}"))
    else:
        result["token_probe_ok"] = True

    # Step 5: structured output
    if name != "tavily":
        print(f"  {C.DIM}structured JSON round-trip…{C.RESET}", end=" ", flush=True)
        s_ok, s_detail = _test_structured_output(name, verbose)
        result["structured_ok"] = s_ok
        if s_ok:
            print(ok(s_detail))
        else:
            print(warn(f"structured: {s_detail}"))
    else:
        result["structured_ok"] = True

    result["overall"] = (
        "PASS"    if result["ping_ok"] and result["token_probe_ok"] and result["structured_ok"]
        else "PARTIAL"
    )
    return result


# ── Rate limit budget summary ─────────────────────────────────────────────────

def _print_budget_table():
    """Print the researched free-tier limits for informed planning."""
    print(f"\n{C.BOLD}  API Free-Tier Budget Reference (April 2026){C.RESET}")
    rows = [
        ("Groq",        "30",  "14 400", "6 000 TPM",    "70B probe: ~2-3k tok → watch TPM"),
        ("Gemini",      "10",  "250",    "250 000 TPM",  "Dec-2025 cuts: 250 RPD for flash"),
        ("Cerebras",    "30",  "—",      "60 000 TPM",   "1M tok/day; 8k ctx on free"),
        ("OpenRouter",  "10",  "~200",   "varies",       "Free models rotate"),
        ("Tavily",      "—",   "~33",    "—",            "1 000 searches/month"),
    ]
    print(f"  {'Provider':<14} {'RPM':>5} {'RPD':>8} {'TPM':>14}  Note")
    print(f"  {'─'*12} {'─'*5} {'─'*8} {'─'*14}  {'─'*32}")
    for r in rows:
        print(f"  {r[0]:<14} {r[1]:>5} {r[2]:>8} {r[3]:>14}  {r[4]}")
    print()


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test(verbose: bool) -> bool:
    print(f"\n{C.BOLD}{'─'*60}{C.RESET}")
    print(f"{C.BOLD}🧪  Full Debate Smoke Test{C.RESET}")
    print(f"    Claim: \"The Earth is round\"")
    print(f"    Expected verdict: TRUE (settled-science shortcut, no LLM call)")
    try:
        from src.orchestration.debate import DebateOrchestrator
        orch    = DebateOrchestrator()
        t0      = time.perf_counter()
        result  = orch.run("The Earth is round")
        elapsed = time.perf_counter() - t0
        orch.close()

        v  = result.verdict
        c  = result.confidence
        cached = result.is_cached

        if v == "TRUE" and c >= 0.9:
            tag = "from cache" if cached else f"{elapsed:.1f}s"
            print(ok(f"Verdict: {v}  confidence: {c:.0%}  ({tag})"))
            return True
        print(fail(f"Unexpected: verdict={v}  confidence={c:.0%}"))
        return False
    except Exception as e:
        print(fail(f"Smoke test crashed: {e}"))
        if verbose:
            import traceback; traceback.print_exc()
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="InsightSwarm API Key Robustness Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--providers",   type=str,  default=None,
                        help="Comma-separated providers (default: all)")
    parser.add_argument("--format-only", action="store_true",
                        help="Only check key format, skip live API calls")
    parser.add_argument("--smoke-test",  action="store_true",
                        help="Run a full debate smoke test at the end")
    parser.add_argument("--verbose",     action="store_true",
                        help="Show raw API responses and headers")
    parser.add_argument("--budget",      action="store_true",
                        help="Print free-tier budget table and exit")
    args = parser.parse_args()

    if args.budget:
        _print_budget_table()
        return

    chosen = (
        [p.strip() for p in args.providers.split(",")]
        if args.providers else list(PROVIDERS.keys())
    )

    print(f"\n{C.BOLD}{'═'*60}{C.RESET}")
    print(f"{C.BOLD}🦅  InsightSwarm — API Key Robustness Test Suite{C.RESET}")
    print(f"    Mode: {'format-only' if args.format_only else 'live (ping + token + structured)'}")
    print(f"    Providers: {', '.join(chosen)}")
    print(f"{'═'*60}{C.RESET}\n")

    results: List[dict] = []

    for name in chosen:
        if name not in PROVIDERS:
            print(warn(f"Unknown provider '{name}' — skipping"))
            continue
        cfg = PROVIDERS[name]
        rpm  = cfg.get("rpm_limit")
        rpd  = cfg.get("rpd_limit")
        meta = f"RPM={rpm or '?'}, RPD={rpd or 'token-based'}"
        print(f"{C.BOLD}▸ {name.upper()}{C.RESET}  "
              f"{C.DIM}[{meta}]  role: {cfg['role']}{C.RESET}")

        r = test_provider(name, cfg, args.format_only, args.verbose)
        results.append(r)

        o = r["overall"]
        if o == "PASS":
            print(ok(f"All checks passed  [{r['latency_ms']}ms]\n"))
        elif o == "FORMAT_OK":
            print(ok(f"Key format valid (live ping skipped)\n"))
        elif o == "MISSING":
            sym = fail if cfg["required"] else warn
            print(sym(f"{'REQUIRED' if cfg['required'] else 'Optional'} key missing: {r['detail']}\n"))
        elif o == "PARTIAL":
            print(warn(f"Ping OK but token/structured probe failed — check TPM budget\n"))
        else:
            sym = fail if cfg["required"] else warn
            print(sym(f"FAILED: {r['detail']}\n"))

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"{C.BOLD}{'─'*60}")
    print(f"  Summary{C.RESET}")
    print(f"{'─'*60}")
    print(f"  {'Provider':<14} {'Status':<16} {'Latency':>9}  {'Role'}")
    print(f"  {'─'*12} {'─'*14} {'─'*9}  {'─'*28}")

    any_required_failed = False
    for r in results:
        s       = r["overall"]
        latency = f"{r['latency_ms']}ms" if r["latency_ms"] else "—"
        colour  = (
            C.GREEN  if s in ("PASS", "FORMAT_OK") else
            C.YELLOW if s in ("PARTIAL", "MISSING") and not r["required"] else
            C.RED
        )
        req = " *" if r["required"] else ""
        print(f"  {colour}{r['name']:<14} {s:<16}{C.RESET} {latency:>9}  "
              f"{r['role'][:28]}{req}")
        if s not in ("PASS", "FORMAT_OK", "PARTIAL") and r["required"]:
            any_required_failed = True

    if any(r["required"] for r in results):
        print(f"\n  * = required provider")

    # ── Budget reference ──────────────────────────────────────────────────────
    print(f"\n  {C.DIM}Run  python scripts/test_api_keys.py --budget  "
          f"to see free-tier limits table.{C.RESET}")

    # ── Rate-limit context for this project ───────────────────────────────────
    print(f"\n{C.BOLD}  InsightSwarm quota context{C.RESET}")
    print(f"  · 1 debate ≈ 14 LLM calls  |  ~3 000-8 000 tokens total")
    print(f"  · Groq free (30 RPM, 6k TPM): max ~1 debate/min before TPM kicks in")
    print(f"  · Gemini free (250 RPD): ~250 debate rounds/day using Gemini")
    print(f"  · Tavily free (33/day): ~16 full debates/day (2 searches each)")
    print(f"  · Cerebras free (1M tok/day): ~125-300 debate rounds/day")
    print(f"  · Caching + consensus shortcut reduce real API usage by ~40%")

    # ── Smoke test ────────────────────────────────────────────────────────────
    smoke_passed = True
    if args.smoke_test:
        smoke_passed = _smoke_test(args.verbose)

    # ── Exit code ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    if any_required_failed:
        print(f"{C.RED}{C.BOLD}  ❌  REQUIRED providers failed. System will not start.{C.RESET}")
        print(f"  Fix your .env file and rerun.\n")
        sys.exit(1)
    elif not smoke_passed:
        print(f"{C.YELLOW}{C.BOLD}  ⚠   Keys OK but smoke test failed.{C.RESET}\n")
        sys.exit(1)
    else:
        print(f"{C.GREEN}{C.BOLD}  ✅  All required checks passed. Ready to run InsightSwarm.{C.RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
