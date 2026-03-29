"""
src/agents/pro_agent.py — All batches applied. Final production version.
"""
from datetime import datetime
from typing import Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import AgentArgumentResponse
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)


class ProAgent(BaseAgent):
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role               = "PRO"
        self.preferred_provider = preferred_provider or "groq"

    def generate(self, state: DebateState) -> AgentResponse:
        logger.info("ProAgent generating — Round %d", state.round)
        prompt = self._build_prompt(state, state.round)
        try:
            raw = self.client.call_structured(
                prompt=prompt,
                output_schema=AgentArgumentResponse,
                temperature=0.7,
                preferred_provider=self.preferred_provider,
            )
            self.call_count += 1
            return AgentResponse(
                agent="PRO",
                round=state.round,
                argument=raw.argument,
                sources=self._sanitize_sources(raw.sources),
                confidence=raw.confidence,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )
        except Exception as e:
            logger.error("ProAgent failed: %s", e)
            err = str(e)
            if "QUOTA_EXHAUSTED" in err or "429" in err.lower():
                arg, conf = "[API_FAILURE] Quota exhausted — update API keys or wait for reset.", 0.0
            else:
                arg  = (f"Based on available evidence, the claim '{state.claim}' "
                        f"appears to be TRUE. [Fallback — technical issue encountered.]")
                conf = 0.3
            return AgentResponse(agent="PRO", round=state.round, argument=arg,
                                 sources=[], confidence=conf,
                                 timestamp=datetime.now().strftime("%H:%M:%S"))

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        evidence_bundle    = state.evidence_sources or state.pro_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)

        if round_num == 1:
            return f"""You are ProAgent in a formal fact-checking debate. Argue that this claim is TRUE.

CLAIM: {state.claim}

EVIDENCE TO USE:
{formatted_evidence}

YOUR TASK:
1. Build the strongest case FOR this claim.
2. CITE ONLY URLS FROM THE EVIDENCE PROVIDED ABOVE. Do not make up or hallucinate URLs.
3. If no URLs are provided, use training knowledge labeled [General Knowledge].
4. Make a persuasive argument in 3-5 sentences.
5. List the source URLs you cited in the 'sources' field.

Do NOT start with "I" or "As an AI"."""
        else:
            con_argument = state.con_arguments[-1] if state.con_arguments else "No counter-argument."
            feedback_section = (
                f"\n\nVERIFICATION FEEDBACK:\n{state.verification_feedback}\n"
                if state.verification_feedback else ""
            )
            return f"""You are ProAgent. Continue arguing that this claim is TRUE: {state.claim}

OPPOSING ARGUMENT:
{con_argument}{feedback_section}

SUPPORTING EVIDENCE:
{formatted_evidence}

YOUR TASK:
1. Directly rebut the Con argument.
2. Reinforce with additional evidence or stronger reasoning.
3. CITE ONLY URLS FROM THE EVIDENCE PROVIDED ABOVE. Do not hallucinate.
4. If previous sources failed, cite different ones from the list.
5. Keep to 3-5 focused sentences."""
