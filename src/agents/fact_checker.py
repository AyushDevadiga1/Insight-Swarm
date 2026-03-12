"""
FactChecker - Verifies sources cited by ProAgent and ConAgent

This agent is responsible for validating URLs cited by debate agents,
comparing source content to claims, and detecting hallucinated sources.
"""

import logging
import requests
import threading
from typing import List, Dict, Optional, Tuple
from src.agents.base import BaseAgent, DebateState
from typing import TypedDict

logger = logging.getLogger(__name__)


class SourceVerification(TypedDict):
    """
    Result of verifying a single source.
    
    Attributes:
        url: The URL that was verified
        status: One of "VERIFIED", "NOT_FOUND", "CONTENT_MISMATCH", "TIMEOUT"
        confidence: 0.0-1.0 score of how well source matches claims
        content_preview: First 500 chars of fetched content (if available)
        error: Error message if verification failed
        agent_source: Which agent cited this ("PRO" or "CON")
        matched_claim: The specific claim text that was matched against
    """
    url: str
    status: str
    confidence: float
    content_preview: Optional[str]
    error: Optional[str]
    agent_source: str
    matched_claim: Optional[str]


class FactCheckerResponse(TypedDict):
    """
    Response from FactChecker agent.
    
    Attributes:
        agent: Always "FACT_CHECKER"
        verification_results: List of SourceVerification results
        verified_count: Number of sources successfully verified
        hallucinated_count: Number of sources that are hallucinated/invalid
        verification_rate: Percentage of sources verified (0.0-1.0)
        overall_confidence: Overall confidence in source verification (0.0-1.0)
    """
    agent: str
    verification_results: List[SourceVerification]
    verified_count: int
    hallucinated_count: int
    verification_rate: float
    overall_confidence: float


