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

logger = logging.getLogger(__name__)

class FactChecker(BaseAgent):
    """
    Agent responsible for verifying sources cited in the debate.
    """
    
    def __init__(self, llm_client):
        super().__init__(llm_client)
        self.role = "FACT_CHECKER"
        self.url_timeout = 10
        self._fuzz_init_lock = threading.Lock()
        self.fuzz = None
        self._initialize_fuzzy_support()
    
    def _initialize_fuzzy_support(self):
        with self._fuzz_init_lock:
            try:
                from fuzzywuzzy import fuzz
                self.fuzz = fuzz
            except ImportError:
                logger.warning("fuzzywuzzy not installed - using fallback matching")

    def generate(self, state: DebateState) -> AgentResponse:
        """Verify all sources cited and return structured results."""
        logger.info("FactChecker verifying all debate sources...")
        
        all_sources = []
        # PRO sources
        for round_sources in state.pro_sources:
            for url in round_sources:
                all_sources.append((url, "PRO"))
        # CON sources
        for round_sources in state.con_sources:
            for url in round_sources:
                all_sources.append((url, "CON"))
                
        results = []
        if all_sources:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self._verify_url, url, agent): url for url, agent in all_sources}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        results.append(future.result())
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

    def _verify_url(self, url: str, agent: str) -> SourceVerification:
        """Deterministic URL verification."""
        try:
            resp = requests.get(url, timeout=self.url_timeout, allow_redirects=True)
            if resp.status_code == 200:
                return SourceVerification(
                    url=url,
                    status="VERIFIED",
                    agent_source=agent,
                    confidence=1.0,
                    content_preview=resp.text[:200]
                )
            return SourceVerification(url=url, status="NOT_FOUND", agent_source=agent, error=f"HTTP {resp.status_code}")
        except Exception as e:
            return SourceVerification(url=url, status="ERROR", agent_source=agent, error=str(e))
