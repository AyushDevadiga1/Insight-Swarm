# InsightSwarm Dataflow Architecture Diagrams

**Date:** March 11, 2026  
**Project Status:** Production Ready ✅  
**Scope:** High-Level & Low-Level Dataflow Diagrams  

---

## 🏗️ HIGH-LEVEL SYSTEM ARCHITECTURE

### Simple Input → Processing → Output Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    INSIGHTSWARM SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  INPUT                  PROCESSING             OUTPUT            │
│  ┌────────┐            ┌──────────┐          ┌──────────┐       │
│  │ Claim  │            │  Debate  │          │ Verdict  │       │
│  │        │──────────→ │ System   │────────→ │          │       │
│  │String  │            │          │          │TRUE/FALSE│       │
│  │        │            │ + Source │          │PARTIALLY │       │
│  └────────┘            │ Verify   │          │          │       │
│                        └──────────┘          └──────────┘       │
│                                                                   │
│                      WITH CONFIDENCE SCORE                       │
│                      ✅ Verified Sources                         │
│                      ❌ Hallucinations Detected                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 HIGH-LEVEL COMPONENT INTERACTION

```
┌──────────────────────────────────────────────────────────────────┐
│                     INPUT: CLAIM                                  │
├──────────────────────────────────────────────────────────────────┤
│ Example: "Coffee prevents cancer"                                │
│ Type: String                                                     │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              DEBATE ORCHESTRATOR (LangGraph)                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        ROUND 1: Initial Arguments                        │    │
│  │  ┌──────────────────┐      ┌──────────────────┐         │    │
│  │  │   ProAgent       │      │   ConAgent       │         │    │
│  │  │ "Yes, evidence   │ ←→   │ "No, risks show │         │    │
│  │  │  shows benefits" │      │  increased rate" │         │    │
│  │  └──────────────────┘      └──────────────────┘         │    │
│  │         ↓                           ↓                    │    │
│  │    [Sources cited]             [Sources cited]          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        ROUND 2: Rebuttals                               │    │
│  │  Same agents challenge each other with new evidence     │    │
│  │         ↓                           ↓                    │    │
│  │    [More sources]              [More sources]          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        ROUND 3: Final Synthesis                         │    │
│  │  Final arguments incorporating all previous points      │    │
│  │         ↓                           ↓                    │    │
│  │    [Final sources]             [Final sources]         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│                    All Sources Collected                         │
│                    (Pro & Con combined)                          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              FACTCHECKER AGENT (Source Verification)             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  For Each Source URL:                                            │
│  1. HTTP GET with 10-second timeout                              │
│  2. Extract content (first 2000 chars)                           │
│  3. Fuzzy match against agent's claim (70% threshold)            │
│  4. Classify: ✅ VERIFIED | ❌ HALLUCINATED                      │
│                                                                   │
│  Pro Sources Verification Rate: X%                               │
│  Con Sources Verification Rate: Y%                               │
│                                                                   │
│  Hallucination Instances Detected:                               │
│  - 404 Not Found                                                 │
│  - Connection TimeOut                                            │
│  - Content Mismatch (<70%)                                       │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              WEIGHTED VERDICT CALCULATION                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  pro_score = pro_words × pro_verification_rate                   │
│  con_score = con_words × con_verification_rate                   │
│  fact_score = avg_verification_rate × 2  (2x weight)             │
│                                                                   │
│  final_ratio = (pro_score + con_score + fact_score) / total      │
│                                                                   │
│  if final_ratio > 0.65:    verdict = "TRUE"                      │
│  elif final_ratio < 0.35:  verdict = "FALSE"                     │
│  else:                     verdict = "PARTIALLY TRUE"            │
│                                                                   │
│  confidence = abs(final_ratio - 0.5) × 2                         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                    OUTPUT: VERDICT                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Results Object:                                                 │
│  {                                                               │
│    "claim": "Coffee prevents cancer",                            │
│    "verdict": "PARTIALLY TRUE",                                  │
│    "confidence": 0.72,                                           │
│    "pro_arguments": [...],                                       │
│    "con_arguments": [...],                                       │
│    "verification_results": [                                     │
│      {url: "...", status: "VERIFIED", confidence: 0.92},        │
│      {url: "...", status: "NOT_FOUND", confidence: 0.0}         │
│    ],                                                            │
│    "pro_verification_rate": 0.75,                                │
│    "con_verification_rate": 0.80                                 │
│  }                                                               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔍 LOW-LEVEL DETAILED DATAFLOW

### Complete Execution Path with Data Structures

```
╔════════════════════════════════════════════════════════════════════╗
║                    DETAILED DATAFLOW EXECUTION                     ║
╚════════════════════════════════════════════════════════════════════╝

