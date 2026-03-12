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
from typing import Tuple, Optional, Dict
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
            verdict, confidence, reasoning, metrics = self._parse_moderator_response(response_text)
            
            logger.info(f"Moderator verdict: {verdict}") # Standardized logging
            logger.info(f"Confidence score: {confidence:.2f}")
            
            return {
                "agent": "MODERATOR",
                "round": state['round'],
                "argument": reasoning[:300] + "..." if len(reasoning) > 300 else reasoning,
                "reasoning": reasoning,  # Return full reasoning as requested
                "sources": [],
                "confidence": confidence,
                "verdict": verdict,
                "metrics": metrics
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
        claim = state['claim']  # Removed html.escape
        
        # Compile arguments
        pro_args = "\n\n".join([
            f"Round {i+1}: {arg}"
            for i, arg in enumerate(state['pro_arguments'])
        ])
        
        con_args = "\n\n".join([
            f"Round {i+1}: {arg}"
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
CONFIDENCE: [0.0 to 1.0]

METRICS:
- CREDIBILITY_SCORE: [0.0 to 1.0]
- FALLACY_COUNT: [integer]
- BALANCE_SCORE: [0.0 to 1.0, where 0.5 is perfectly balanced]

REASONING:
[2-3 paragraphs explaining your verdict.]

Begin your analysis:"""
        
        return prompt
    
    def _parse_moderator_response(self, response_text: str) -> Tuple[str, float, str, Dict]:
        """
        Parse Moderator's verdict from LLM response using robust regex.
        Returns: (verdict, confidence, reasoning, metrics)
        """
        verdict = None
        confidence = 0.5
        reasoning = ""
        metrics = {
            "credibility": 0.5,
            "fallacies": 0,
            "balance": 0.5
        }

        # Verdict: Tight exact match for allowed values
        verdict_pattern = r"(?:VERDICT|Verdict|verdict)\s*[:\-]?\s*(TRUE|FALSE|PARTIALLY TRUE|INSUFFICIENT EVIDENCE)"
        verdict_match = re.search(verdict_pattern, response_text, re.IGNORECASE)
        if verdict_match:
            verdict = verdict_match.group(1).upper().strip()
        
        # Confidence: Precision parsing
        conf_match = re.search(r"CONFIDENCE\s*[:\-]?\s*(0?\.\d+|1\.0|1)", response_text, re.IGNORECASE)
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
            except ValueError: pass

        # Metrics parsing
        cred_match = re.search(r"CREDIBILITY_SCORE\s*[:\-]?\s*(0?\.\d+|1\.0|1)", response_text, re.IGNORECASE)
        if cred_match: metrics["credibility"] = float(cred_match.group(1))
        
        fall_match = re.search(r"FALLACY_COUNT\s*[:\-]?\s*(\d+)", response_text, re.IGNORECASE)
        if fall_match: metrics["fallacies"] = int(fall_match.group(1))
        
        bal_match = re.search(r"BALANCE_SCORE\s*[:\-]?\s*(0?\.\d+|1\.0|1)", response_text, re.IGNORECASE)
        if bal_match: metrics["balance"] = float(bal_match.group(1))

        # Reasoning: Capture everything after REASONING up to end or next marker
        reason_match = re.search(r"REASONING\s*[:\-]?\s*(.*)", response_text, re.IGNORECASE | re.DOTALL)
        if reason_match:
            reasoning = reason_match.group(1).strip()
        
        if not verdict:
            logger.warning("Moderator: Failed to parse verdict accurately.")
            verdict = "INSUFFICIENT EVIDENCE"
            reasoning = response_text.strip() if not reasoning else reasoning

        return verdict, confidence, reasoning, metrics
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
            "argument": reasoning,
            "reasoning": reasoning,
            "sources": [],
            "confidence": confidence,
            "verdict": verdict,
            "metrics": {
                "credibility": (pro_verification + con_verification) / 2,
                "fallacies": 0,
                "balance": 0.5
            }
        }
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """
        Required by BaseAgent interface.
        """
        return self._build_analysis_prompt(state)