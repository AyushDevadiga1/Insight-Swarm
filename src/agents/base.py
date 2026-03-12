"""
Base classes and type definitions for all agents
"""

from abc import ABC, abstractmethod
from typing import TypedDict, List, Optional


# ============================================
# TYPE DEFINITIONS
# ============================================

class AgentResponse(TypedDict):
    """
    Structured response from an agent after generating an argument
    
    Attributes:
        agent: Agent identifier ('PRO' or 'CON')
        round: Current debate round number
        argument: The agent's main argument text
        sources: List of URLs/citations used
        confidence: Agent's confidence in its argument (0.0 to 1.0)
    """
    agent: str
    round: int
    argument: str
    sources: List[str]
    confidence: float
    verdict: Optional[str]
    reasoning: Optional[str]  # NEW: Structured reasoning field


class DebateState(TypedDict):
    """
    Shared state object passed between agents during debate
    
    This contains the complete history of the debate and is updated
    after each agent's turn.
    
    Attributes:
        claim: The claim being fact-checked
        round: Current round number (1, 2, 3)
        pro_arguments: List of all ProAgent arguments so far
        con_arguments: List of all ConAgent arguments so far
        pro_sources: List of source lists from ProAgent
        con_sources: List of source lists from ConAgent
        verification_results: List of source verification results from FactChecker
        pro_verification_rate: Percentage of PRO sources verified (0.0-1.0)
        con_verification_rate: Percentage of CON sources verified (0.0-1.0)
        verdict: Final verdict (set at end, None during debate)
        confidence: Final confidence score (set at end, None during debate)
    """
    claim: str
    round: int
    pro_arguments: List[str]
    con_arguments: List[str]
    pro_sources: List[List[str]]
    con_sources: List[List[str]]
    verification_results: Optional[List]
    pro_verification_rate: Optional[float]
    con_verification_rate: float
    fact_check_result: str  # Added field
    moderator_reasoning: Optional[str]
    verdict: Optional[str]
    confidence: Optional[float]


# ============================================
# BASE AGENT CLASS
# ============================================

class BaseAgent(ABC):
    """
    Abstract base class for all debate agents.
    
    All agents (ProAgent, ConAgent, FactChecker, Moderator) inherit from this
    and must implement the generate() and _build_prompt() methods.
    """
    
    def __init__(self, llm_client):
        """
        Initialize agent with LLM client
        
        Args:
            llm_client: FreeLLMClient instance for API calls
        """
        from src.llm.client import FreeLLMClient
        
        self.client: FreeLLMClient = llm_client
        self.role: str = "UNKNOWN"  # Override in subclass
        self.call_count: int = 0
    
    @abstractmethod
    def generate(self, state: DebateState) -> AgentResponse:
        """
        Generate agent's response based on current debate state.
        
        This is the main method called by the orchestrator. Each agent
        must implement its own logic for analyzing the state and
        generating an appropriate response.
        
        Args:
            state: Current state of the debate with all history
            
        Returns:
            Structured agent response with argument and sources
        """
        pass
    
    @abstractmethod
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """
        Build the prompt to send to the LLM based on debate state.
        
        Each agent builds prompts differently based on their role.
        ProAgent prompts force arguing FOR, ConAgent forces AGAINST.
        
        Args:
            state: Current debate state
            round_num: Current round number
            
        Returns:
            Formatted prompt string for the LLM
        """
        pass
    
    def _parse_response(self, response_text: str) -> tuple[str, List[str]]:
        """
        Extract argument and sources from LLM response text.
        
        Expected format from LLM:
            ARGUMENT:
            [argument text here]
            
            SOURCES:
            - [source 1]
            - [source 2]
        
        Validates response and provides safe fallback.
        
        Args:
            response_text: Raw text from LLM
            
        Returns:
            Tuple of (argument_text, list_of_sources)
            
        Raises:
            ValueError: If response is None or not a string
        """
        # Validate input
        if response_text is None:
            raise ValueError("Response text is None")
        
        if not isinstance(response_text, str):
            raise ValueError(f"Response text must be string, got {type(response_text).__name__}")
        
        if not response_text.strip():
            raise ValueError("Response text is empty")
        
        # Split by SOURCES marker
        parts = response_text.split("SOURCES:")
        
        if len(parts) == 2:
            # Extract argument (remove markers)
            argument = parts[0].replace("ARGUMENT:", "").replace("REBUTTAL:", "").strip()
            
            # Validate argument is not empty
            if not argument.strip():
                raise ValueError("Argument text is empty after parsing")
            
            # Extract sources (lines starting with -)
            sources_text = parts[1].strip()
            sources = []
            
            for line in sources_text.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    source = line.removeprefix("- ").strip()
                    if source:  # Only add non-empty sources
                        sources.append(source)
            
            # Return argument and whatever sources were found (even if empty)
            if not sources:
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️ No sources found in response from {getattr(self, 'role', 'AGENT')}")
            return argument, sources
        
        else:
            # Fallback: treat entire response as argument
            # This is a safety net for malformed responses
            argument = response_text.strip()
            if len(argument) > 5000:
                argument = argument[:5000]  # Truncate very long responses
            
            return argument, []