STAGE 1: INITIALIZATION
═══════════════════════════════════════════════════════════════════

Input Claim: "Coffee reduces heart disease risk"
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ DebateState (TypedDict) Created                                 │
├─────────────────────────────────────────────────────────────────┤
│ {                                                                │
│   "claim": "Coffee reduces heart disease risk",                 │
│   "round": 1,                                                    │
│   "pro_arguments": [],                                           │
│   "con_arguments": [],                                           │
│   "pro_sources": [],                                             │
│   "con_sources": [],                                             │
│   "verification_results": None,                                  │
│   "pro_verification_rate": None,                                 │
│   "con_verification_rate": None,                                 │
│   "verdict": None,                                               │
│   "confidence": None                                             │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘


STAGE 2: ROUND 1 - INITIAL ARGUMENTS
═══════════════════════════════════════════════════════════════════

PRO_AGENT_NODE (state)
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. Build prompt with claim and current state                     │
├─────────────────────────────────────────────────────────────────┤
│    Prompt: "Argue that claim is TRUE. Cite sources."             │
│            + [Context from state]                                │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Call LLM (FreeLLMClient)                                      │
├─────────────────────────────────────────────────────────────────┤
│    - Try Groq API first                                          │
│    - Fallback to Gemini if needed                                │
│    - Rate limiting: 5 calls/min                                  │
│    - Timeout: 30 seconds                                         │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Parse Response                                                │
├─────────────────────────────────────────────────────────────────┤
│    Response: "Coffee contains polyphenols that reduce...         │
│              Mayo Clinic study: https://mayo.edu/coffee          │
│              Harvard Research: https://harvard.edu/study"        │
├─────────────────────────────────────────────────────────────────┤
│    Extract:                                                      │
│    - Argument text: "Coffee contains polyphenols..."            │
│    - Sources: [                                                  │
│        "https://mayo.edu/coffee",                               │
│        "https://harvard.edu/study"                              │
│      ]                                                           │
│    - Confidence: 0.85                                            │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Create AgentResponse (TypedDict)                              │
├─────────────────────────────────────────────────────────────────┤
│ {                                                                │
│   "agent": "PRO",                                                │
│   "round": 1,                                                    │
│   "argument": "Coffee contains polyphenols...",                 │
│   "sources": [                                                   │
│       "https://mayo.edu/coffee",                                │
│       "https://harvard.edu/study"                               │
│   ],                                                             │
│   "confidence": 0.85                                             │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Update DebateState                                            │
├─────────────────────────────────────────────────────────────────┤
│ pro_arguments: ["Coffee contains polyphenols..."]               │
│ pro_sources: [["https://mayo.edu/coffee",                       │
│               "https://harvard.edu/study"]]                      │
└─────────────────────────────────────────────────────────────────┘

        ↓ (Same process for ConAgent with opposite position)

CON_AGENT_NODE (state)
        ↓
        [Detailed flow same as ProAgent]
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ ConAgent provides counter-argument with sources                  │
│ con_arguments: ["However, excessive caffeine increases..."]      │
│ con_sources: [["https://ncbi.nlm.nih.gov/sleep",               │
│               "https://healthline.com/caffeine"]]                │
│ round incremented to 2                                           │
└─────────────────────────────────────────────────────────────────┘


STAGE 3: ROUND 2 & 3 (ITERATIONS)
═══════════════════════════════════════════════════════════════════

Loop while round <= 3:
  - ProAgent responds to ConAgent's arguments
  - ConAgent responds to ProAgent's arguments
  - Round increments after each ConAgent turn
  - Arguments accumulate in lists

Result after Round 3:
┌─────────────────────────────────────────────────────────────────┐
│ DebateState:                                                    │
│ {                                                                │
│   "pro_arguments": [                                             │
│       "argument_round_1",                                        │
│       "rebuttal_round_2",                                        │
│       "synthesis_round_3"                                        │
│   ],                                                             │
│   "con_arguments": [                                             │
│       "counter_round_1",                                         │
│       "rebuttal_round_2",                                        │
│       "synthesis_round_3"                                        │
│   ],                                                             │
│   "pro_sources": [                                               │
│       ["url1", "url2"],        // Round 1                        │
│       ["url3", "url4"],        // Round 2                        │
│       ["url5"]                 // Round 3                        │
│   ],                                                             │
│   "con_sources": [                                               │
│       ["urlA", "urlB"],        // Round 1                        │
│       ["urlC"],                // Round 2                        │
│       ["urlD", "urlE", "urlF"] // Round 3                        │
│   ],                                                             │
│   "round": 4  // Incremented after Round 3 ConAgent              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘


STAGE 4: FACTCHECKER VERIFICATION
═══════════════════════════════════════════════════════════════════

FACT_CHECKER_NODE (state)
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. Extract all sources from state                                │
├─────────────────────────────────────────────────────────────────┤
│ all_sources = [                                                  │
│   ("https://mayo.edu/coffee", "Coffee contains...", "PRO"),     │
│   ("https://harvard.edu/study", "Harvard study...", "PRO"),    │
│   ("https://ncbi.nlm.nih.gov/sleep", "Sleep study...", "CON"), │
│   ... (total 9 URLs)                                             │
│ ]                                                                │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. For Each URL: Verification Process                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ URL: "https://mayo.edu/coffee"                                   │
│ Claim: "Coffee contains polyphenols..."                         │
│                                                                   │
│ a) Fetch URL:                                                    │
│    ├─ requests.get(url, timeout=10)                              │
│    ├─ Status: 200 OK ✅                                          │
│    └─ Content: "...polyphenols reduce heart disease risk..."    │
│                                                                   │
│ b) Fuzzy Match:                                                  │
│    ├─ Agent claim: "Coffee contains polyphenols..."             │
│    ├─ Source text: "polyphenols reduce heart disease..."        │
│    ├─ Similarity: 87% (using fuzzywuzzy)                         │
│    └─ Result: ✅ VERIFIED (≥70% threshold)                      │
│                                                                   │
│ c) Create SourceVerification:                                    │
│    {                                                             │
│      "url": "https://mayo.edu/coffee",                          │
│      "status": "VERIFIED",                                       │
│      "confidence": 0.87,                                         │
│      "content_preview": "...polyphenols reduce...",             │
│      "error": None,                                              │
│      "agent_source": "PRO",                                      │
│      "matched_claim": "Coffee contains polypheno..."             │
│    }                                                             │
│                                                                   │
│ URL: "https://fake-cancer-cure.invalid"                          │
│                                                                   │
│ a) Fetch URL:                                                    │
│    ├─ requests.get(url, timeout=10)                              │
│    └─ Status: 404 Not Found ❌                                    │
│                                                                   │
│ b) Create SourceVerification:                                    │
│    {                                                             │
│      "url": "https://fake-cancer-cure.invalid",                 │
│      "status": "NOT_FOUND",                                      │
│      "confidence": 0.0,                                          │
│      "content_preview": None,                                    │
│      "error": "404 Not Found",                                   │
│      "agent_source": "PRO",                                      │
│      "matched_claim": None                                       │
│    }                                                             │
│                                                                   │
│ [Process continues for all 9 URLs]                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Calculate Verification Metrics                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ Total sources verified: 9                                        │
│ Verified count: 7                                                │
│ Hallucinated count: 2                                            │
│                                                                   │
│ Pro sources: 5 total, 4 verified (80%)                           │
│ Con sources: 4 total, 3 verified (75%)                           │
│                                                                   │
│ verification_rate = 7 / 9 = 78%                                  │
│ overall_confidence = avg(all confidence scores) = 0.74           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Update State with Verification Data                           │
├─────────────────────────────────────────────────────────────────┤
│ verification_results: [7 VERIFIED + 2 HALLUCINATED]              │
│ pro_verification_rate: 0.80                                      │
│ con_verification_rate: 0.75                                      │
└─────────────────────────────────────────────────────────────────┘


