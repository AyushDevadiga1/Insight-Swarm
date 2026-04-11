# InsightSwarm 🦅

> **Multi-Agent Fact-Checking through Adversarial Debate, Human-in-the-Loop Oversight, and Adaptive Confidence Calibration**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0-orange)](https://langchain-ai.github.io/langgraph/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-168%20passing-brightgreen.svg)]()
[![Published](https://img.shields.io/badge/IJRASET-Published-blue.svg)]()

A **production-grade, research-quality** automated fact-checking system where four specialised AI agents debate claims, verify sources in real-time, and converge on a calibrated verdict — with optional human intervention at any stage. Built entirely on free-tier APIs with zero infrastructure cost.

**Bharat College of Engineering, University of Mumbai**
Guided by **Prof. Shital Gujar**, Dept. of CSE (AI & ML)

---

## Table of Contents

- [What It Does](#what-it-does)
- [Novel Research Contributions](#novel-research-contributions)
- [High-Level Design (HLD)](#high-level-design-hld)
- [System Architecture Diagram](#system-architecture-diagram)
- [LangGraph Execution Flow](#langgraph-execution-flow)
- [Data Flow Diagram](#data-flow-diagram)
- [Low-Level Design (LLD)](#low-level-design-lld)
- [Agent Design](#agent-design)
- [API Resilience Architecture](#api-resilience-architecture)
- [Frontend Architecture](#frontend-architecture)
- [Database and Caching Layer](#database-and-caching-layer)
- [HITL Flow](#hitl-flow)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Running Benchmarks](#running-benchmarks)
- [Key Metrics](#key-metrics)
- [Development Trajectory](#development-trajectory)
- [Tests](#tests)
- [Citation](#citation)
- [Acknowledgements](#acknowledgements)

---

## What It Does

You submit a claim. InsightSwarm:

1. **Estimates complexity** — ClaimComplexityEstimator scores the claim on semantic, domain, temporal, and evidence-availability dimensions and adjusts debate depth automatically (2–4 rounds, 3–7 minimum sources)
2. **Decomposes** — ClaimDecomposer splits compound claims into atomic sub-claims, processed in parallel
3. **Checks consensus** — A lightweight pre-check detects settled scientific facts (e.g. "vaccines cause autism") and short-circuits debate entirely if confidence > 90%
4. **Retrieves evidence** — Tavily search fetches real web evidence for both PRO and CON sides simultaneously before debate begins
5. **Debates** — ProAgent (🛡️) argues TRUE, ConAgent (⚔️) argues FALSE across N rounds. Each receives the opponent's prior argument and must directly challenge it
6. **Verifies** — FactChecker fetches every cited URL, runs semantic similarity matching, paywall detection, temporal alignment, and domain trust scoring. Detects both **Type I** (fabricated URL) and **Type II** (real URL, fabricated content) hallucinations
7. **Pauses for human review** — if source verification confidence falls below 30%, the LangGraph graph interrupts and emits a `human_review_required` SSE event to the React frontend
8. **Moderates** — Moderator synthesises a trust-weighted composite verdict using argument quality (30%) + verification rate (30%) + domain trust (20%) + consensus pre-check (20%)
9. **Calibrates** — AdaptiveConfidenceCalibrator corrects systematic underconfidence using geometric-mean source trust scoring and debate asymmetry signals
10. **Streams** — every pipeline step is streamed live to the React frontend via Server-Sent Events

---

## Novel Research Contributions

| Contribution | Description | Where |
|---|---|---|
| **Type I + II Hallucination Detection** | Every cited URL is fetched and content-matched. Type I = 404/DNS failure. Type II = real URL whose content doesn't support the agent's claim | `src/agents/fact_checker.py` |
| **Trust-Weighted Composite Verdict** | `S = 0.30×Qarg + 0.30×Vrate + 0.20×Tdomain + 0.20×Ccons` — argument quality, verification rate, domain trust, and consensus pre-check | `src/agents/moderator.py` |
| **HITL via LangGraph Interrupts** | Graph pauses at `interrupt_before=["human_review"]`; React HITLPanel renders per-source override UI; `/api/debate/resume/{id}` resumes from checkpoint | `src/orchestration/debate.py` |
| **Adaptive Confidence Calibration** | Detects systematic underconfidence (`raw < 0.65` while `source_quality > 0.75`). Uses geometric mean (not arithmetic) of trust scores to penalise single weak sources | `src/novelty/confidence_calibration.py` |
| **Claim Complexity Estimation** | Scores semantic + domain + temporal + evidence-availability dimensions. Dynamically sets debate rounds and minimum source count | `src/novelty/claim_complexity.py` |
| **Argumentation Quality Analysis** | 10 logical fallacy types detected per argument (ad hominem, strawman, false dichotomy, appeal to authority, slippery slope, appeal to emotion, hasty generalisation, circular reasoning, red herring, cherry-picking) | `src/novelty/argumentation_analysis.py` |

---

## High-Level Design (HLD)

The system is organised into four logical layers. Each layer has a single responsibility and communicates with the layers above and below it through well-defined interfaces.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LAYER 1 — PRESENTATION                            │
│                                                                             │
│   React 18 + Vite frontend  │  Zustand state  │  SSE EventSource stream    │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│   │  DebateArena │  │ StagePanel   │  │ HITLPanel    │  │ MetricsGrid   │  │
│   │  (live feed) │  │ (pipeline)   │  │ (overrides)  │  │ (calibration) │  │
│   └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲  SSE / REST
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LAYER 2 — API GATEWAY                              │
│                                                                             │
│   FastAPI  │  slowapi rate-limiting (10 req/min)  │  CORS  │  Auth         │
│   ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐    │
│   │  POST /verify    │  │  GET /stream     │  │  POST /debate/resume  │    │
│   │  (submit claim)  │  │  (SSE events)    │  │  (HITL resume)        │    │
│   └──────────────────┘  └──────────────────┘  └───────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲  Python calls
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LAYER 3 — ORCHESTRATION ENGINE                       │
│                                                                             │
│   LangGraph StateGraph  │  DebateOrchestrator  │  MemorySaver checkpoint   │
│                                                                             │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│   │ Consensus│ │ProAgent  │ │ConAgent  │ │FactCheck │ │   Moderator    │  │
│   │  Check   │ │ (Groq)   │ │ (Gemini) │ │  (Groq)  │ │   (Gemini)     │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│                                                                             │
│   ┌─────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│   │ ClaimComplexityEst. │  │ ArgumentationAnalyzer│  │ ConfCalibrator   │  │
│   └─────────────────────┘  └──────────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲  API calls
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 4 — INFRASTRUCTURE                              │
│                                                                             │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────────────┐    │
│  │  FreeLLMClient   │  │ Tavily Search  │  │  SQLite (semantic cache) │    │
│  │  (4-provider     │  │  + Google CSE  │  │  all-MiniLM-L6-v2 embeds │    │
│  │   rotation)      │  │  failover      │  │  cosine similarity 0.85  │    │
│  └──────────────────┘  └────────────────┘  └──────────────────────────┘    │
│                                                                             │
│  Groq → Gemini → Cerebras → OpenRouter  (circuit-breaker + exponential)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture Diagram

```
                        ┌─────────────────────┐
                        │      USER CLAIM      │
                        └──────────┬──────────┘
                                   │
                                   ▼
                     ┌─────────────────────────┐
                     │    FastAPI Backend        │
                     │  POST /verify            │
                     │  GET  /stream (SSE)      │
                     │  POST /debate/resume     │
                     └──────────┬──────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │         DebateOrchestrator           │
              │                                      │
              │   ┌─────────────────────────────┐   │
              │   │  SemanticCache (SQLite)      │   │
              │   │  cosine sim ≥ 0.85 → HIT    │   │
              │   └─────────────┬───────────────┘   │
              │                 │ MISS               │
              │                 ▼                    │
              │   ┌─────────────────────────────┐   │
              │   │  ClaimComplexityEstimator    │   │
              │   │  → num_rounds, min_sources   │   │
              │   └─────────────┬───────────────┘   │
              │                 ▼                    │
              │   ┌─────────────────────────────┐   │
              │   │  ClaimDecomposer             │   │
              │   │  → atomic sub-claims         │   │
              │   └─────────────┬───────────────┘   │
              │                 ▼                    │
              │   ┌─────────────────────────────┐   │
              │   │  Tavily Search (adversarial) │   │
              │   │  PRO evidence + CON evidence │   │
              │   └─────────────┬───────────────┘   │
              └─────────────────┼────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────────────┐
        │               LangGraph StateGraph                │
        │                                                    │
        │  ┌─────────────────────────────────────────────┐  │
        │  │            DebateState (Pydantic v2)        │  │
        │  │  claim, round, pro_arguments, con_arguments │  │
        │  │  verification_results, metrics, confidence  │  │
        │  └─────────────────────────────────────────────┘  │
        │                                                    │
        │  [START]                                           │
        │     │                                              │
        │     ▼                                              │
        │  ┌─────────────────┐    confidence > 0.90         │
        │  │ consensus_check │──────────────────────────┐   │
        │  └────────┬────────┘                          │   │
        │           │ needs debate                      │   │
        │           ▼                                   │   │
        │  ┌──────────────────────────────────────┐     │   │
        │  │  ┌──────────┐  ×N  ┌──────────────┐ │     │   │
        │  │  │ pro_agent│─────▶│  con_agent   │ │     │   │
        │  │  │  (Groq)  │      │   (Gemini)   │ │     │   │
        │  │  └──────────┘      └──────┬───────┘ │     │   │
        │  │   ▲ summarizer feeds      │          │     │   │
        │  │   └──────────────────────┘ loop end │     │   │
        │  └──────────────────────────────────────┘     │   │
        │           │                                   │   │
        │           ▼                                   │   │
        │  ┌──────────────────┐                         │   │
        │  │  fact_checker    │ strips Type I & II      │   │
        │  │  (Groq)          │ hallucinations           │   │
        │  └────────┬─────────┘                         │   │
        │           │ rate < 30%?  ──▶ [revision loop]  │   │
        │           │ rate ≥ 30%                        │   │
        │           ▼                                   │   │
        │  ╔════════════════════╗  ← HITL INTERRUPT     │   │
        │  ║   human_review     ║  (graph pauses,       │   │
        │  ║  (SSE emitted)     ║   SSE fires)          │   │
        │  ╚════════════════════╝                        │   │
        │           │ resume via /api/debate/resume      │   │
        │           ▼                        ◀──────────┘   │
        │  ┌────────────────────────────────────────────┐   │
        │  │               moderator (Gemini)           │   │
        │  │  S = 0.30×Qarg + 0.30×Vrate               │   │
        │  │      + 0.20×Tdomain + 0.20×Ccons          │   │
        │  │  + ArgumentationAnalyzer (10 fallacies)    │   │
        │  │  + AdaptiveConfidenceCalibrator            │   │
        │  └────────────────────┬───────────────────────┘   │
        │                       │                            │
        │                       ▼                            │
        │  ┌──────────────────────────────────────────────┐ │
        │  │          verdict (ExplainabilityEngine)      │ │
        │  │  → TRUE / FALSE / PARTIALLY TRUE /           │ │
        │  │    INSUFFICIENT EVIDENCE                     │ │
        │  └──────────────────────────────────────────────┘ │
        │                       │                            │
        │                    [END]                           │
        └───────────────────────┬───────────────────────────┘
                                │ SSE stream
                                ▼
                   ┌─────────────────────────┐
                   │    React 18 Frontend     │
                   │  Vite + Zustand + SSE    │
                   └─────────────────────────┘
```

---

## LangGraph Execution Flow

```
START
  │
  ├──▶ consensus_check
  │         │
  │    conf > 0.90? ──YES──▶ moderator ──▶ verdict ──▶ END
  │         │ NO
  │         ▼
  │    summarizer  (history cap + rolling summary after round 2)
  │         │
  │    ┌────┴─────────────────────────────────┐
  │    │   DEBATE LOOP (× num_rounds)          │
  │    │                                       │
  │    │   pro_agent (Groq Llama 3.3 70B)      │
  │    │       │ role-locked to argue TRUE      │
  │    │       │ retrieves PRO evidence         │
  │    │       ▼                                │
  │    │   con_agent (Gemini 2.5 Flash)         │
  │    │       │ role-locked to argue FALSE     │
  │    │       │ challenges prior pro argument  │
  │    │       ▼                                │
  │    │   _should_continue?                   │
  │    │       │ round < num_rounds ──▶ loop   │
  │    └────────────────────────────────────────┘
  │         │ round == num_rounds
  │         ▼
  │    fact_checker (Groq)
  │         │ fetches all cited URLs
  │         │ semantic similarity matching (≥ 0.82)
  │         │ paywall detection
  │         │ temporal alignment
  │         │ domain trust scoring
  │         │
  │    _should_retry?
  │         │ rate < 30% AND retry_count < 1 ──▶ revision ──▶ fact_checker
  │         │ rate ≥ 30% OR retry exhausted
  │         ▼
  │    ╔═════════════════════╗
  │    ║   human_review      ║  ◀── INTERRUPT (interrupt_before)
  │    ║   (graph pauses)    ║      SSE fires human_review_required
  │    ╚═════════════════════╝      HITLPanel shown in React
  │         │ POST /api/debate/resume/{thread_id}
  │         │ (with optional source overrides + verdict override)
  │         ▼
  │    moderator (Gemini 2.5 Flash)
  │         │ trust-weighted composite score
  │         │ + ArgumentationAnalyzer
  │         │ + AdaptiveConfidenceCalibrator
  │         ▼
  │    verdict
  │         │ ExplainabilityEngine (XAI)
  │         │ → writes to semantic cache
  │         ▼
  │       END
```

---

## Data Flow Diagram

```
                        USER
                          │
                  Submit claim text
                          │
                          ▼
              ┌───────────────────────┐
              │   FastAPI Server      │
              │   POST /verify        │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │   Semantic Cache      │  ◀─── SQLite + all-MiniLM-L6-v2
              │   cosine sim ≥ 0.85   │       embeddings stored per claim
              └─────┬─────────────────┘
            MISS    │        HIT
                    │         │
                    │         └──────────────────▶ cached verdict
                    ▼                              returned in < 1s
        ┌─────────────────────────┐
        │  ClaimComplexityEstimator│
        │  semantic + domain +    │
        │  temporal + evidence    │
        │  → complexity_tier      │
        │  → num_rounds (2-4)     │
        │  → min_sources (3-7)    │
        └───────────┬─────────────┘
                    ▼
        ┌─────────────────────────┐
        │    ClaimDecomposer      │
        │  (complex claim?)       │
        │  YES → [s1, s2, s3]    │
        │  NO  → [original]       │
        └───────────┬─────────────┘
                    ▼
        ┌─────────────────────────┐
        │   Tavily Search API     │
        │  search_adversarial()   │
        │  → pro_evidence[]       │
        │  → con_evidence[]       │
        │                         │
        │  Failover: Google CSE   │
        │  (on HTTP 429 / 403)    │
        └───────────┬─────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
    pro_evidence          con_evidence
    (passed to ProAgent)  (passed to ConAgent)
         │                     │
         ▼                     ▼
   ┌──────────┐          ┌──────────┐
   │ ProAgent │          │ ConAgent │
   │ argues   │ ◀──────▶ │ argues   │
   │  TRUE    │  debate  │  FALSE   │
   └────┬─────┘  loop    └─────┬────┘
        │                      │
        │  pro_arguments[]     │  con_arguments[]
        │  pro_sources[]       │  con_sources[]
        └──────────┬───────────┘
                   ▼
         ┌───────────────────┐
         │   FactChecker     │
         │                   │
         │  For each URL:    │
         │  1. HTTP fetch    │
         │  2. BeautifulSoup │
         │  3. Cosine sim    │
         │     vs claim text │
         │  4. Paywall check │
         │  5. Temporal align│
         │  6. Domain trust  │
         │                   │
         │  Status assigned: │
         │  VERIFIED         │
         │  NOT_FOUND        │
         │  CONTENT_MISMATCH │
         │  TIMEOUT          │
         │  PAYWALL_RESTRICTED│
         │  INVALID_URL      │
         └────────┬──────────┘
                  │
        pro_ver_rate + con_ver_rate
                  │
         rate < 30%?
         YES ──▶ revision loop (max 1×)
         NO  ──▶
                  │
         ╔════════▼═══════╗
         ║ HITL INTERRUPT ║  (if rate still low after revision)
         ║                ║  SSE: human_review_required
         ║ HITLPanel:     ║  Human reviews per-URL statuses
         ║ override source║  and optionally sets verdict_override
         ╚════════╤═══════╝
                  │ POST /api/debate/resume
                  ▼
         ┌──────────────────────────────────────────┐
         │               Moderator                  │
         │                                          │
         │  S = 0.30 × Qarg                         │
         │    + 0.30 × Vrate                        │
         │    + 0.20 × Tdomain                      │
         │    + 0.20 × Ccons                        │
         │                                          │
         │  ArgumentationAnalyzer:                  │
         │    detect 10 fallacy types per argument  │
         │    citation quality + rhetoric scoring   │
         │    → quality_score per argument          │
         │                                          │
         │  AdaptiveConfidenceCalibrator:           │
         │    Qsrc = geomean(trust_scores)          │
         │    Asym = |pro_len - con_len| / total    │
         │    E = 0.60×Qsrc + 0.40×Asym            │
         │    boost = min(0.25, (E-0.60)×0.50)     │
         │    conf_final = raw + boost×(1-raw)      │
         │                                          │
         │  Verdict: TRUE / FALSE /                 │
         │           PARTIALLY TRUE /               │
         │           INSUFFICIENT EVIDENCE          │
         └──────────────────┬───────────────────────┘
                            │
                            ▼
                   ExplainabilityEngine
                   (feature importance, decision path,
                    counterfactuals, transparency score)
                            │
                            ▼
                   Write to SemanticCache
                            │
                    ◀── SSE: verdict event ──▶
                            │
                         USER sees:
                  verdict + confidence +
                  debate transcript +
                  per-URL verification table +
                  argumentation quality panel +
                  calibration metadata
```

---

## Low-Level Design (LLD)

### Core Data Models

```
DebateState (Pydantic v2 BaseModel)
├── claim: str
├── round: int = 1
├── num_rounds: int = 3
├── pro_arguments: List[str]          # one entry per round
├── con_arguments: List[str]          # one entry per round
├── pro_sources: List[List[str]]      # URLs cited per round
├── con_sources: List[List[str]]
├── pro_evidence: List[Dict]          # Tavily evidence for ProAgent
├── con_evidence: List[Dict]          # Tavily evidence for ConAgent
├── evidence_sources: List[Dict]      # merged, used by FactChecker for URL allow-list
├── verification_results: List[Dict]  # SourceVerification records
├── pro_verification_rate: float
├── con_verification_rate: float
├── verdict: str = "UNKNOWN"
├── confidence: float = 0.0
├── moderator_reasoning: str
├── metrics: Dict[str, Any]           # consensus, argumentation_analysis, calibration, explanation
├── is_cached: bool = False
├── summary: str                      # rolling debate summary (after round 2)
├── sub_claims: List[str]
├── retry_count: int = 0
├── human_verdict_override: Optional[str]   # set by HITL resume
└── system_status: Optional[str]

SourceVerification (Pydantic v2 BaseModel)
├── url: str
├── status: Literal["VERIFIED","NOT_FOUND","INVALID_URL","TIMEOUT",
│                   "CONTENT_MISMATCH","PAYWALL_RESTRICTED","ERROR"]
├── confidence: float         # 0.0–1.0
├── similarity_score: float   # RapidFuzz / cosine similarity
├── trust_score: float        # domain authority weight
├── trust_tier: str           # ACADEMIC / GOVERNMENT / NEWS / GENERAL / LOW
├── agent_source: Literal["PRO","CON"]
├── content_preview: Optional[str]
├── matched_claim: Optional[str]
└── error: Optional[str]

AgentResponse (Pydantic v2 BaseModel)
├── agent: Literal["PRO","CON","MODERATOR","FACT_CHECKER"]
├── round: int
├── argument: str
├── sources: List[str]
├── confidence: float
├── verdict: Optional[str]
├── reasoning: Optional[str]
└── metrics: Optional[Dict]

ModeratorVerdict (Pydantic v2 BaseModel)
├── verdict: str           # auto-normalised via field_validator
├── confidence: float
├── reasoning: str
└── metrics: Optional[Dict]
```

### LLM Client — Provider Rotation Logic

```
FreeLLMClient.call() / call_structured()
│
├── _provider_order(preferred_provider)
│     └── [preferred, groq, gemini, cerebras, openrouter]  (rotated)
│
├── for each provider:
│     ├── CircuitBreaker.is_allowed()?  NO → skip
│     ├── APIKeyManager.has_working_keys()?  NO → skip
│     ├── provider_cooldown not expired?  NO → skip
│     ├── _check_rate_limit()  (per-minute sliding window)  EXCEEDED → skip
│     │
│     └── _dispatch_call()
│           ├── Groq:       groq.chat.completions.create()
│           ├── Gemini:     genai.Client.models.generate_content()
│           ├── Cerebras:   requests.post to api.cerebras.ai
│           └── OpenRouter: requests.post to openrouter.ai
│
│     On success → CircuitBreaker.record_success()
│                  APIKeyManager.report_key_success()
│                  return response text
│
│     On rate limit → extract retry_after → set_provider_cooldown()
│                     break (try next provider)
│
│     On other error → CircuitBreaker.record_failure()
│                      APIKeyManager.report_key_failure()
│                      exponential backoff (capped at 8s)
│                      retry up to max_retries
│
└── All providers failed → raise RuntimeError

APIKeyManager
├── tri-state per key: ACTIVE / RATE_LIMITED / INVALID (zero-quota)
├── RATE_LIMITED keys → cooldown 90s then auto-recover
├── INVALID keys → permanently skipped (zero-quota config issue)
└── report_key_success() / report_key_failure() thread-safe with Lock

CircuitBreaker (per provider)
├── failure_threshold: 3
├── recovery_timeout: 60s
├── CLOSED → OPEN after 3 consecutive failures
├── OPEN → HALF_OPEN after recovery_timeout
└── HALF_OPEN → CLOSED on success, OPEN on failure
```

---

## Agent Design

```
BaseAgent (ABC)
├── generate(state: DebateState) → AgentResponse   [abstract]
├── _build_prompt(state, round_num) → str          [abstract]
├── _format_evidence(evidence_bundle) → str
└── _sanitize_sources(sources) → List[str]

ProAgent (BaseAgent)
├── Role: argue claim is TRUE
├── Provider: Groq (Llama 3.3 70B)
├── Evidence: uses state.pro_evidence (pre-fetched Tavily results)
├── Output schema: AgentArgumentResponse (Pydantic)
└── Role-locking: system prompt forces TRUE argument regardless of LLM prior

ConAgent (BaseAgent)
├── Role: argue claim is FALSE
├── Provider: Gemini 2.5 Flash
├── Evidence: uses state.con_evidence
├── Receives: last pro_argument (must challenge directly)
└── Output schema: AgentArgumentResponse

FactChecker (BaseAgent)
├── Role: verify every cited URL
├── Provider: Groq
├── URL allow-list: only URLs in state.evidence_sources pass (strips Type I hallucinations)
├── Content match: semantic cosine similarity (all-MiniLM-L6-v2) vs claim
├── Threshold: 0.82 (below = CONTENT_MISMATCH, Type II hallucination)
├── Domain trust tiers:
│     ACADEMIC:    .edu, .ac.uk, pubmed, arxiv, springer → 0.90
│     GOVERNMENT:  .gov, .gov.in, who.int, un.org       → 0.85
│     NEWS:        reuters, apnews, bbc, guardian        → 0.75
│     GENERAL:     wikipedia, major outlets              → 0.65
│     LOW:         social media, anonymous blogs         → 0.30
└── Thread pool: shared executor (prevents OOM from per-call executor creation)

Moderator (BaseAgent)
├── Role: synthesise final verdict
├── Provider: Gemini 2.5 Flash
├── Composite formula:
│     S = 0.30×Qarg + 0.30×Vrate + 0.20×Tdomain + 0.20×Ccons
├── Verdict normalisation: field_validator maps 30+ variant strings to canonical set
│     e.g. "PARTLY TRUE" → "PARTIALLY TRUE", "UNVERIFIABLE" → "INSUFFICIENT EVIDENCE"
├── Fallback on RateLimitError → RATE_LIMITED verdict (not a crash)
└── Passes raw confidence to AdaptiveConfidenceCalibrator (called in debate.py)
```

---

## API Resilience Architecture

```
Groq (primary, 28 RPM)
  │  ↓ rate limit / circuit open
Gemini (secondary, 9 RPM)
  │  ↓ rate limit / circuit open
Cerebras (tertiary, 28 RPM)
  │  ↓ rate limit / circuit open
OpenRouter (quaternary, 18 RPM)
  │  ↓ all exhausted
RuntimeError (surfaced to user gracefully)

Per-provider safeguards:
  ├── Sliding window rate counter (calls in last 60s vs PROVIDER_RATE_LIMITS)
  ├── 90-second cooldown on rate limit (configurable via env)
  ├── Circuit breaker (CLOSED → OPEN after 3 failures, recovers in 60s)
  ├── Tri-state APIKeyManager (ACTIVE / RATE_LIMITED / INVALID)
  ├── tenacity retry with exponential backoff (capped at 8s)
  └── API key redaction from error logs (regex strips gsk_*, AIza*, sk-or-* patterns)

Tavily Search failover:
  ├── Primary: Tavily API (dual-sided evidence retrieval)
  └── Failover: Google Custom Search Engine (on HTTP 429 / 403)
```

---

## Frontend Architecture

```
React 18 + Vite + Zustand

App.jsx (3-panel shell)
├── Sidebar.jsx
│     ├── ClaimInput.jsx          (submit new claim)
│     ├── HistoryList.jsx         (past claims)
│     └── ProviderStatus.jsx      (fallback warnings via metrics.model_substitutions)
│
├── Main Panel
│     ├── BattleHeader.jsx        (🛡️ ProAgent vs ⚔️ ConAgent live scores)
│     ├── DebateArena.jsx         (live debate transcript, SSE-driven)
│     │     └── AgentBubble.jsx   (per-argument bubble with source hover cards)
│     │           └── SourceHoverCard.jsx  (trust tier, verification status, URL)
│     ├── SubClaimBanner.jsx      (shown when claim is decomposed)
│     └── FallacyPanel.jsx        (detected fallacies per agent)
│
└── Right Panel (StagePanel.jsx)
      ├── Pipeline stages (DECOMPOSING → SEARCHING → PRO → CON → FACT_CHECK →
      │                    HUMAN_REVIEW → MODERATOR → COMPLETE)
      ├── HITLPanel.jsx           (per-source override dropdowns, amber pulse)
      │     └── triggers on human_review_required SSE event
      │     └── POST /api/debate/resume/{thread_id} on submit
      ├── MetricsGrid.jsx
      │     ├── ArgumentationBlock  (pro/con quality bars, fallacy counts)
      │     ├── CalibrationBlock    (raw → calibrated confidence, adjustment)
      │     └── VerificationTable   (per-URL status badges)
      └── LoadingOrb.jsx          (cinematic loading animation)

State Management (Zustand):
  useDebateStore.js
  ├── claim, threadId, status
  ├── proArguments[], conArguments[]
  ├── verificationResults[]
  ├── verdict, confidence, metrics
  ├── hitlRequired: bool
  └── actions: submitClaim, resumeHITL, reset

SSE Hook:
  useSSE.js
  ├── Stable UUID runId (prevents reconnect loops)
  ├── EventSource → /api/stream/{thread_id}
  ├── Events: progress, verdict, human_review_required, error, heartbeat
  └── AbortController for clean unmount (no stale connection leaks)
```

---

## Database and Caching Layer

```
SQLite (insightswarm.db)
├── Semantic cache table
│     ├── claim_embedding: BLOB   (all-MiniLM-L6-v2, 384-dim)
│     ├── verdict: TEXT
│     ├── confidence: REAL
│     ├── full_result: JSON
│     └── created_at: TIMESTAMP
│
└── Lookup algorithm:
      1. Encode incoming claim → 384-dim vector
      2. Load all cached embeddings into NumPy array (vectorised, O(1) amortised)
      3. Cosine similarity: new_vec · cached_vecs / (||new|| × ||cached||)
      4. Best match ≥ 0.85 threshold → return cached result (< 1s)
      5. Below threshold → run full debate pipeline

L1 In-Memory Cache (BoundedCache)
├── Thread-safe LRU (OrderedDict + Lock)
├── Max 100 entries
├── Sits in front of SQLite (avoids disk I/O for hot entries)
└── Evicts LRU on overflow
```

---

## HITL Flow

```
                    ┌─────────────────────────────────┐
                    │      FactChecker completes       │
                    │  pro_rate=0.18, con_rate=0.22    │
                    └────────────────┬────────────────┘
                                     │
                         both < 30% threshold?
                                     │ YES
                                     ▼
                    ┌─────────────────────────────────┐
                    │   _should_retry() → "retry"     │
                    │   revision loop (× 1 max)       │
                    │   agents regenerate arguments   │
                    │   fact_checker re-runs          │
                    └────────────────┬────────────────┘
                                     │
                         still < 30% after retry?
                                     │ YES
                                     ▼
                    ╔═════════════════════════════════╗
                    ║      human_review NODE          ║
                    ║  (LangGraph interrupt fires)    ║
                    ║                                 ║
                    ║  SSE event emitted:             ║
                    ║  { type: "human_review_required"║
                    ║    verification_results: [...] }║
                    ╚══════════════════╤══════════════╝
                                       │
                           React frontend receives event
                                       │
                                       ▼
                    ┌─────────────────────────────────┐
                    │         HITLPanel renders        │
                    │                                  │
                    │  For each URL:                   │
                    │  ┌─────────────────────────────┐ │
                    │  │ url: reuters.com/article... │ │
                    │  │ status: CONTENT_MISMATCH    │ │
                    │  │ Override: [dropdown]        │ │
                    │  │   VERIFIED / NOT_FOUND /    │ │
                    │  │   CONTENT_MISMATCH /        │ │
                    │  │   PAYWALL / INVALID_URL     │ │
                    │  └─────────────────────────────┘ │
                    │                                  │
                    │  Optional verdict override:      │
                    │  [TRUE / FALSE / PARTIALLY TRUE] │
                    │                                  │
                    │  [Submit Review] button          │
                    └──────────────────┬───────────────┘
                                       │ POST /api/debate/resume/{thread_id}
                                       │ body: { source_overrides, verdict_override }
                                       ▼
                    ┌─────────────────────────────────┐
                    │   Backend patches DebateState   │
                    │   human_verdict_override set    │
                    │   graph.invoke(None, config)    │
                    │   resumes from checkpoint       │
                    └──────────────────┬───────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────┐
                    │    moderator node runs          │
                    │    with corrected sources       │
                    │    verdict SSE event fires      │
                    └─────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Version | Role |
|---|---|---|---|
| Backend API | FastAPI | 0.110+ | REST + SSE endpoint server |
| Orchestration | LangGraph | 1.0 | Stateful debate graph |
| State models | Pydantic v2 | 2.x | Type-safe DebateState |
| Checkpointing | MemorySaver | built-in | Per-session graph state isolation |
| Primary LLM | Groq Llama 3.3 70B | latest | ProAgent + FactChecker |
| Secondary LLM | Gemini 2.5 Flash | latest | ConAgent + Moderator |
| Tertiary LLM | Cerebras Llama 3.1 8B | latest | Fallback provider |
| Quaternary LLM | OpenRouter | latest | Final fallback provider |
| Embeddings | all-MiniLM-L6-v2 | sentence-transformers | Semantic cache + URL matching |
| Search | Tavily API | — | Dual-sided evidence retrieval |
| Search failover | Google Custom Search | — | Auto-failover on 429/403 |
| Cache | SQLite + LRU | built-in | Semantic cache (< 1s hit latency) |
| Rate limiting | slowapi | — | 10 req/min per IP on API routes |
| Frontend | React 18 + Vite | 18 / 5+ | UI framework |
| State mgmt | Zustand | — | Frontend state |
| Streaming | native EventSource | — | SSE client (no library needed) |
| Icons | Lucide React | — | UI icons |
| Fonts | Inter + Fira Code | Google Fonts | Typography |
| Resilience | tenacity | — | Exponential backoff on LLM calls |
| HTML parsing | BeautifulSoup4 | 4.x | URL content extraction |
| Fuzzy match | RapidFuzz | — | URL content vs claim similarity |

---

## Project Structure

```
InsightSwarm/
│
├── api/
│   ├── server.py                  FastAPI app: /verify, /stream, /debate/resume, /health
│   └── websocket_hitl.py          WebSocket manager for HITL (fallback channel)
│
├── src/
│   ├── agents/
│   │   ├── base.py                BaseAgent ABC: format_evidence, sanitize_sources
│   │   ├── pro_agent.py           ProAgent: role-locked TRUE, Groq Llama 3.3 70B
│   │   ├── con_agent.py           ConAgent: role-locked FALSE, Gemini 2.5 Flash
│   │   ├── fact_checker.py        FactChecker: URL fetch + semantic match + trust scoring
│   │   └── moderator.py           Moderator: composite score + verdict normalisation
│   │
│   ├── core/
│   │   └── models.py              DebateState, AgentResponse, SourceVerification (Pydantic v2)
│   │
│   ├── llm/
│   │   └── client.py              FreeLLMClient: 4-provider rotation, circuit breaker, rate limits
│   │
│   ├── novelty/
│   │   ├── argumentation_analysis.py    10-fallacy detector, citation quality, rhetoric scoring
│   │   ├── confidence_calibration.py    AdaptiveConfidenceCalibrator (geometric mean, ECE)
│   │   ├── claim_complexity.py          ClaimComplexityEstimator (semantic/domain/temporal/evidence)
│   │   └── explainability.py            ExplainabilityEngine (feature importance, counterfactuals)
│   │
│   ├── orchestration/
│   │   ├── debate.py              DebateOrchestrator: LangGraph graph + all 9 nodes
│   │   └── cache.py               SemanticCache: SQLite + embeddings + LRU L1
│   │
│   ├── resilience/
│   │   ├── circuit_breaker.py     CircuitBreaker: CLOSED/OPEN/HALF_OPEN per provider
│   │   └── fallback_handler.py    FallbackHandler: wraps graph execution with graceful fallback
│   │
│   ├── utils/
│   │   ├── api_key_manager.py     APIKeyManager: tri-state key lifecycle (ACTIVE/RATE_LIMITED/INVALID)
│   │   ├── claim_decomposer.py    ClaimDecomposer: splits compound claims into atomic sub-claims
│   │   ├── summarizer.py          Summarizer: rolling debate history compression (after round 2)
│   │   ├── tavily_retriever.py    TavilyRetriever: adversarial search + Google CSE failover
│   │   ├── url_helper.py          URLNormalizer: sanitise, dedup, SSRF-filter URLs
│   │   └── trust_scorer.py        TrustScorer: domain authority tier assignment
│   │
│   └── monitoring/
│       └── api_status.py          Real-time provider health monitoring
│
├── frontend/
│   └── src/
│       ├── App.jsx                3-panel shell (Sidebar | DebateArena | StagePanel)
│       ├── index.css              Aurora glassmorphism theme, Inter + Fira Code
│       ├── components/
│       │   ├── debate/
│       │   │   ├── BattleHeader.jsx      🛡️ vs ⚔️ live score header
│       │   │   ├── DebateArena.jsx       SSE-driven live debate transcript
│       │   │   └── AgentBubble.jsx       Per-argument bubble + source hover cards
│       │   ├── hitl/
│       │   │   └── HITLPanel.jsx         Source override UI (amber pulse alert)
│       │   ├── layout/
│       │   │   └── Sidebar.jsx           Navigation + claim history + provider warnings
│       │   ├── pipeline/
│       │   │   ├── StagePanel.jsx        Pipeline stage tracker (right panel)
│       │   │   ├── SubClaimBanner.jsx    Sub-claim display when decomposed
│       │   │   └── FallacyPanel.jsx      Detected fallacy display
│       │   └── results/
│       │       └── MetricsGrid.jsx       Argumentation quality + calibration metadata
│       ├── store/
│       │   └── useDebateStore.js         Zustand global state
│       └── hooks/
│           ├── useSSE.js                 SSE connection with stable UUID + AbortController
│           └── useApiStatusStore.js      Provider health polling
│
├── tests/
│   ├── unit/                      Unit tests (168 passing)
│   ├── integration/               Integration tests
│   │   ├── test_novelty_features.py     HITL, trust weighting, decomposition, circuit breakers
│   │   └── test_real_api_health.py      Live provider diagnostics
│   ├── load/
│   │   └── test_concurrent_users.py     10-user concurrency suite
│   ├── benchmark_suite.py         FEVER benchmark: precision/recall/F1/ECE vs baselines
│   └── red_team_cases.py          Adversarial prompt injection + edge cases
│
├── scripts/
│   ├── download_fever.py          Download 200-claim FEVER balanced dataset
│   ├── run_benchmark_quick.py     10-claim sanity check (~5 min)
│   ├── run_ablation.py            4-config ablation study (50 claims × 4 configs)
│   └── generate_paper_metrics.py  Output LaTeX tables from benchmark_report.json
│
├── data/
│   └── fever_sample.json          100-claim benchmark dataset (50 TRUE / 50 FALSE)
│
├── paper/                         Published IJRASET research paper + drafts
├── progress/                      25-day development logs (D1–D25)
├── outputs/                       Benchmark results (fever_results.json, ablation_results.json)
│
├── .env                           API keys (gitignored)
├── requirements.txt               Pinned Python dependencies
├── pytest.ini                     Test configuration
└── .github/workflows/ci.yml       GitHub Actions CI
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/AyushDevadiga1/Insight-Swarm.git
cd InsightSwarm
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Set API keys

Create `.env` in the project root:

```env
# Required (at least one LLM provider)
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
TAVILY_API_KEY=tvly-...

# Optional (additional fallback providers)
OPENROUTER_API_KEY=sk-or-v1-...
CEREBRAS_API_KEY=csk_...

# Optional tuning
SEMANTIC_CACHE_ENABLED=1
RATE_LIMIT_GROQ=28
RATE_LIMIT_GEMINI=9
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_MODEL=gemini-2.5-flash
```

**Free keys:**
| Provider | Link | Free Tier |
|---|---|---|
| Groq | https://console.groq.com | 14,400 req/day |
| Gemini | https://aistudio.google.com | 250 req/day |
| Tavily | https://tavily.com | 1,000 searches/month |
| Cerebras | https://cloud.cerebras.ai | Free tier available |
| OpenRouter | https://openrouter.ai | Free tier available |

### 3. Start the backend

```bash
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 5. Submit a claim

Open http://localhost:5173, type any factual claim and press Enter. Example claims:

```
"Drinking coffee reduces the risk of type 2 diabetes"
"The James Webb Space Telescope launched in 2021"
"India has more than 1.4 billion people"
"5G towers cause COVID-19"
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Groq API key (primary LLM provider) |
| `GEMINI_API_KEY` | — | Google Gemini API key (secondary) |
| `TAVILY_API_KEY` | — | Tavily search API key |
| `OPENROUTER_API_KEY` | — | OpenRouter key (tertiary fallback) |
| `CEREBRAS_API_KEY` | — | Cerebras key (quaternary fallback) |
| `SEMANTIC_CACHE_ENABLED` | `1` | Enable/disable SQLite semantic cache |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `CEREBRAS_MODEL` | `llama3.1-8b` | Cerebras model name |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.1-8b-instruct` | OpenRouter model |
| `RATE_LIMIT_GROQ` | `28` | Groq calls per minute (buffer below 30) |
| `RATE_LIMIT_GEMINI` | `9` | Gemini calls per minute (buffer below 10) |
| `RATE_LIMIT_CEREBRAS` | `28` | Cerebras calls per minute |
| `RATE_LIMIT_OPENROUTER` | `18` | OpenRouter calls per minute |
| `ENABLE_OFFLINE_FALLBACK` | `false` | Return static message when all providers fail |

---

## Running Benchmarks

The benchmark suite evaluates InsightSwarm against two baselines on a 100-claim FEVER-derived dataset.

```bash
# Step 1: Download FEVER benchmark dataset
python scripts/download_fever.py
# → saves data/fever_sample.json (100 balanced claims)

# Step 2: Quick sanity check (10 claims, ~5 min)
python scripts/run_benchmark_quick.py

# Step 3: Full benchmark (100 claims, ~90 min on free-tier APIs)
python tests/benchmark_suite.py --n 100

# Step 4: Ablation study (4 configs × 50 claims, ~45 min)
python scripts/run_ablation.py --n 50

# Step 5: Generate LaTeX tables for paper submission
python scripts/generate_paper_metrics.py
```

**Outputs in `outputs/`:**

| File | Contents |
|---|---|
| `fever_results.json` | Per-claim InsightSwarm results |
| `baseline_results.json` | Keyword + single-agent baseline results |
| `benchmark_report.json` | Aggregated precision/recall/F1/ECE per system |
| `ablation_results.json` | ΔF1 per component removed |
| `table_main.tex` | Ready-to-paste LaTeX comparison table |
| `table_ablation.tex` | Ablation LaTeX table |

**Results (preliminary evaluation, 100-claim benchmark):**

| Metric | Keyword Baseline | Zero-shot LLM | InsightSwarm |
|---|---|---|---|
| F1 Score | 0.56 | 0.68 | **0.81** |
| Precision | 0.54 | 0.70 | **0.82** |
| Recall | 0.58 | 0.66 | **0.80** |
| Hallucination Rate | N/A | ~20% | **< 3%** |
| ECE (Calibration Error) | N/A | 0.31 | **0.24** |
| Median Latency | < 1s | ~5s | 47s |
| Monthly Infrastructure Cost | Rs. 0 | Rs. 0 | **Rs. 0** |

---

## Key Metrics

| Metric | Value |
|---|---|
| Codebase size | 15,600+ lines |
| Automated tests | 168 passing (100% pass rate) |
| Resolved defects across 25 dev days | 96 |
| Source hallucination rate | < 3% |
| Semantic cache similarity threshold | 0.85 cosine similarity |
| Type II hallucination threshold | 0.82 semantic similarity |
| HITL trigger threshold | PRO or CON verification rate < 30% |
| Moderator composite weights | Arg quality 30% + Verification 30% + Trust 20% + Consensus 20% |
| Confidence calibration boost cap | 0.25 (capped at 0.95 final) |
| Expected Calibration Error improvement | 0.31 → 0.24 |
| Average latency per claim | 35–60 seconds |
| Semantic cache hit latency | < 1 second |
| Claims processed per day (free tier) | ~960 |

---

## Development Trajectory

Built across 25 structured development days:

| Phase | Days | Key Deliverables | Tests | Defects Fixed |
|---|---|---|---|---|
| Foundation | 1 | Architecture docs, FreeLLMClient, thread-safe dual-provider fallback | 5/5 | 0 |
| Core agents | 2–3 | FactChecker (URL fetch, semantic match, hallucination classification), Moderator, XSS hardening | 35/35 | 25 |
| Stability | 4–6 | Pydantic v2 migration, semantic cache, tri-state API key manager | 38/38 | 29 |
| Scale | 7–12 | Cerebras + OpenRouter expansion, heterogeneous model pairing, 10-user concurrency testing | 80/80 | 18 |
| Modern stack | 13–20 | FastAPI + React migration, SSE streaming, LangGraph MemorySaver, Aurora glassmorphism UI | 120/120 | 16 |
| Novelty + Security | 21–25 | HITL via LangGraph interrupts, ArgumentationAnalyzer, AdaptiveCalibrator, FEVER benchmark, SSRF + rate-limit hardening | 168/168 | 8 |

**Three pivotal architectural decisions:**
1. **Day 2** — Discovery that word-count verdicts couldn't distinguish verified from fabricated sources → FactChecker-weighted composite verdict (core hallucination-reduction mechanism)
2. **Day 4** — Migration from fragile `TypedDict` to Pydantic `BaseModel` → eliminated all `KeyError` crashes pipeline-wide, enabled schema-strict `call_structured()` parsing
3. **Days 18–20** — Replaced Streamlit prototype with FastAPI + React → unlocked SSE streaming and HITL panel (the two most critical contributions)

Zero defects introduced in the final two days despite peak feature velocity in Days 21–23 — a direct result of maintaining test-driven discipline from Day 1.

---

## Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Full test suite
pytest tests/ -v --tb=short

# Integration: novelty features (HITL, trust weighting, decomposition)
pytest tests/integration/test_novelty_features.py -v

# Load: 10 concurrent users
pytest tests/load/test_concurrent_users.py -v

# Live API health check (requires real .env keys)
python tests/integration/test_real_api_health.py

# Red-team adversarial cases
python tests/red_team_cases.py
```

---

## Citation

```bibtex
@article{insightswarm2026,
  author    = {Gawas, Soham and Ghawali, Bhargav and Gawali, Mahesh and Devadiga, Ayush and Gujar, Shital},
  title     = {InsightSwarm: A Multi-Agent Adversarial Framework for Automated Fact-Checking with Real-Time Source Verification, Human-in-the-Loop Oversight, and Adaptive Confidence Calibration},
  journal   = {International Journal for Research in Applied Science and Engineering Technology (IJRASET)},
  year      = {2026},
  url       = {https://github.com/AyushDevadiga1/Insight-Swarm},
  note      = {Bharat College of Engineering, University of Mumbai}
}
```

---

## Acknowledgements

Guided by **Prof. Shital Gujar**, Department of CSE (AI & ML), Bharat College of Engineering, University of Mumbai.

Built on [LangGraph](https://langchain-ai.github.io/langgraph/), [FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/), [Groq](https://groq.com/), [Google Gemini](https://deepmind.google/technologies/gemini/), [Tavily](https://tavily.com/), [Pydantic](https://docs.pydantic.dev/), [sentence-transformers](https://www.sbert.net/), and [RapidFuzz](https://github.com/maxbachmann/RapidFuzz).

---

<div align="center">
  <sub>InsightSwarm — Bharat College of Engineering, University of Mumbai, 2026</sub>
</div>
