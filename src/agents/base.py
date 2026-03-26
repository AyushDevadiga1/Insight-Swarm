"""
src/agents/base.py
B2-P6: _format_evidence() moved here from ProAgent/ConAgent to eliminate duplication.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.core.models import AgentResponse, DebateState
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, llm_client: FreeLLMClient):
        self.client     = llm_client
        self.role: str  = "UNKNOWN"
        self.call_count = 0

    @abstractmethod
    def generate(self, state: DebateState) -> AgentResponse:
        raise NotImplementedError

    @abstractmethod
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        raise NotImplementedError

    def _format_evidence(self, evidence_bundle: Optional[List[Dict[str, Any]]]) -> str:
        """
        B2-P6 fix: single shared implementation — remove the identical copy in
        ProAgent and ConAgent and call self._format_evidence() instead.
        """
        if not evidence_bundle:
            return (
                "No pre-fetched evidence available. "
                "Use your training knowledge and clearly label each claim as "
                "[General Knowledge] since no URLs were retrieved."
            )
        lines = []
        for item in evidence_bundle:
            title   = item.get("title", "Source")
            url     = item.get("url", "")
            # B4-P5 fix: increase evidence context to 500 chars (from 300)
            content = item.get("content", "")[:500]
            lines.append(f"- {title} ({url}): {content}...")
        return "\n".join(lines)

    def _sanitize_sources(self, sources: Optional[List[str]]) -> List[str]:
        if not sources:
            return []
        try:
            from src.utils.url_helper import URLNormalizer
        except ImportError:
            logger.warning("URLNormalizer not available — sources returned raw")
            return [s for s in sources if isinstance(s, str) and s.strip()]

        cleaned, seen = [], set()
        for s in sources:
            if not isinstance(s, str):
                continue
            url = URLNormalizer.sanitize_url(s)
            if url and url not in seen:
                cleaned.append(url)
                seen.add(url)

        skipped = len(sources) - len(cleaned)
        if skipped:
            logger.debug("_sanitize_sources: skipped %d invalid/duplicate entries", skipped)
        return cleaned