STAGE 5: VERDICT CALCULATION
═══════════════════════════════════════════════════════════════════

VERDICT_NODE (state)
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. Count argument words                                          │
├─────────────────────────────────────────────────────────────────┤
│ pro_words = 523  (total words across 3 arguments)                │
│ con_words = 487  (total words across 3 arguments)                │
│ total_words = 1010                                               │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Calculate weighted scores                                     │
├─────────────────────────────────────────────────────────────────┤
│ pro_score = 523 × 0.80 = 418.4                                   │
│ con_score = 487 × 0.75 = 365.25                                  │
│ fact_score = (0.80 + 0.75) / 2 × 2 = 1.55                        │
│                                                                   │
│ total_weighted = 418.4 + 365.25 = 783.65                         │
│ pro_ratio = 418.4 / 783.65 = 0.534                               │
│                                                                   │
│ [If no hallucinations: pro_ratio = 523/1010 = 0.518]             │
│ [Verification added: +0.016 boost to pro]                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Determine verdict                                             │
├─────────────────────────────────────────────────────────────────┤
│ final_ratio = 0.534                                              │
│                                                                   │
│ if 0.534 > 0.65:     verdict = "TRUE"      ✗ (No)              │
│ elif 0.534 < 0.35:   verdict = "FALSE"     ✗ (No)              │
│ else:                verdict = "PARTIALLY TRUE" ✓               │
│                                                                   │
│ confidence = 2 × abs(0.534 - 0.5) = 2 × 0.034 = 0.068           │
│          OR = 2 × abs(0.5 - 0.534) = round to 0.07 (7%)         │
│                                                                   │
│ (70% confidence that verdict is PARTIALLY TRUE)                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Return final state with verdict                               │
├─────────────────────────────────────────────────────────────────┤
│ state['verdict'] = "PARTIALLY TRUE"                              │
│ state['confidence'] = 0.70                                       │
└─────────────────────────────────────────────────────────────────┘


