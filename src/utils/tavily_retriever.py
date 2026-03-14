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


# Global instance
_tavily_instance = None

def get_tavily_retriever() -> TavilyEvidenceRetriever:
    """Get global Tavily retriever instance"""
    global _tavily_instance
    if _tavily_instance is None:
        _tavily_instance = TavilyEvidenceRetriever()
    return _tavily_instance
