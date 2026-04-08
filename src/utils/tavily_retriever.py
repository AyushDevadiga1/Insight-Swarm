"""
src/utils/tavily_retriever.py — Final production version.
"""
import os, logging, threading
from typing import List, Dict, Any, Optional

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None  # type: ignore

import re

logger = logging.getLogger(__name__)

# ISSUE-007 FIX: Block private/loopback URLs before any fetch to prevent SSRF.
# These patterns cover: loopback, RFC-1918 private ranges, link-local, and cloud metadata endpoints.
_BLOCKED_URL_PATTERNS = re.compile(
    r'https?://('
    r'localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0'
    r'|10\.\d+\.\d+\.\d+'
    r'|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+'
    r'|192\.168\.\d+\.\d+'
    r'|169\.254\.\d+\.\d+'   # AWS/Azure link-local metadata
    r'|::1|\[::1\]'           # IPv6 loopback
    r')',
    re.IGNORECASE,
)

def _is_safe_url(url: str) -> bool:
    """Return False if the URL resolves to a private/loopback address."""
    if not url:
        return False
    if _BLOCKED_URL_PATTERNS.match(url):
        logger.warning("SSRF guard: blocked private URL: %s", url)
        return False
    return True


class TavilyEvidenceRetriever:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if TavilyClient is None:
            logger.warning("Tavily client library not installed — retrieval disabled")
            self.client = None
            return
        if not self.api_key:
            logger.warning("No TAVILY_API_KEY found — Tavily retrieval disabled")
            self.client = None
        else:
            try:
                self.client = TavilyClient(api_key=self.api_key)
                logger.info("Tavily evidence retriever initialized")
            except Exception as e:
                logger.error("Failed to initialize Tavily client: %s", e)
                self.client = None

    def search_adversarial(self, claim: str, max_results: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Dual-sided search: one for supporting evidence, one for rebuttals.
        Falls back to Google Custom Search if Tavily is rate-limited or quota-exhausted."""
        if not self.client:
            return self._google_fallback(claim, max_results)
        try:
            pro_resp = self.client.search(query=f"{claim} facts and supporting evidence",
                                          search_depth="advanced", max_results=max_results)
            con_resp = self.client.search(query=f"{claim} rebuttals counter-arguments controversy",
                                          search_depth="advanced", max_results=max_results)

            def _fmt(results):
                return [
                    {"title": r.get("title",""), "url": r.get("url",""),
                     "content": r.get("content","")[:600], "score": r.get("score",0.0)}
                    for r in results.get("results",[])
                    # ISSUE-007 FIX: filter any private/internal URLs before returning
                    if _is_safe_url(r.get("url",""))
                ]

            data = {"pro": _fmt(pro_resp), "con": _fmt(con_resp)}
            logger.info("Dual-sided search: %d Pro / %d Con sources", len(data["pro"]), len(data["con"]))
            return data
        except Exception as e:
            err = str(e).lower()
            if any(key in err for key in ("429", "rate limit", "quota", "forbidden", "403")):
                logger.warning("Tavily rate-limited or quota exhausted — falling back to Google CSE: %s", e)
                return self._google_fallback(claim, max_results)
            else:
                logger.error("Adversarial search failed: %s", e)
            return {"pro": [], "con": []}

    def _google_fallback(self, claim: str, max_results: int) -> Dict[str, List[Dict[str, Any]]]:
        """Use Google Custom Search as fallback when Tavily is unavailable."""
        try:
            from src.utils.google_cse_retriever import get_google_cse_retriever
            cse = get_google_cse_retriever()
            result = cse.search_adversarial(claim, max_results)
            if result["pro"] or result["con"]:
                logger.info("Google CSE fallback: %d pro / %d con", len(result["pro"]), len(result["con"]))
            return result
        except Exception as e:
            logger.error("Google CSE fallback also failed: %s", e)
            return {"pro": [], "con": []}

    def search_evidence(self, claim: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if not self.client:
            return []
        try:
            response = self.client.search(query=claim, search_depth="advanced",
                                          max_results=max_results, include_answer=False,
                                          include_raw_content=True, include_images=False)
            evidence = [{"title": r.get("title",""), "url": r.get("url",""),
                         "content": r.get("content","")[:500], "score": r.get("score",0.0)}
                        for r in response.get("results",[])]
            logger.info("Retrieved %d evidence sources for: '%s'", len(evidence), claim)
            return evidence
        except Exception as e:
            logger.error("Tavily search failed: %s", e)
            return []

    def get_relevant_sources(self, claim: str, num_sources: int = 3) -> List[str]:
        return [item["url"] for item in self.search_evidence(claim, max_results=num_sources) if item["url"]]


_tavily_instance = None
_tavily_lock     = threading.Lock()

def get_tavily_retriever() -> TavilyEvidenceRetriever:
    global _tavily_instance
    if _tavily_instance is None:
        with _tavily_lock:
            if _tavily_instance is None:
                _tavily_instance = TavilyEvidenceRetriever()
    return _tavily_instance