STAGE 6: OUTPUT RESPONSE
═══════════════════════════════════════════════════════════════════

Final Complete DebateState Object
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ {                                                                │
│   "claim": "Coffee reduces heart disease risk",                 │
│   "round": 4,                                                    │
│   "pro_arguments": [...3 arguments...],                          │
│   "con_arguments": [...3 arguments...],                          │
│   "pro_sources": [[url1,url2], [url3,url4], [url5]],           │
│   "con_sources": [[urlA,urlB], [urlC], [urlD,urlE,urlF]],      │
│   "verification_results": [                                      │
│     {url: url1, status: "VERIFIED", conf: 0.87, ...},          │
│     {url: url2, status: "VERIFIED", conf: 0.82, ...},          │
│     ...                                                          │
│     {url: "fake-cure", status: "NOT_FOUND", conf: 0.0, ...},  │
│     ...                                                          │
│   ],                                                             │
│   "pro_verification_rate": 0.80,                                 │
│   "con_verification_rate": 0.75,                                 │
│   "verdict": "PARTIALLY TRUE",                                   │
│   "confidence": 0.70                                             │
│ }                                                                │
│                                                                   │
│ SUMMARY:                                                        │
│ ✅ 7/9 sources verified                                          │
│ ❌ 2/9 sources hallucinated                                      │
│ 📊 78% overall verification rate                                 │
│ ⚖️  Verdict: PARTIALLY TRUE (70% confidence)                     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔗 DATA STRUCTURE RELATIONSHIPS

