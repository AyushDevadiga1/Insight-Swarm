"""
FactChecker - Verifies sources cited during debate using deterministic checks.
"""
import logging
import requests
import threading
from typing import List, Dict, Optional, Tuple, Any
from src.agents.base import BaseAgent, DebateState
from src.core.models import SourceVerification, AgentResponse
import concurrent.futures
import re
from src.utils.temporal_verifier import TemporalVerifier
from src.utils.trust_scorer import TrustScorer

logger = logging.getLogger(__name__)

class FactChecker(BaseAgent):
    """
    Agent responsible for verifying sources cited in the debate.
    """
    
    def __init__(self, llm_client, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role = "FACT_CHECKER"
        self.preferred_provider = preferred_provider or "groq"
        from src.config import FactCheckerConfig
        self.url_timeout = FactCheckerConfig.URL_TIMEOUT
        self._fuzz_init_lock = threading.Lock()
        self.fuzz = None
        self._initialize_fuzzy_support()
        
        # Phase 3: Semantic Verification
        self.model = None
        self._initialize_semantic_model()

    def _initialize_semantic_model(self):
        try:
            from src.utils.embedding import get_embedding_model
            self.model = get_embedding_model()
        except Exception as e:
            logger.warning(f"Failed to initialize sentence-transformers: {e}")
    
    def _initialize_fuzzy_support(self):
        with self._fuzz_init_lock:
            try:
                from rapidfuzz import fuzz
                self.fuzz = fuzz
            except ImportError:
                logger.warning("rapidfuzz not installed - fuzzy matching disabled")
                self.fuzz = None

    def generate(self, state: DebateState) -> AgentResponse:
        """Verify all sources cited and return structured results."""
        logger.info("FactChecker verifying all debate sources...")
        
        all_sources = []
        # PRO sources
        for i, round_sources in enumerate(state.pro_sources):
            argument = state.pro_arguments[i] if i < len(state.pro_arguments) else ""
            for url in round_sources:
                all_sources.append((url, "PRO", argument))
        # CON sources
        for i, round_sources in enumerate(state.con_sources):
            argument = state.con_arguments[i] if i < len(state.con_arguments) else ""
            for url in round_sources:
                all_sources.append((url, "CON", argument))
                
        results = []
        if all_sources:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self._verify_url, url, agent, argument): url for url, agent, argument in all_sources}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        if res is not None:
                            results.append(res)
                    except Exception as e:
                        logger.error(f"Failed to verify {futures[future]}: {e}")

        # Calculate metrics for the response reasoning/argument
        pro_verified = sum(1 for r in results if r.agent_source == "PRO" and r.status == "VERIFIED")
        con_verified = sum(1 for r in results if r.agent_source == "CON" and r.status == "VERIFIED")
        
        return AgentResponse(
            agent="FACT_CHECKER",
            round=state.round,
            argument=f"Source verification complete. PRO verification: {pro_verified}, CON verification: {con_verified}.",
            sources=[r.url for r in results],
            confidence=1.0,
            metrics={
                "verification_results": [r.to_dict() for r in results],
                "pro_rate": pro_verified / len([r for r in results if r.agent_source == "PRO"]) if any(r.agent_source == "PRO" for r in results) else 0.0,
                "con_rate": con_verified / len([r for r in results if r.agent_source == "CON"]) if any(r.agent_source == "CON" for r in results) else 0.0
            }
        )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """Requirement for BaseAgent, though FactChecker is deterministic."""
        return "Verify the sources in the current debate state."

    def _verify_url(self, url: str, agent: str, claim: str = "") -> SourceVerification:
        """Deterministic URL verification with validation.

        If the input is not a valid URL (no scheme/netloc), return an
        INVALID_URL result instead of attempting to fetch it. This
        avoids noisy errors like "No connection adapters were found".
        """
        from urllib.parse import urlparse

        try:
            # Defensive: ensure we only deal with strings
            if not isinstance(url, str):
                logger.debug("_verify_url received non-str url: %r", url)
                return SourceVerification(url=str(url), status="INVALID_URL", agent_source=agent, error="Non-string URL")

            original = url
            url = url.strip()
            logger.debug("_verify_url called with url=%r (agent=%s)", url, agent)

            parsed = urlparse(url)
            # Require explicit http/https schemes and a network location
            if not (parsed.scheme in ("http", "https") and parsed.netloc):
                logger.debug("Invalid URL format detected (no scheme/netloc): %r parsed=%s", url, parsed)
                return SourceVerification(
                    url=original,
                    status="INVALID_URL",
                    agent_source=agent,
                    error="Invalid URL format: no scheme or host"
                )

            # Safe to fetch
            USER_AGENTS = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
            ]
            import random
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            resp = requests.get(
                url,
                timeout=self.url_timeout,
                allow_redirects=True,
                headers=headers
            )
            
            # Detect paywalls or access restrictions
            paywall_indicators = ['subscribe to read', 'paywall', 'premium content', 'login to continue', 'subscription required', 'members only']
            if any(indicator in resp.text.lower() for indicator in paywall_indicators):
                 return SourceVerification(
                    url=url,
                    status="PAYWALL_RESTRICTED",
                    agent_source=agent,
                    error="Content is behind a paywall or requires login"
                )

            if resp.status_code == 200:
                content = resp.text
                
                # Only apply temporal verification when the claim explicitly
                # references a 4-digit year.  Generic claims have no temporal
                # constraint so skipping is correct.
                if claim and re.search(r'\b(?:19|20)\d{2}\b', claim):
                    tv = TemporalVerifier()
                    is_aligned, msg = tv.verify_alignment(claim, content)
                    if not is_aligned:
                        return SourceVerification(
                            url=url,
                            status="CONTENT_MISMATCH",
                            agent_source=agent,
                            error=msg,
                            content_preview=content[:200]
                        )
                
                # Phase 3: Semantic Verification
                if self.model and claim:
                    # Split content into sentences for more granular matching
                    sentences = re.split(r'(?<=[.!?])\s+', content)
                    if sentences:
                        # Extract sentences that contain ANY relevant keywords from the claim to save time
                        keywords = set(re.findall(r'\w+', claim.lower()))
                        candidate_sentences = [
                            s for s in sentences 
                            if len(s) > 20 and any(kw in s.lower() for kw in keywords)
                        ]
                        
                        if candidate_sentences:
                            from sklearn.metrics.pairwise import cosine_similarity
                            import numpy as np
                            
                            claim_embedding = self.model.encode([claim])
                            sentence_embeddings = self.model.encode(candidate_sentences)
                            
                            similarities = cosine_similarity(claim_embedding, sentence_embeddings)[0]
                            max_sim = np.max(similarities)
                            
                            if max_sim > 0.75:
                                trust_score = TrustScorer.get_score(url)
                                trust_level = TrustScorer.get_tier_label(trust_score)

                                return SourceVerification(
                                    url=url,
                                    status="VERIFIED",
                                    agent_source=agent,
                                    confidence=float(max_sim),
                                    trust_score=trust_score,
                                    trust_tier=trust_level,
                                    content_preview=candidate_sentences[np.argmax(similarities)][:200]
                                )
                            else:
                                return SourceVerification(
                                    url=url,
                                    status="CONTENT_MISMATCH",
                                    agent_source=agent,
                                    error=f"Semantic similarity tool low: {max_sim:.2f}",
                                    content_preview=content[:200]
                                )

                trust_score = TrustScorer.get_score(url)
                trust_level = TrustScorer.get_tier_label(trust_score)

                return SourceVerification(
                    url=url,
                    status="VERIFIED",
                    agent_source=agent,
                    confidence=1.0,
                    trust_score=trust_score,
                    trust_tier=trust_level,
                    content_preview=content[:200]
                )
            return SourceVerification(url=url, status="NOT_FOUND", agent_source=agent, error=f"HTTP {resp.status_code}")
        except requests.Timeout:
            return SourceVerification(url=str(url), status="TIMEOUT", agent_source=agent, error="Request timeout")
        except requests.RequestException as e:
            # Log debug to help diagnose noisy adapter errors
            logger.debug("requests exception for url=%r: %s", url, e)
            return SourceVerification(url=str(url), status="ERROR", agent_source=agent, error=str(e))
        except Exception as e:
            logger.exception("Unexpected error verifying url=%r", url)
            return SourceVerification(url=str(url), status="ERROR", agent_source=agent, error=str(e))
