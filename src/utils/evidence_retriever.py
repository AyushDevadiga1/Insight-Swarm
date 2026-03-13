"""
EvidenceRetriever - Integrates Tavily Search for real evidence retrieval
"""

import os
from typing import List, Dict
from tavily import TavilyClient

class EvidenceRetriever:
    """Retrieves real evidence before debate"""
    def __init__(self):
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    def retrieve_for_position(self, claim: str, position: str) -> List[Dict]:
        """
        Retrieve evidence favoring a position
        Args:
            claim: The claim to search
            position: "support" or "refute"
        Returns:
            List of evidence snippets with URLs
        """
        if position == "support":
            query = f"{claim} evidence supporting true"
        else:
            query = f"{claim} evidence refuting false"
        results = self.tavily.search(query, max_results=5)
        return [
            {
                'url': result['url'],
                'title': result['title'],
                'content': result['content'][:500],
                'score': result.get('score', 0.5)
            }
            for result in results['results']
        ]
