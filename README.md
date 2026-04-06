# InsightSwarm 🦅

**Multi-Agent Fact-Checking through Adversarial Debate, Human-in-the-Loop Oversight, and Adaptive Confidence Calibration**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-stateful%20graph-orange)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A production-grade, research-quality fact-checking system where four specialised AI agents debate claims, verify sources in real-time, and converge on a calibrated verdict — with optional human intervention at any stage.

---

## What it does

You submit a claim. InsightSwarm:

1. **Decomposes** complex multi-part claims into atomic sub-claims
2. **Retrieves** real web evidence for both sides via Tavily search
3. **Debates** across 3 rounds: 🛡️ ProAgent argues TRUE, ⚔️ ConAgent argues FALSE
4. **Verifies** every cited URL with HTTP fetch, paywall detection, temporal alignment, semantic matching, and domain trust scoring
5. **Pauses for human review** if source confidence is low (HITL via LangGraph interrupts)
6. **Moderates** with a trust-weighted composite score and deep argumentation quality analysis
7. **Calibrates** confidence to correct systematic underconfidence using source quality and debate asymmetry signals
8. **Streams** every step live to a React frontend via Server-Sent Events

---

## Novel Research Contributions

| Contribution | Description |
|---|---|
| **HITL via LangGraph interrupts** | Graph pauses at `human_review` node; frontend renders source override UI; `/api/debate/resume/{id}` resumes execution with human corrections |
| **Argumentation quality analysis** | 10+ logical fallacy types detected per argument; citation quality and rhetoric scoring integrated into Moderator scoring |
| **Adaptive confidence calibration** | Detects and corrects underconfidence using geometric mean of source trust scores and debate asymmetry signals |
| **Trust-weighted multi-agent consensus** | Moderator composite = 30% argument quality + 30% verification rate + 20% trust score + 20% consensus pre-check |

---

## Architecture

```
User Claim
    │
    ▼
┌────────────────────────────────────────────────┐
│             LangGraph State Graph              │
│                                                │
│  consensus_check → [settled? skip → moderator]│
│        │ needs debate                          │
│        ▼                                       │
│  summarizer → pro_agent → con_agent ──┐        │
│       ▲           (× N rounds)        │ end    │
│       └───────────────────────────────┘        │
│                    │                           │
│            fact_checker ──[low conf?]──→ retry │
│                    │                           │
│  ══════ INTERRUPT: human_review ═════════════  │  ← HITL
│                    │                           │
│    moderator (+ argumentation + calibration)   │
│                    │                           │
│                 verdict                        │
└────────────────────────────────────────────────┘
         │
         ▼ SSE stream
   React Frontend (Vite)
```

### Agents

| Agent | Symbol | Role | Provider |
|---|---|---|---|
| ProAgent | 🛡️ | Argues claim is TRUE | Groq |
| ConAgent | ⚔️ | Argues claim is FALSE | Gemini |
| FactChecker | 🔬 | Verifies all cited sources | Groq |
| Moderator | ⚖️ | Delivers final verdict | Gemini |

---

## Stack

**Backend:** Python 3.11, FastAPI, LangGraph, Pydantic v2, SQLite (semantic cache + checkpointing), sentence-transformers  
**Frontend:** React 18, Vite, Zustand, SSE streaming, Lucide icons  
**LLMs:** Groq (Llama 3.3 70B), Google Gemini Flash, with circuit-breaker fallback chain  
**Search:** Tavily API (dual-sided evidence retrieval)

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/AyushDevadiga1/Insight-Swarm.git
cd InsightSwarm
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set API keys

Create `.env` in the root:

```env
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
TAVILY_API_KEY=tvly-...

# Optional
OPENROUTER_API_KEY=sk-or-v1-...
CEREBRAS_API_KEY=csk_...
SEMANTIC_CACHE_ENABLED=1
```

Get free keys:
- **Groq** → https://console.groq.com (14,400 req/day free)
- **Gemini** → https://aistudio.google.com (free tier)
- **Tavily** → https://tavily.com (1,000 searches/month free)

### 3. Start backend

```bash
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Start frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Running Benchmarks

The benchmark suite evaluates InsightSwarm against two baselines on a 100-claim FEVER-derived dataset.

```bash
# Quick sanity check (10 claims, ~5 min)
python scripts/run_benchmark_quick.py

# Full benchmark (100 claims, 1-2 hours)
python tests/benchmark_suite.py --n 100 --quick