class FactChecker(BaseAgent):
    """
    Agent responsible for verifying sources cited in the debate.
    
    Tasks:
    - Extract all URLs from ProAgent and ConAgent responses
    - Attempt to fetch each URL with timeout
    - Compare fetched content to cited claims using fuzzy matching
    - Classify each source as VERIFIED, HALLUCINATED, or INVALID
    - Calculate verification score and report hallucinations
    """
    
    def __init__(self, llm_client):
        """
        Initialize FactChecker.
        
        Args:
            llm_client: FreeLLMClient instance (not directly used, but required by BaseAgent)
        """
        super().__init__(llm_client)
        self.role = "FACT_CHECKER"
        self.url_timeout = 10  # seconds
        self.fuzzy_match_threshold = 70  # percentage
        self._fuzz_init_lock = threading.Lock()  # Thread-safe fuzzy import
        self.fuzz = None
        self.has_fuzzy_support = False
        
        # Try to import fuzzywuzzy, but don't fail if not available
        self._initialize_fuzzy_support()
    
    def generate(self, state: DebateState) -> FactCheckerResponse:
        """
        Verify all sources cited during the debate.
        
        Process:
        1. Extract all URLs from pro_sources and con_sources
        2. For each URL, attempt to fetch and verify content concurrently
        3. Use fuzzy matching to validate that source content matches claims
        4. Calculate overall verification metrics
        5. Return detailed verification report
        
        Args:
            state: Current debate state with all arguments and sources
            
        Returns:
            FactCheckerResponse with verification details for all sources
        """
        logger.info("FactChecker: Starting concurrent source verification")
        
        # Extract all sources with their corresponding claims
        all_sources_with_claims = self._extract_sources_with_claims(state)
        
        if not all_sources_with_claims:
            logger.info("ℹ️ No sources found to verify")
            return FactCheckerResponse(
                agent="FACT_CHECKER",
                verification_results=[],
                verified_count=0,
                hallucinated_count=0,
                verification_rate=0.0,  # No sources = 0.0 (Fixes inconsistency)
                overall_confidence=0.0
            )
        
        # Deduplicate sources
        seen_urls = set()
        unique_sources = []
        for url, claim_text, agent_source in all_sources_with_claims:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append((url, claim_text, agent_source))
        
        # Verify sources concurrently (Fixes Reliability/Throughput issues)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        verification_results = []
        max_workers = min(10, len(unique_sources))  # Limit concurrency
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Map verify_source to each unique source
            future_to_url = {
                executor.submit(self._verify_source, url, claim, src): url 
                for url, claim, src in unique_sources
            }
            
            for future in as_completed(future_to_url, timeout=60): # Overall 60s timeout
                try:
                    result = future.result()
                    verification_results.append(result)
                    logger.info(f"  [{result['status']}] {future_to_url[future][:50]}... (conf: {result['confidence']:.0%})")
                except Exception as exc:
                    url = future_to_url[future]
                    logger.error(f'URL {url} generated an exception: {exc}')
        
        # Calculate metrics with zero division safety
        total_count = len(verification_results)
        verified_count = sum(1 for r in verification_results if r['status'] == "VERIFIED")
        
        if total_count > 0:
            verification_rate = verified_count / total_count
            overall_confidence = sum(r['confidence'] for r in verification_results) / total_count
            hallucinated_count = total_count - verified_count
        else:
            verification_rate = 0.0
            overall_confidence = 0.0
            hallucinated_count = 0
        
        logger.info(f"\n📊 Verification Summary:")
        logger.info(f"  Total sources: {total_count}")
        logger.info(f"  ✅ Verified: {verified_count}")
        logger.info(f"  ❌ Hallucinated: {hallucinated_count}")
        logger.info(f"  📈 Rate: {verification_rate:.0%}")
        logger.info(f"  🎯 Confidence: {overall_confidence:.1%}\n")
        
        return FactCheckerResponse(
            agent="FACT_CHECKER",
            verification_results=verification_results,
            verified_count=verified_count,
            hallucinated_count=hallucinated_count,
            verification_rate=verification_rate,
            overall_confidence=overall_confidence
        )
    
    def _initialize_fuzzy_support(self) -> None:
        """
        Initialize fuzzy matching support in a thread-safe manner.
        Called once during __init__.
        """
        with self._fuzz_init_lock:
            if self.fuzz is not None:
                return  # Already initialized
            
            try:
                from fuzzywuzzy import fuzz
                self.fuzz = fuzz
                self.has_fuzzy_support = True
            except ImportError:
                logger.warning("⚠️  fuzzywuzzy not installed - will use simple string matching")
                self.has_fuzzy_support = False
    
    def _extract_sources_with_claims(self, state: DebateState) -> List[Tuple[str, str, str]]:
        """
        Extract all URLs from debate state along with corresponding claims.
        
        Args:
            state: Debate state with pro_sources and con_sources
            
        Returns:
            List of (url, claim_text, agent_source) tuples
        """
        sources_with_claims = []
        
        # Extract PRO sources with corresponding arguments
        for i, source_list in enumerate(state['pro_sources']):
            if i < len(state['pro_arguments']):
                argument = state['pro_arguments'][i]
                for url in source_list:
                    if url and url.strip():  # Skip empty URLs
                        sources_with_claims.append((url.strip(), argument, "PRO"))
        
        # Extract CON sources with corresponding arguments
        for i, source_list in enumerate(state['con_sources']):
            if i < len(state['con_arguments']):
                argument = state['con_arguments'][i]
                for url in source_list:
                    if url and url.strip():  # Skip empty URLs
                        sources_with_claims.append((url.strip(), argument, "CON"))
        
        return sources_with_claims
    
    def _verify_source(self, url: str, claim_text: str, agent_source: str) -> SourceVerification:
        """
        Verify a single source URL.
        
        Process:
        1. Attempt to fetch URL with timeout
        2. If successful, extract text content
        3. Use fuzzy matching to compare claim to content
        4. Classify result and calculate confidence
        
        Args:
            url: URL to verify
            claim_text: The claim text that supposedly supports this source
            agent_source: Which agent cited this ("PRO" or "CON")
            
        Returns:
            SourceVerification result
        """
        try:
            # Attempt to fetch URL
            logger.debug(f"Fetching: {url}")
            
            response = requests.get(
                url, 
                timeout=self.url_timeout,
                headers={'User-Agent': 'InsightSwarm/1.0 (fact-checker)'},
                allow_redirects=True
            )
            
            # Check status code
            if response.status_code == 404:
                return SourceVerification(
                    url=url,
                    status="NOT_FOUND",
                    confidence=0.0,
                    content_preview=None,
                    error="404 Not Found",
                    agent_source=agent_source,
                    matched_claim=None
                )
            
            if response.status_code not in [200, 302, 301]:
                return SourceVerification(
                    url=url,
                    status="NOT_FOUND",
                    confidence=0.0,
                    content_preview=None,
                    error=f"HTTP {response.status_code}",
                    agent_source=agent_source,
                    matched_claim=None
                )
            
            # Extract text content
            content = response.text[:2000]  # First 2000 chars for matching
            
            # Perform fuzzy matching between claim and content
            similarity_score = self._fuzzy_match(claim_text, content)
            
            # Classify result
            if similarity_score >= self.fuzzy_match_threshold:
                status = "VERIFIED"
            else:
                status = "CONTENT_MISMATCH"
            
            # Normalize confidence to 0.0-1.0
            confidence = min(similarity_score / 100.0, 1.0)
            
            content_preview = content[:500] if content else None
            
            return SourceVerification(
                url=url,
                status=status,
                confidence=confidence,
                content_preview=content_preview,
                error=None,
                agent_source=agent_source,
                matched_claim=claim_text[:100]  # Store first 100 chars of claim
            )
        
        except requests.Timeout:
            return SourceVerification(
                url=url,
                status="TIMEOUT",
                confidence=0.0,
                content_preview=None,
                error=f"Timeout after {self.url_timeout}s",
                agent_source=agent_source,
                matched_claim=None
            )
        
        except requests.ConnectionError as e:
            return SourceVerification(
                url=url,
                status="NOT_FOUND",
                confidence=0.0,
                content_preview=None,
                error=f"Connection error: {str(e)[:50]}",
                agent_source=agent_source,
                matched_claim=None
            )
        
        except Exception as e:
            logger.debug(f"Unexpected error verifying {url}: {str(e)}")
            return SourceVerification(
                url=url,
                status="NOT_FOUND",
                confidence=0.0,
                content_preview=None,
                error=f"Error: {type(e).__name__}",
                agent_source=agent_source,
                matched_claim=None
            )
    
    def _fuzzy_match(self, claim_text: str, source_content: str) -> float:
        """
        Calculate similarity between claim and source content.
        
        Uses fuzzywuzzy if available, otherwise falls back to simple keyword matching.
        
        Args:
            claim_text: The claim to match (usually 50-200 words)
            source_content: The source content to match against (usually 200-2000 words)
            
        Returns:
            Similarity score (0-100)
        """
        if not claim_text or not source_content:
            return 0.0
        
        # Use fuzzywuzzy if available
        if self.has_fuzzy_support:
            # Use partial_ratio for substring matching (claim might be partial quote)
            return self.fuzz.partial_ratio(claim_text.lower(), source_content.lower())
        
        # Fallback: simple keyword matching
        claim_words = set(claim_text.lower().split())
        content_words = set(source_content.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were'}
        claim_words = claim_words - stop_words
        content_words = content_words - stop_words
        
        if not claim_words:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = claim_words & content_words
        union = claim_words | content_words
        
        similarity = 100.0 * len(intersection) / len(union) if union else 0.0
        
        return similarity
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """
        Not used by FactChecker (no LLM interaction), but required by BaseAgent interface.
        
        FactChecker uses deterministic fact verification, not LLM generation.
        """
        return ""
