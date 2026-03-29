# D16 Progress Report: Performance, Stability, and Full UI Redesign

**Date:** March 29, 2026
**Project:** InsightSwarm

## 1. Overview of Changes Made Today
Today's session involved a drastic overhaul of the platform's backend stability, frontend reactivity, and visual aesthetics. We executed Batches 1 through 5 of the stabilization plan:

### Backend & Core Stability
*   **Source Fallback**: Integrated `GoogleCSERetriever` as an automatic failover when Tavily runs out of quota (HTTP 429).
*   **Hallucination Stripping**: Added pre-validation to `_fact_checker_node` in `debate.py` to intercept and strip out any URLs fabricated by the LLM agents before they hit the FactChecker, saving massive overhead.
*   **Rate Limit Concurrency**: Refactored `client.py` to use accurate per-provider rate limits (e.g. Groq 28/min, Gemini 13/min) and lowered cooldown timeouts to 120s max.

### Frontend Connections & State
*   **SSE Race Condition Fix**: Completely refactored `useSSE.js` to rely on a stable UUID `runId` passed down from `App.jsx`, preventing infinite auto-reconnect loops and fixing the frozen heartbeat.
*   **Aborting Stale Polls**: Swapped `AbortSignal.timeout` with `AbortController` in `useApiStatusStore.js` for better browser compatibility and fewer console errors on rapid unmounts.

### Full Premium UI Redesign & New Features
*   **LLM-based Fallacy Detection**: Updated the Moderator to actively flag logical fallacies.
*   **Progressive Hover Cards**: Transformed citations in `AgentBubble.jsx` into interactive chips that reveal verification status and trust tier on hover.
*   **Aurora Glassmorphism Theme**: Created `AuroraBackground.jsx` and completely redesigned `index.css` for a high-end, animated, glass-like aesthetic with Inter/Fira Code Google Fonts.
*   **New Premium Components**: Added `SubClaimBanner.jsx`, `FallacyPanel.jsx`, and a cinematic `LoadingOrb.jsx` to polish the user experience.

---

## 2. Git Commit Plan

Given the sheer volume of architectural changes, we have implemented an atomic "per-file" commit strategy to guarantee absolute traceability. 

Instead of broad functional batches, every single modified and created file receives its own distinct, highly descriptive commit message matching conventional spec (e.g., `feat`, `fix`, `style`, `build`).

This entire per-file commit chain is automated and mapped directly inside the `scripts/commit_d16.bat` file, ensuring perfect granularity across the 20+ overhauled modules.
