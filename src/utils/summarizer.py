import logging
from src.llm.client import FreeLLMClient
from src.core.models import DebateState

logger = logging.getLogger(__name__)

class Summarizer:
    """
    Summarizes debate history to prevent context window overflow.
    Fulfills Audit Issue #20.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        self.client = llm_client

    def summarize_history(self, state: DebateState) -> str:
        """
        Creates a concise summary of the debate so far.
        """
        if state.round <= 2:
            return ""

        pro_args = "\n".join(state.pro_arguments)
        con_args = "\n".join(state.con_arguments)
        
        prompt = f"""Summarize the following debate on '{state.claim}' into a concise 1-paragraph overview. 
Highlight the main points of contention and the strongest evidence presented by both sides.

PRO ARGUMENTS:
{pro_args}

CON ARGUMENTS:
{con_args}
"""
        try:
            summary = self.client.call(
                prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            logger.info(f"Generated debate summary for round {state.round}")
            return summary
        except Exception as e:
            logger.warning(f"Summarizer failed: {e}")
            return "Summary unavailable."