# Ablation study (4 configs × 50 claims)
python scripts/run_ablation.py --n 50

# Generate LaTeX tables for paper
python scripts/generate_paper_metrics.py
```

Output files appear in `outputs/`:
- `fever_results.json` — per-claim InsightSwarm results
- `baseline_results.json` — keyword and single-agent baseline results
- `benchmark_report.json` — aggregated precision/recall/F1 per system
- `ablation_results.json` — ΔF1 per component removed
- `table_main.tex` — ready-to-paste LaTeX comparison table
- `table_ablation.tex` — ablation LaTeX table

---

## HITL (Human-in-the-Loop)

The HITL system triggers when source verification confidence falls below threshold:

1. Backend graph pauses at `interrupt_before=["human_review"]`
2. SSE emits `human_review_required` event with current verification results
3. React frontend auto-switches to Verdict tab and renders `HITLPanel`
4. Reviewer can override individual source statuses or set a verdict override
5. On submit: `POST /api/debate/resume/{thread_id}` resumes the graph
6. Final verdict arrives as normal `verdict` SSE event

---

## Project Structure

```
InsightSwarm/
├── api/
│   ├── server.py              # FastAPI app (SSE, HITL resume, health)
│   └── websocket_hitl.py      # WebSocket manager for HITL
├── src/
│   ├── agents/                # Pro, Con, FactChecker, Moderator
│   ├── core/models.py         # DebateState, AgentResponse (Pydantic)
│   ├── llm/client.py          # Multi-provider client with fallback chain
│   ├── novelty/
│   │   ├── argumentation_analysis.py   # Fallacy detection, quality scoring
│   │   └── confidence_calibration.py   # Adaptive confidence calibration
│   ├── orchestration/
│   │   ├── debate.py          # LangGraph graph + HITL interrupt
│   │   └── cache.py           # Semantic cache (SQLite + embeddings)
│   ├── monitoring/api_status.py
│   └── utils/                 # Tavily, claim decomposer, summarizer, URL tools
├── frontend/
│   └── src/
│       ├── App.jsx            # 3-panel shell (Sidebar | Main | StagePanel)
│       ├── components/
│       │   ├── hitl/HITLPanel.jsx       # HITL review UI
│       │   ├── debate/BattleHeader.jsx  # 🛡️ vs ⚔️ header
│       │   ├── debate/DebateArena.jsx   # Live debate thread
│       │   ├── pipeline/StagePanel.jsx  # Grok-style right panel
│       │   └── results/MetricsGrid.jsx  # Argumentation + calibration metrics
│       ├── store/useDebateStore.js      # Zustand state
│       └── hooks/useSSE.js             # SSE connection + HITL handler
├── tests/
│   └── benchmark_suite.py     # FEVER benchmark with baselines
├── scripts/
│   ├── download_fever.py      # FEVER dataset downloader
│   ├── run_ablation.py        # 4-config ablation study
│   ├── run_benchmark_quick.py # 10-claim sanity check
│   └── generate_paper_metrics.py  # LaTeX table generator
├── data/
│   └── fever_sample.json      # 100-claim benchmark dataset
├── paper/
│   └── demo_paper_v2.md       # ACL/EMNLP demo paper draft
└── .github/workflows/ci.yml   # GitHub Actions CI
```

---

## Key Metrics

| Metric | Value |
|---|---|
| Source hallucination rate | < 3% (internal validation) |
| Semantic cache threshold | 0.85 cosine similarity |
| HITL trigger threshold | pro or con verification rate < 30% |
| Moderator composite weights | Arg quality 30% + Verification 30% + Trust 20% + Consensus 20% |
| Average latency | ~30–60s per claim |
| Cache hit latency | < 1s |

---

## Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Full test suite
pytest tests/ -v --tb=short

# Red-team adversarial cases
python tests/red_team_cases.py
```

---

## Citation

```bibtex
@software{insightswarm2026,
  author    = {Gawas, Soham and Ghawali, Bhargav and Gawali, Mahesh and Devadiga, Ayush},
  title     = {InsightSwarm: Multi-Agent Fact-Checking with Adversarial Debate and HITL Oversight},
  year      = {2026},
  url       = {https://github.com/AyushDevadiga1/Insight-Swarm},
  note      = {Bharat College of Engineering, University of Mumbai}
}
```

---

## Acknowledgments

Guided by **Prof. Shital Gujar**, Department of CSE (AI & ML), Bharat College of Engineering.  
Built on LangGraph, FastAPI, React, Groq, Gemini, and Tavily.
