"""
Tavily Evidence Retriever - Gets high-quality sources before debate.

Uses Tavily API for web search to provide evidence-based context.
Reduces hallucinated sources and improves debate quality.
"""

import os
import logging
from typing import List, Dict, Any, Optional

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None  # type: ignore


logger = logging.getLogger(__name__)

class TavilyEvidenceRetriever:
    """
    Retrieves evidence from web search using Tavily API.
    
    Provides high-quality, relevant sources for claims before debate.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily client.
        
        Args:
            api_key: Tavily API key (defaults to TAVILY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if TavilyClient is None:
            logger.warning("Tavily client library not installed - retrieval disabled")
            self.client = None
            return
        if not self.api_key:
            logger.warning("⚠️ No TAVILY_API_KEY found - Tavily retrieval disabled")
            self.client = None
        else:
            try:
                self.client = TavilyClient(api_key=self.api_key)
                logger.info("✅ Tavily evidence retriever initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
                self.client = None
    
    def search_adversarial(self, claim: str, max_results: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform two targeted searches: one for supporting evidence and one for rebuttals.
        Ensures both Pro and Con agents have high-quality, relevant data.
        """
        if not self.client:
            return {"pro": [], "con": []}
        try:
            # Pro search: Focus on confirmation and established facts
            pro_query = f"{claim} facts and supporting evidence"
            pro_resp = self.client.search(query=pro_query, search_depth="advanced", max_results=max_results)
            
            # Con search: Focus on controversies, rebuttals, and counter-arguments
            con_query = f"{claim} rebuttals counter-arguments controversy"
            con_resp = self.client.search(query=con_query, search_depth="advanced", max_results=max_results)

            def _format_res(results):
                return [{
                    'title': r.get('title', ''),
                    'url': r.get('url', ''),
                    'content': r.get('content', '')[:600],
                    'score': r.get('score', 0.0)
                } for r in results.get('results', [])]

            data = {
                "pro": _format_res(pro_resp),
                "con": _format_res(con_resp)
            }
            logger.info(f"⚖️ Dual-sided search complete: {len(data['pro'])} Pro / {len(data['con'])} Con sources.")
            return data
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate limit" in err_str:
                logger.warning(f"⚠️ Tavily rate limit reached: {e}")
            else:
                logger.error(f"Adversarial search failed: {e}")
            return {"pro": [], "con": []}

    def search_evidence(self, claim: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for evidence related to a claim.
        
        Args:
            claim: The claim to search evidence for
            max_results: Maximum number of results to return
            
        Returns:
            List of evidence dicts with 'title', 'url', 'content', 'score'
        """
        if not self.client:
            logger.warning("Tavily client not available - returning empty evidence")
            return []
        
        try:
            # Use Tavily search with claim as query
            response = self.client.search(
                query=claim,
                search_depth="advanced",  # Get comprehensive results
                max_results=max_results,
                include_answer=False,  # We want sources, not AI summaries
                include_raw_content=True,  # Get full content snippets
                include_images=False  # Focus on text sources
            )
            
            evidence = []
            for result in response.get('results', []):
                evidence.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', '')[:500],  # Truncate content
                    'score': result.get('score', 0.0)
                })
            
            logger.info(f"📚 Retrieved {len(evidence)} evidence sources for: '{claim}'")
            return evidence
            
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []
    
    def get_relevant_sources(self, claim: str, num_sources: int = 3) -> List[str]:
        """
        Get list of relevant source URLs for a claim.
        
        Args:
            claim: The claim to find sources for
            num_sources: Number of URLs to return
            
        Returns:
            List of URLs as strings
        """
        evidence = self.search_evidence(claim, max_results=num_sources)
        return [item['url'] for item in evidence if item['url']]


import threading

# Global instance
_tavily_instance = None
_tavily_lock = threading.Lock()

def get_tavily_retriever() -> TavilyEvidenceRetriever:
    """Get global Tavily retriever instance"""
    global _tavily_instance
    if _tavily_instance is None:
        with _tavily_lock:
            if _tavily_instance is None:
                _tavily_instance = TavilyEvidenceRetriever()
    return _tavily_instance
