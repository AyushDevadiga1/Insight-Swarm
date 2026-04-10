# Proposed Architectural Enhancements for InsightSwarm

While the current implementation correctly fulfills the requirements of a multi-agent truth-verification system, incorporating the following modern architectural strategies would advance the capability from a robust research prototype to an enterprise-grade production platform. 

None of these impact the fundamental `claim -> debate -> verify` logical loop; rather, they scale how efficiently that loop executes.

---

### 1. Vector Database for Semantic Cache (Replaces `orchestration/cache.py`)
**Current:** Raw `numpy` cosine similarity array. It parses bytes into tensors per cache hit, which operates at `O(N)` linear complexity. As the database of debate transcripts grows to thousands, `get_verdict()` will suffer noticeable CPU bottlenecks.
**Enhancement:** Migrate the cache store to a standalone embedding engine like **FAISS** (Facebook AI Similarity Search) or **ChromaDB**. 
**Benefit:** Sub-millisecond similarity lookups via Approximate Nearest Neighbor (ANN) indexing over millions of vector embeddings.

### 2. Fully Asynchronous LLM I/O Operations
**Current:** `FreeLLMClient` executes HTTP requests synchronously (as evidenced by blocking operations via `time.sleep` and internal delays). The execution thread halts entirely, blocking the CPU while waiting for Groq or Gemini's response over the network.
**Enhancement:** Rewrite `client.py` using `asyncio` and `httpx.AsyncClient`. Update `DebateOrchestrator` nodes to use `arun()` asynchronous graph traversal where possible.
**Benefit:** Drastic improvements in throughput. A single server node could orchestrate thousands of concurrent debates without spawning thousands of heavy OS threads.

### 3. Asymmetric Job Queues for Long-Running Debates
**Current:** Debates are executed inline within the `/stream` API endpoint via SSE (Server-Sent Events). If a debate requires 3+ minutes—and the user refreshes the page or their WiFi drops—the HTTP connection drops, effectively terminating the ongoing analysis node.
**Enhancement:** Decouple debate execution using a message broker like **Redis / Celery**.
* Upon submitting a claim, the server queues the job and instantly returns a `thread_id`.
* The background worker runs the heavy LangGraph execution safely.
* The frontend simply connects via WebSockets to listen to broadcasts for that arbitrary `thread_id` allowing for safe disconnects and resumes.

### 4. Direct Information-Retrieval Models
**Current:** The system combines Tavily Search with open-weight models (Groq/Gemini).
**Enhancement:** Introduce **Perplexity API (`sonar-pro`)** exclusively for the FactCheck or Moderator tiers. Perplexity inherently conducts internet grounding and citation correlation at the model-layer, bypassing the "retrieve-then-read" bottleneck.
**Benefit:** Fewer hallucinations in the Moderator consensus evaluation stage and denser verification citation data.

### 5. Multi-Node Deployment Strategy
**Current:** Global singleton configurations (like tracker singletons or disk-bound checkpointers) bind the orchestrator to a single server instance.
**Enhancement:** Implement distributed KV stores (like Redis) for the LangGraph Checkpointer (`MemorySaver_v2`).
**Benefit:** The system can be deployed across a Kubernetes cluster via multiple load-balanced pods without losing debate state.
