"""
src/utils/claim_decomposer.py — Final production version.
"""
import logging
from typing import List
from pydantic import BaseModel
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)


class ClaimsOutput(BaseModel):
    claims: List[str]


class ClaimDecomposer:
    def __init__(self, llm_client: FreeLLMClient):
        self.client = llm_client

    def decompose(self, full_claim: str) -> List[str]:
        # Fast-exit: short claims with no conjunctions don't need decomposition
        words = full_claim.split()
        if len(words) < 10 and " and " not in full_claim.lower() and "," not in full_claim:
            return [full_claim]

        prompt = (
            f"You are a Claim Decomposer. Split the following complex claim into atomic, "
            f"independent statements that can be individually fact-checked.\n"
            f"Each statement must be a complete, self-contained sentence.\n\n"
            f"COMPLEX CLAIM: {full_claim[:500]}\n\n"
            f'Respond in JSON format:\n{{"claims": ["atomic claim 1", "atomic claim 2", ...]}}'
        )
        try:
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=ClaimsOutput,
                temperature=0.1,
                preferred_provider="groq",
            )
            claims = response.claims if hasattr(response, "claims") else []
            if not claims:
                logger.warning("ClaimDecomposer returned empty list — falling back to original.")
                return [full_claim]
            logger.info("Decomposed claim into %d parts.", len(claims))
            return claims
        except Exception as e:
            logger.warning("ClaimDecomposer failed: %s — falling back to original.", e)
            return [full_claim]
