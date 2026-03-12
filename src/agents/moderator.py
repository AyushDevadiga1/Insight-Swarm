"""
Moderator Agent - Analyzes debate quality and produces reasoned verdicts

This agent:
1. Reviews all arguments from ProAgent, ConAgent, and FactChecker
2. Assesses evidence quality (not quantity)
3. Identifies logical fallacies
4. Weighs source credibility
5. Produces explainable verdicts with confidence reasoning
"""

import logging
import re
import html
from typing import Tuple, Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)


class Moderator(BaseAgent):
    """
    4th agent that moderates the debate and produces final verdict.
    
    Unlike ProAgent/ConAgent (adversarial) and FactChecker (mechanical),
    Moderator uses reasoning to assess argument quality holistically.
    
    Novel contribution: Evidence-based consensus, not vote counting.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        """
        Initialize Moderator
        
        Args:
            llm_client: FreeLLMClient instance
        """
        super().__init__(llm_client)
        self.role = "MODERATOR"
    
    def generate(self, state: DebateState) -> AgentResponse:
        """
        Analyze complete debate and produce reasoned verdict.
        
        Process:
        1. Review all arguments (Pro, Con)
        2. Review FactChecker verification results
        3. Assess evidence quality
        4. Identify logical fallacies
        5. Produce verdict with detailed reasoning
        
        Args:
            state: Complete debate state
            
        Returns:
            AgentResponse with verdict and reasoning
        """
        logger.info("Moderator analyzing debate...")
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(state)
        
        # Get Moderator's analysis
        try:
            response_text = self.client.call(
                prompt,
                temperature=0.3,  # Lower temperature for analytical task
                max_tokens=1500
            )
            
            # Parse response
            verdict, confidence, reasoning = self._parse_moderator_response(response_text)
            
            logger.info(f"Moderator verdict: {verdict} ({confidence:.1%} confidence)")
            
            return {
                "agent": "MODERATOR",
                "round": state['round'],
                "argument": reasoning,  # Return parsed reasoning, not raw response
                "sources": [],
                "confidence": confidence,
                "verdict": verdict
            }
        
        except Exception as e:
            logger.error(f"Moderator analysis failed: {e}")
            
            # Fallback to simple verdict
            return self._fallback_verdict(state)
    
    def _build_analysis_prompt(self, state: DebateState) -> str:
        """
        Build comprehensive analysis prompt for Moderator.
        
        This prompt asks the LLM to:
        - Assess argument quality
        - Evaluate evidence
        - Identify fallacies
        - Consider verification results
        - Produce reasoned verdict
        
        Args:
            state: Debate state
            
        Returns:
            Formatted prompt
        """
        claim = html.escape(state['claim'])
        
        # Compile arguments
        pro_args = "\n\n".join([
            f"Round {i+1}: {html.escape(arg)}"
            for i, arg in enumerate(state['pro_arguments'])
        ])
        
        con_args = "\n\n".join([
            f"Round {i+1}: {html.escape(arg)}"
            for i, arg in enumerate(state['con_arguments'])
        ])
        
        # Get verification summary
        pro_verification = state.get('pro_verification_rate', 0.0)
        con_verification = state.get('con_verification_rate', 0.0)
        
        verification_summary = f"""
Source Verification Results:
- ProAgent sources: {pro_verification:.1%} verified
- ConAgent sources: {con_verification:.1%} verified
"""
        
        # Build comprehensive prompt
        prompt = f"""You are the Moderator in a fact-checking debate. Your role is to analyze the quality of arguments and evidence to determine the truth of a claim.

CLAIM TO EVALUATE:
{claim}

PROAGENT ARGUMENTS (arguing claim is TRUE):
{pro_args}

CONAGENT ARGUMENTS (arguing claim is FALSE):
{con_args}

{verification_summary}

YOUR TASK:
As an impartial moderator, assess the debate quality and determine the verdict. Consider:

1. **Argument Quality**: Are arguments well-reasoned and supported by evidence?
2. **Evidence Strength**: Do cited sources actually support the claims made?
3. **Logical Fallacies**: Are there any logical errors (ad hominem, straw man, false causality)?
4. **Source Credibility**: Are sources from reputable institutions vs. random blogs?
5. **Verification Results**: How many sources were actually verified?
6. **Nuance**: Is the claim absolute or are there conditions/exceptions?

