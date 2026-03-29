"""
src/agents/con_agent.py — All batches applied. Final production version.
"""
from datetime import datetime
from typing import Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import AgentArgumentResponse
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)


class ConAgent(BaseAgent):
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role               = "CON"
        self.preferred_provider = preferred_provider or "gemini"

    def generate(self, state: DebateState) -> AgentResponse:
        logger.info("ConAgent generating — Round %d", state.round)
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
                agent="CON",
                round=state.round,
                argument=raw.argument,
                sources=self._sanitize_sources(raw.sources),
                confidence=raw.confidence,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )
        except Exception as e:
            logger.error("ConAgent failed: %s", e)
            err = str(e)
            if "QUOTA_EXHAUSTED" in err or "429" in err.lower():
                arg, conf = "[API_FAILURE] Quota exhausted — update API keys or wait for reset.", 0.0
            else:
                arg  = (f"The claim '{state.claim}' is not fully supported. "
                        f"[Fallback — technical issue encountered.]")
                conf = 0.3
            return AgentResponse(agent="CON", round=state.round, argument=arg,
                                 sources=[], confidence=conf,
                                 timestamp=datetime.now().strftime("%H:%M:%S"))

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        evidence_bundle    = state.evidence_sources or state.con_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)
        pro_argument       = state.pro_arguments[-1] if state.pro_arguments else "No Pro argument."

        if round_num == 1:
            return f"""You are ConAgent in a formal fact-checking debate. Argue that this claim is FALSE.

CLAIM: {state.claim}

PRO AGENT ARGUED:
{pro_argument}

COUNTER-EVIDENCE:
{formatted_evidence}

YOUR TASK:
1. Build the strongest case AGAINST this claim.
2. Directly challenge the Pro argument — identify flaws or missing context.
3. CITE ONLY URLS FROM THE EVIDENCE PROVIDED ABOVE. Do not make up or hallucinate URLs.
4. If no URLs are provided, use training knowledge labeled [General Knowledge].
5. Be specific in 3-5 sentences.
6. List the source URLs you cited in the 'sources' field.

Do NOT start with "I" or "As an AI"."""
        else:
            latest_pro = state.pro_arguments[-1] if state.pro_arguments else "No new Pro argument."
            feedback_section = (
                f"\n\nVERIFICATION FEEDBACK:\n{state.verification_feedback}\n"
                if state.verification_feedback else ""
            )
            return f"""You are ConAgent. Continue arguing that this claim is FALSE: {state.claim}

YOUR PREVIOUS ARGUMENT:
{state.con_arguments[-1] if len(state.con_arguments) > 1 else "Establishing initial case."}

LATEST PRO REBUTTAL:
{latest_pro}{feedback_section}

COUNTER-EVIDENCE:
{formatted_evidence}

YOUR TASK:
1. Rebut the Pro's latest argument specifically.
2. Identify new flaws, missing context, or contradictory evidence.
3. CITE ONLY URLS FROM THE EVIDENCE PROVIDED ABOVE. Do not hallucinate.
4. If previous sources failed, cite stronger alternatives from the list.
5. Keep to 3-5 focused sentences."""