```
┌─────────────────────────────────────────────────────────────────┐
│                      DebateState (Main Container)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Debate History Section                                   │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │ • claim: str                                              │  │
│  │ • round: int (1-4)                                        │  │
│  │ • pro_arguments: List[str]                                │  │
│  │ • con_arguments: List[str]                                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ↕ Contains                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Sources Section                                           │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │ • pro_sources: List[List[str]]                            │  │
│  │   └─ Per round: ["url1", "url2", ...]                    │  │
│  │ • con_sources: List[List[str]]                            │  │
│  │   └─ Per round: ["urlA", "urlB", ...]                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ↕ Sent to FactChecker                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Verification Section                                      │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │ • verification_results: List[SourceVerification]          │  │
│  │   └─ Each: {url, status, confidence, error, ...}         │  │
│  │ • pro_verification_rate: float (0.0-1.0)                  │  │
│  │ • con_verification_rate: float (0.0-1.0)                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ↕ Results in                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Verdict Section                                           │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │ • verdict: str (TRUE|FALSE|PARTIALLY TRUE|ERROR)          │  │
│  │ • confidence: float (0.0-1.0)                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 CONTROL FLOW DIAGRAM

```
START
  ↓
[Accept Claim Input]
  ↓
[Initialize DebateState] ─────────────────┐
  ↓                                        │
[Round = 1]                                │
  ↓                                        │
┌─────────────────────────────────┐       │
│ DEBATE LOOP (Rounds 1-3)        │       │
├─────────────────────────────────┤       │
│ ┌──────────────┐  ┌───────────┐ │       │
│ │ ProAgent     │→ │ConAgent   │ │       │
│ │ Generate     │  │ Generate  │ │       │
│ │ Argument     │  │ Rebuttal  │ │       │
│ │ + Sources    │  │ + Sources │ │       │
│ └──────────────┘  └───────────┘ │       │
│   ↓                    ↓         │       │
│ [Add to              [Add to      │       │
│  pro_arguments]      con_arguments] │   │
│                                    │       │
│ [Increment Round]                  │       │
│                                    │       │
└─────────────────────────────────────┬─────┘
                                      │
                          [Is Round > 3?]
                              ↙           ↘
                            NO           YES
                             ↓             │
                          [Loop]           │
                             ↓             │
                          [Round++]        ↓
                                      [Exit Loop]
                                           ↓
                            [All Sources Collected]
                                           ↓
                    ┌─────────────────────────────┐
                    │  FACTCHECKER VERIFICATION    │
                    ├─────────────────────────────┤
                    │ For each URL:               │
                    │  1. Fetch content           │
                    │  2. Fuzzy match             │
                    │  3. Classify status         │
                    │  4. Calculate confidence    │
                    │  5. Store result            │
                    │                             │
                    │ Calculate:                  │
                    │  - pro_verification_rate    │
                    │  - con_verification_rate    │
                    │  - overall_confidence       │
                    │  - hallucination_count      │
                    └─────────────────────────────┘
                                           ↓
                    ┌─────────────────────────────┐
                    │  VERDICT CALCULATION        │
                    ├─────────────────────────────┤
                    │ 1. Count pro/con words      │
                    │ 2. Apply verification rates │
                    │ 3. Weight FactChecker 2x    │
                    │ 4. Calculate final ratio    │
                    │ 5. Determine verdict        │
                    │ 6. Calculate confidence     │
                    └─────────────────────────────┘
                                           ↓
                            [Return DebateState with
                             Verdict + Confidence]
                                           ↓
                                         OUTPUT
                                           ↓
                                         END
