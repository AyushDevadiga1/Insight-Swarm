"""
src/utils/google_cse_retriever.py

Google Custom Search Engine retriever — fallback when Tavily is rate-limited
or quota-exhausted. Uses existing GOOGLE_CLOUD (API key) and GOOGLE_CX
(Custom Search Engine ID) from .env.

Returns the same {"pro": [...], "con": [...]} shape as TavilyEvidenceRetriever
so it is a drop-in replacement.
"""
import os
import logging
import threading
from typing import List, Dict, Any, Optional

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

_CSE_BASE = "https://www.googleapis.com/customsearch/v1"


class GoogleCSERetriever:
    """
    Retriever backed by Google Custom Search API.
    Free tier: 100 queries/day.
    """

    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_CLOUD")
        self.cx      = cx      or os.getenv("GOOGLE_CX")

        if not HAS_REQUESTS:
            logger.warning("requests library not installed — GoogleCSERetriever disabled")
            self._enabled = False
        elif not self.api_key or not self.cx:
            logger.warning(
                "GOOGLE_CLOUD or GOOGLE_CX not set — GoogleCSERetriever disabled"
            )
            self._enabled = False
        else:
            self._enabled = True
            logger.info("GoogleCSERetriever initialized (cx=%s)", self.cx[:8] + "…")

    # ── Public API (mirrors TavilyEvidenceRetriever) ───────────────────────────

    def search_adversarial(
        self, claim: str, max_results: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Dual-sided search: supporting vs. rebuttal evidence."""
        if not self._enabled:
            return {"pro": [], "con": []}
        try:
            pro  = self._search(f"{claim} evidence facts", max_results)
            con  = self._search(f"{claim} counter-argument criticism debunked", max_results)
            logger.info(
                "GoogleCSE adversarial: %d pro / %d con results",
                len(pro), len(con)
            )
            return {"pro": pro, "con": con}
        except Exception as e:
            logger.error("GoogleCSE adversarial search failed: %s", e)
            return {"pro": [], "con": []}

    def search_evidence(self, claim: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Single-sided evidence search."""
        if not self._enabled:
            return []
        try:
            return self._search(claim, max_results)
        except Exception as e:
            logger.error("GoogleCSE evidence search failed: %s", e)
            return []

    def get_relevant_sources(self, claim: str, num_sources: int = 3) -> List[str]:
        return [item["url"] for item in self.search_evidence(claim, num_sources) if item["url"]]

    # ── Internal ───────────────────────────────────────────────────────────────

    def _search(self, query: str, n: int) -> List[Dict[str, Any]]:
        """Execute a single CSE search. Returns normalised result list."""
        params = {
            "key": self.api_key,
            "cx":  self.cx,
            "q":   query,
            "num": min(n, 10),   # CSE max per request is 10
        }
        resp = _requests.get(_CSE_BASE, params=params, timeout=10)

        # Surface rate-limit / quota errors clearly
        if resp.status_code == 429:
            raise RuntimeError("Google CSE rate-limited (429)")
        if resp.status_code == 403:
            raise RuntimeError("Google CSE quota exceeded or key invalid (403)")
        resp.raise_for_status()

        data  = resp.json()
        items = data.get("items", [])
        return [
            {
                "title":   item.get("title", ""),
                "url":     item.get("link", ""),
                "content": item.get("snippet", "")[:500],
                "score":   1.0,          # CSE doesn't give relevance scores
            }
            for item in items
            if item.get("link")
        ]


# ── Singleton ──────────────────────────────────────────────────────────────────
_cse_instance = None
_cse_lock     = threading.Lock()


def get_google_cse_retriever() -> GoogleCSERetriever:
    global _cse_instance
    if _cse_instance is None:
        with _cse_lock:
            if _cse_instance is None:
                _cse_instance = GoogleCSERetriever()
    return _cse_instance
