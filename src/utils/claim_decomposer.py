import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)

class ClaimDecomposer:
    """
    Decomposes multi-part claims into atomic sub-claims.
    Fulfills Audit Issue #09.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        self.client = llm_client

    def decompose(self, full_claim: str) -> List[str]:
        """
        Takes a potentially complex claim and returns a list of atomic claims.
        """
        # Quick exit for short claims
        if len(full_claim.split()) < 10 and " and " not in full_claim.lower() and "," not in full_claim:
            return [full_claim]

        prompt = f"""You are a Claim Decomposer. Split the following complex claim into atomic, independent statements that can be individually fact-checked.
EACH statement must be a complete, self-contained sentence.

COMPLEX CLAIM: {full_claim}

Respond in JSON format:
{{
  "claims": ["atomic claim 1", "atomic claim 2", ...]
}}
"""
        try:
            class ClaimsOutput(BaseModel):
                claims: List[str]

            response = self.client.call_structured(
                prompt=prompt,
                output_schema=ClaimsOutput,
                temperature=0.1,
                preferred_provider="gemini"
            )
            
            # Ensure we have a list of strings
            claims = response.claims if hasattr(response, 'claims') else []
            
            # Validation: if total fail or empty, return original
            if not claims:
                logger.warning("ClaimDecomposer returned empty list, falling back to original claim.")
                return [full_claim]
            
            logger.info(f"Decomposed claim into {len(claims)} parts.")
            return claims
            
        except Exception as e:
            logger.warning(f"ClaimDecomposer failed: {e}. Falling back to original.")
            return [full_claim]
