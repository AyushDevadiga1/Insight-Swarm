# InsightSwarm Implementation Plan

This plan comprehensively addresses **all 40 issues**: the 30 issues from the InsightSwarm Audit Report PDF, plus the 10 additional critical/high/medium issues (31-40) you provided. We will roll these out in 4 structured phases. 

## User Requirements / Interventions Required
While I can write the code for all 40 issues, there are a few specific tasks where **you** will need to intervene or provide resources:

1. **API Keys (Phase 2 & 4)**: 
   - We are adding **Tavily Search** (Issue #10). You will need to get a `TAVILY_API_KEY` and add it to your [.env](file:///c:/Users/hp/Desktop/InsightSwarm/.env) file.
   - For **LangSmith Evals** (Issue #24), you will need a `LANGCHAIN_API_KEY` in your [.env](file:///c:/Users/hp/Desktop/InsightSwarm/.env).
2. **CI/CD GitHub Actions (Phase 4)**:
   - I can write the `.github/workflows/ci.yml` file (Issue #26), but **you** will need to push it to GitHub and ensure Actions are enabled in your repository settings.
3. **Streamlit Cloud Deployment**:
   - For any Streamlit-specific memory or thread fixes (Issues #16, #17, #29), after I commit the code, **you** will need to trigger the redeployment on your Streamlit Cloud dashboard.

---

## Phase 1: Streamlit UX, Threading & Memory (Hotfixes)
These are the immediate, visible fixes for the web application's stability and speed.
### Tasks:
- [ ] **#16** Streamlit Graph Recompilation (`@st.cache_resource`)
- [ ] **#17** Concurrent Users State Bleeding (`MemorySaver` threading)
- [ ] **#27** UI Asynchronous Streaming (`st.status`, `st.write_stream`)
- [ ] **#29** Streamlit Moderator Chat Memory Leak (Cap session state history)
- [ ] **#28** Semantic Verdict Caching (SQLite Vector Store)
- [ ] **#30** User Feedback Loop (Thumbs up/down storage)

## Phase 2: Security, Stability & Typing (Core Hardening)
This phase ensures the application does not crash, rate-limits gracefully, validates inputs, and types states correctly.
### Tasks:
- [ ] **#21** Structured Output Parsing (`Pydantic` JSON mode for LLM outputs)
- [ ] **#32** Rate Limit Backoff Strategy (Add `tenacity` exponential backoff)
- [ ] **#34** DebateState `TypedDict` Definitions
- [ ] **#35** Logging Configuration (`logging.basicConfig`)
- [ ] **#36** Verdict Calculation Sanity Checks
- [ ] **#37** Input Validation on Claims
- [ ] **#38** Graceful Degradation (Fallback states if LLM providers go down)

## Phase 2: Core Logic Overhaul (Retrieval-Augmented Adversarial Debate)
This transforms the system from an LLM hallucination generator into a true RAG-grounded fact checker.

### Tasks:
- [ ] **#10, #11, #33** Retrieval-First Evidence (Integrate Tavily Search before debate starts)
- [ ] **#1** Mid-Debate Verification Gates (Failed sources block arguments natively)
- [ ] **#5** Heterogeneous Model Pairing (Pro: Llama 3.1 70B, Con: Gemini 2.0 Flash)
- [ ] **#2** FactChecker 2x Vote Weight Reduction (Score multiplier instead of debater vote)
- [ ] **#3** Source Verification decoupled from Truth Label
- [ ] **#4** Deterministic Composite Confidence Scores
- [ ] **#7** `INSUFFICIENT_EVIDENCE` Abstention Path
- [ ] **#31** Moderator Access to Verification Details (Pass full dictionaries to Moderator prompt)
- [ ] **#20** Debate Summariser (Context window truncation mid-debate)
- [ ] **#22** Gemini Fallback State Tagging (Mark `MIXED_MODELS` if failover occurs)
- [ ] **#40** Dynamic Round Tracking (Allow configuration beyond hardcoded 3)

## Phase 3: Fetching Upgrades & Pipeline Refinements
Scaling up the reliability and intelligence of FactChecker.

### Tasks:
- [ ] **#14** User-Agent Rotation / Browser Headers
- [ ] **#12** Differentiating `TIMEOUT` from `HALLUCINATED`
- [ ] **#15** Paywall / Login-Wall Detection (`PAYWALL_RESTRICTED` status)
- [ ] **#13** Semantic Embedding Matches instead of Fuzzy Keyword matches
- [ ] **#8** DomainTrustScorer (Weight arguments by domain authority)
- [ ] **#9** ClaimDecomposer Agent (Split multi-part claims before processing)
- [ ] **#6** Scientific Consensus Pre-Gate (Skip debate for settled science)

## Phase 4: Production Observability (Excluding CI/CD)
Ensuring persistence and continuous capability testing.
### Tasks:
- [ ] **#18** Resumable Debates (`SqliteSaver` / LangGraph Checkpointing)
- [ ] **#19** Human-in-the-loop Override (LangGraph `interrupt_before`)
- [ ] **#39** SQLite Metrics/Observability Deployment Logs
- [ ] **#23** Measured Hallucination Rate Benchmark
- [ ] **#24** LangSmith LLM Quality Eval Suite (Requires API Key)
- [ ] **#25** Adversarial / Red-Team Test Directory

## ON HOLD (Until Project is Production-Ready)
- [ ] **#26** CI/CD Pipeline (`.github/workflows`)


---
**Review Requests:**
Are you comfortable starting with the **Phase 1** Foundation tasks?
