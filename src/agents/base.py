"""
Base classes and type definitions for all agents.
_sanitize_sources() added here so ProAgent and ConAgent can call self._sanitize_sources().
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.models import AgentResponse, DebateState
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all debate agents.

    All agents (ProAgent, ConAgent, FactChecker, Moderator) inherit from this
    and must implement the generate() and _build_prompt() methods.
    """

    def __init__(self, llm_client: FreeLLMClient):
        self.client     = llm_client
        self.role: str  = "UNKNOWN"
        self.call_count = 0

    @abstractmethod
    def generate(self, state: DebateState) -> AgentResponse:
        raise NotImplementedError("Subclasses must implement generate()")

    @abstractmethod
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        raise NotImplementedError("Subclasses must implement _build_prompt()")

    def _sanitize_sources(self, sources: Optional[List[str]]) -> List[str]:
        """
        Sanitize a list of source strings into valid, deduplicated URLs.
        Called by ProAgent and ConAgent after receiving LLM response.
        """
        if not sources:
            return []

        try:
            from src.utils.url_helper import URLNormalizer
        except ImportError:
            logger.warning("URLNormalizer not available — sources returned raw")
            return [s for s in sources if isinstance(s, str) and s.strip()]

        cleaned = []
        seen    = set()
        for s in sources:
            if not isinstance(s, str):
                continue
            url = URLNormalizer.sanitize_url(s)
            if url and url not in seen:
                cleaned.append(url)
                seen.add(url)

        skipped = len(sources) - len(cleaned)
        if skipped > 0:
            logger.debug(f"_sanitize_sources: skipped {skipped} invalid/duplicate entries")

        return cleaned