IMPORTANT GUIDELINES:
- Focus on EVIDENCE QUALITY, not quantity (a short argument with strong evidence beats long argument with weak evidence)
- Penalize arguments with unverified sources
- Identify logical fallacies and downweight those arguments
- Consider if claim is partially true (e.g., "true in some cases but not all")
- Be conservative: if evidence is weak on both sides, verdict should reflect uncertainty

OUTPUT FORMAT (you must follow this exactly):

VERDICT: [TRUE | FALSE | PARTIALLY TRUE | INSUFFICIENT EVIDENCE]
CONFIDENCE: [0.0 to 1.0 as decimal, e.g., 0.75]

REASONING:
[2-3 paragraphs explaining your verdict. Include:
- Which arguments were strongest and why
- Any logical fallacies you identified
- How verification results influenced your decision
- Why you assigned this confidence level
- Any important nuances or conditions]

Begin your analysis:"""
        
        return prompt
    
    def _parse_moderator_response(self, response_text: str) -> Tuple[str, float, str]:
        """
        Parse Moderator's verdict from LLM response using robust regex.
        
        Handles varied spacing, casing, and trailing punctuation.
        """
        verdict = None
        confidence = 0.5
        reasoning = ""

        # Verdict parsing: case-insensitive, handles varied spacing/markers
        verdict_match = re.search(
            r"(?:VERDICT|Verdict|verdict)\s*[:\-]?\s*(\w+(?:\s+\w+)?)", 
            response_text,
            re.IGNORECASE
        )
        if verdict_match:
            verdict_text = verdict_match.group(1).upper().strip()
            # Normalize to standard verdicts
            if "TRUE" in verdict_text and "PARTIALLY" not in verdict_text and "FALSE" not in verdict_text:
                verdict = "TRUE"
            elif "FALSE" in verdict_text and "PARTIALLY" not in verdict_text:
                verdict = "FALSE"
            elif "PARTIALLY" in verdict_text or "PARTIAL" in verdict_text:
                verdict = "PARTIALLY TRUE"
            elif "INSUFFICIENT" in verdict_text or "UNCLEAR" in verdict_text:
                verdict = "INSUFFICIENT EVIDENCE"
        
        # Confidence parsing: case-insensitive, handles varied spacing
        conf_match = re.search(
            r"(?:CONFIDENCE|Confidence|confidence)\s*[:\-]?\s*(0?\.\d+|1\.0|1)", 
            response_text,
            re.IGNORECASE
        )
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.5

        # Reasoning parsing: capture everything after REASONING marker
        reason_match = re.search(
            r"(?:REASONING|Reasoning|reasoning)\s*[:\-]?\s*(.*)", 
            response_text, 
            re.IGNORECASE | re.DOTALL
        )
        if reason_match:
            reasoning = reason_match.group(1).strip()
        
        if not verdict:
            logger.warning("Failed to parse verdict, defaulting to INSUFFICIENT EVIDENCE")
            verdict = "INSUFFICIENT EVIDENCE"
            confidence = 0.3
            reasoning = response_text.strip()

        return verdict, confidence, reasoning
    def _fallback_verdict(self, state: DebateState) -> AgentResponse:
        """
        Fallback verdict if Moderator LLM call fails.
        """
        logger.warning("Using fallback verdict calculation")
        
        pro_verification = state.get('pro_verification_rate') or 0.0
        con_verification = state.get('con_verification_rate') or 0.0
        
        if pro_verification > 0.7 and con_verification < 0.3:
            verdict = "TRUE"
            confidence = pro_verification
            reasoning = "ProAgent's sources were well-verified while ConAgent's were not."
        elif con_verification > 0.7 and pro_verification < 0.3:
            verdict = "FALSE"
            confidence = con_verification
            reasoning = "ConAgent's sources were well-verified while ProAgent's were not."
        else:
            verdict = "PARTIALLY TRUE"
            confidence = 0.5
            reasoning = "Both sides had mixed verification results."
        
        return {
            "agent": "MODERATOR",
            "round": state['round'],
            "argument": reasoning,  # Return reasoning, not full text
            "sources": [],
            "confidence": confidence,
            "verdict": verdict
        }
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """
        Required by BaseAgent interface.
        """
        return self._build_analysis_prompt(state)