```

---

## 📊 DATA TRANSFORMATION SUMMARY

```
DebateState Evolution Through Stages:

INPUT ──→ DEBATE ──→ FACTCHECK ──→ VERDICT ──→ OUTPUT

Stage 1: Initial    Stage 2-4: Populated with    Stage 5: Enriched   Stage 6: Final
         Null values  arguments & sources         with verification   Complete

round: 1            round: 4                      round: 4            round: 4
proArgs: []         proArgs: [3 items]            proArgs: [3 items]  proArgs: [3 items]
conArgs: []         conArgs: [3 items]            conArgs: [3 items]  conArgs: [3 items]
sources: [][]       sources: populated            sources: populated  sources: populated
verify: None        verify: None                  verify: [7 items]   verify: [7 items]
rates: None         rates: None                   rates: 0.80/0.75    rates: 0.80/0.75
verdict: None       verdict: None                 verdict: None       verdict: "PARTIALLY TRUE"
confid: None        confid: None                  confid: None        confid: 0.70
```

---

## 🎯 COMPONENT COMMUNICATION MAP

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                            │
│                  (DebateOrchestrator)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Manages:                                                        │
│  ┌────────────┐    ┌─────────────────┐    ┌──────────────┐     │
│  │ProAgent    │───→│FreeLLMClient    │←───│ConAgent      │     │
│  └────────────┘    │  ├─Groq (main)  │    └──────────────┘     │
│         ↑          │  └─Gemini(bkp)  │           ↑               │
│         │          └─────────────────┘           │               │
│         │  Shares LLM client                      │               │
│         └──────────────────────────────────────────┘              │
│                                                                   │
│  Also manages:                                                   │
│  ┌──────────────┐                 ┌───────────────┐             │
│  │FactChecker   │←---- State ─────→│ Verdict       │             │
│  │  ├─URL Fetch │   (updated by     │ Calculation  │             │
│  │  ├─Fuzzy     │    sources)        │   (weighted │             │
│  │  └─Classify  │                 │  consensus)  │             │
│  └──────────────┘                 └───────────────┘             │
│         ↑                                    ↑                    │
│         └────────── DebateState ────────────┘                    │
│          (central data structure flowing)                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ EXECUTION CHECKLIST

```
┌─ Pre-Execution ────────────────────────────────────┐
│ ✅ Dependencies installed (groq, gemini, requests) │
│ ✅ API keys configured                             │
│ ✅ Rate limiters initialized                       │
│ ✅ Logging configured                              │
└────────────────────────────────────────────────────┘
                           ↓
┌─ Execution Phase 1: Debate ────────────────────────┐
│ ✅ Create DebateState                              │
│ ✅ ProAgent generates 3 arguments                   │
│ ✅ ConAgent generates 3 rebuttals                   │
│ ✅ All sources collected (mixed valid & fake)      │
│ ✅ State fully populated with arguments/sources    │
└────────────────────────────────────────────────────┘
                           ↓
┌─ Execution Phase 2: Verification ──────────────────┐
│ ✅ FactChecker extracts all URLs                   │
│ ✅ Fetch each URL with timeout protection          │
│ ✅ Fuzzy match content against claims              │
│ ✅ Classify: VERIFIED | HALLUCINATED               │
│ ✅ Calculate verification rates per agent          │
│ ✅ Update state with verification_results          │
└────────────────────────────────────────────────────┘
                           ↓
┌─ Execution Phase 3: Verdict ───────────────────────┐
│ ✅ Count argument words                             │
│ ✅ Apply verification weighting                     │
│ ✅ Calculate final weighted ratio                   │
│ ✅ Determine verdict: TRUE | FALSE | PARTIAL       │
│ ✅ Calculate confidence score                       │
│ ✅ Return complete final result                     │
└────────────────────────────────────────────────────┘
```

---

**Generated:** March 11, 2026  
**Diagrams reflect:** Complete Day 1 → Day 2 implementation  
**Status:** ✅ All system components documented
