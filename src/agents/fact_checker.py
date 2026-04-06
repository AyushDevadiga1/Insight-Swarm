"""
src/agents/fact_checker.py — Final production version. All batches applied.
"""
import logging, random, re, threading, time, atexit as _atexit
from src.novelty import get_contradiction_detector

from typing import List, Optional, Tuple, Any
from urllib.parse import urlparse

import requests
import concurrent.futures
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import SourceVerification
from src.utils.temporal_verifier import TemporalVerifier
from src.utils.trust_scorer import TrustScorer
from src.config import FactCheckerConfig

logger = logging.getLogger(__name__)

_VERIFY_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="insightswarm_verify")
_atexit.register(_VERIFY_POOL.shutdown, wait=False)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
]


class FactChecker(BaseAgent):
    def __init__(self, llm_client, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role               = "FACT_CHECKER"
        self.preferred_provider = preferred_provider or "groq"
        self.url_timeout        = FactCheckerConfig.URL_TIMEOUT
        self._fuzz_init_lock    = threading.Lock()
        self.fuzz               = None
        self._initialize_fuzzy_support()
        self.model = None
        self._initialize_semantic_model()

    def _initialize_semantic_model(self):
        try:
            from src.utils.embedding import get_embedding_model
            self.model = get_embedding_model()
        except Exception as e:
            logger.warning("Failed to initialize sentence-transformers: %s", e)

    def _initialize_fuzzy_support(self):
        with self._fuzz_init_lock:
            try:
                from rapidfuzz import fuzz
                self.fuzz = fuzz
            except ImportError:
                logger.warning("rapidfuzz not installed - fuzzy matching disabled")

    def generate(self, state: DebateState) -> AgentResponse:
        logger.info("FactChecker verifying all debate sources...")
        all_sources: List[Tuple[str, str, str]] = []

        for i, round_sources in enumerate(state.pro_sources):
            argument = state.pro_arguments[i] if i < len(state.pro_arguments) else ""
            for url in round_sources:
                if isinstance(url, str) and url.strip():
                    all_sources.append((url, "PRO", argument))

        for i, round_sources in enumerate(state.con_sources):
            argument = state.con_arguments[i] if i < len(state.con_arguments) else ""
            for url in round_sources:
                if isinstance(url, str) and url.strip():
                    all_sources.append((url, "CON", argument))

        results: List[SourceVerification] = []

        if all_sources:
            claim_embedding = None
            if self.model:
                try:
                    claim_embedding = self.model.encode([state.claim])
                except Exception as e:
                    logger.warning("Failed to pre-encode claim: %s", e)

            futures = {
                _VERIFY_POOL.submit(self._verify_url, url, agent, state.claim, claim_embedding, state): url
                for url, agent, _ in all_sources
            }

            try:
                for future in concurrent.futures.as_completed(futures, timeout=60):
                    url = futures[future]
                    try:
                        res = future.result(timeout=15)
                        if res is not None:
                            results.append(res)
                    except concurrent.futures.TimeoutError:
                        logger.warning("URL verification timed out: %s", url)
                        results.append(SourceVerification(url=url, status="TIMEOUT", agent_source=None, error="Verification timed out"))
                    except Exception as e:
                        logger.error("Failed to verify %s: %s", url, e)
                        results.append(SourceVerification(url=url, status="ERROR", agent_source=None, error=str(e)))
            except concurrent.futures.TimeoutError:
                logger.warning("FactChecker batch verification timed out after 60s")
                for future, url in futures.items():
                    if not future.done():
                        results.append(SourceVerification(url=url, status="TIMEOUT", agent_source=None, error="Batch timeout"))

        pro_results  = [r for r in results if r.agent_source == "PRO"]
        con_results  = [r for r in results if r.agent_source == "CON"]
        pro_verified = sum(1 for r in pro_results if r.status == "VERIFIED")
        con_verified = sum(1 for r in con_results if r.status == "VERIFIED")
        total        = len(results)
        overall_confidence = (pro_verified + con_verified) / total if total > 0 else 0.0
        pro_rate = (pro_verified / len(pro_results)) if pro_results else 0.0
        con_rate = (con_verified / len(con_results)) if con_results else 0.0

        
        # NOVELTY: Evidence Contradiction Detection
        from src.novelty import get_contradiction_detector
        detector = get_contradiction_detector()
        contradiction_analysis = detector.detect_contradictions(results, state.claim)
        
        return AgentResponse(
            agent="FACT_CHECKER",
            round=state.round,
            argument=f"Source verification complete. PRO: {pro_verified}/{len(pro_results)} verified. CON: {con_verified}/{len(con_results)} verified.",
            sources=[r.url for r in results],
            confidence=round(overall_confidence, 3),
            metrics={"verification_results": [r.to_dict() for r in results], "pro_rate": pro_rate, "con_rate": con_rate, "contradictions": contradiction_analysis},
        )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        return "Verify the sources in the current debate state."

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1),
           retry=retry_if_exception_type(requests.exceptions.ConnectionError), reraise=True)
    def _fetch_url(self, url: str) -> requests.Response:
        return requests.get(url, timeout=(3.0, self.url_timeout), allow_redirects=True, stream=True,
                            headers={"User-Agent": random.choice(_USER_AGENTS),
                                     "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                                     "Accept-Language": "en-US,en;q=0.5", "DNT": "1",
                                     "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1"})

    def _verify_url(self, url: str, agent: str, claim: str = "",
                    claim_embedding: Any = None, state: Optional[DebateState] = None) -> SourceVerification:
        try:
            if not isinstance(url, str):
                return SourceVerification(url=str(url), status="INVALID_URL", agent_source=agent, error="Non-string URL")
            url = url.strip()
            parsed = urlparse(url)
            if not (parsed.scheme in ("http", "https") and parsed.netloc):
                return SourceVerification(url=url, status="INVALID_URL", agent_source=agent, error="Invalid URL format")

            netloc = parsed.netloc.lower()
            if "localhost" in netloc or "127.0.0.1" in netloc or not netloc.isascii():
                return SourceVerification(url=url, status="INVALID_URL", agent_source=agent, error="Invalid or restricted domain")

            is_tavily_source = False
            if state:
                for pool in [state.evidence_sources, state.pro_evidence, state.con_evidence]:
                    if not pool: continue
                    for item in pool:
                        if item.get("url") == url:
                            is_tavily_source = True
                            if item.get("content"):
                                return self._process_content(url, item["content"], agent, claim, claim_embedding)

            resp = self._fetch_url(url)
            raw_bytes = b""
            start_time = time.time()
            for chunk in resp.iter_content(chunk_size=8192):
                if time.time() - start_time > self.url_timeout:
                    break
                raw_bytes += chunk
                if len(raw_bytes) >= 51200: break
            content_text = raw_bytes.decode("utf-8", errors="ignore")

            if any(ind in content_text.lower() for ind in
                   ["subscribe to read", "paywall", "premium content", "login to continue",
                    "subscription required", "members only"]):
                return SourceVerification(url=url, status="PAYWALL_RESTRICTED", agent_source=agent, error="Content behind paywall")

            if resp.status_code == 200:
                return self._process_content(url, content_text, agent, claim, claim_embedding)
            
            if is_tavily_source and resp.status_code == 404:
                return SourceVerification(url=url, status="CONTENT_MISMATCH", agent_source=agent, error="Source unavailable at verification time")
            return SourceVerification(url=url, status="NOT_FOUND", agent_source=agent, error=f"HTTP {resp.status_code}")

        except requests.Timeout:
            return SourceVerification(url=str(url), status="TIMEOUT", agent_source=agent, error="Request timeout")
        except requests.RequestException as e:
            return SourceVerification(url=str(url), status="ERROR", agent_source=agent, error=str(e))
        except Exception as e:
            logger.exception("Unexpected error verifying %r", url)
            return SourceVerification(url=str(url), status="ERROR", agent_source=agent, error=str(e))

    def _process_content(self, url: str, content: str, agent: str,
                         claim: str = "", claim_embedding: Any = None) -> SourceVerification:
        if claim and re.search(r"\b(?:19|20)\d{2}\b", claim):
            is_aligned, msg = TemporalVerifier().verify_alignment(claim, content)
            if not is_aligned:
                return SourceVerification(url=url, status="CONTENT_MISMATCH", agent_source=agent,
                                          error=msg, content_preview=content[:200])

        if self.model and claim:
            sentences = re.split(r"(?<=[.!?])\s+", content)
            keywords  = set(re.findall(r"\w+", claim.lower()))
            scored    = [(sum(1 for kw in keywords if kw in s.lower()), s)
                         for s in sentences if 30 <= len(s) <= 1000]
            scored    = [(sc, s) for sc, s in scored if sc > 0]
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [s for _, s in scored[:5]]

            if candidates:
                from sklearn.metrics.pairwise import cosine_similarity
                import numpy as np
                query_emb     = claim_embedding if claim_embedding is not None else self.model.encode([claim])
                sims          = cosine_similarity(query_emb, self.model.encode(candidates))[0]
                max_sim       = float(np.max(sims))
                trust_score   = TrustScorer.get_score(url)
                trust_level   = TrustScorer.get_tier_label(trust_score)
                threshold     = FactCheckerConfig.SEMANTIC_THRESHOLD
                if max_sim > threshold:
                    return SourceVerification(url=url, status="VERIFIED", agent_source=agent,
                                              confidence=max_sim, trust_score=trust_score, trust_tier=trust_level,
                                              content_preview=candidates[int(np.argmax(sims))][:200])
                return SourceVerification(url=url, status="CONTENT_MISMATCH", agent_source=agent,
                                          error=f"Semantic similarity too low: {max_sim:.2f}", content_preview=content[:200])

        trust_score = TrustScorer.get_score(url)
        trust_level = TrustScorer.get_tier_label(trust_score)
        return SourceVerification(url=url, status="VERIFIED", agent_source=agent,
                                  confidence=1.0, trust_score=trust_score, trust_tier=trust_level,
                                  content_preview=content[:200])
