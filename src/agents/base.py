"""
Base classes and type definitions for all agents
"""
import logging
import re
from typing import List
from urllib.parse import urlparse
from abc import ABC, abstractmethod
from src.core.models import AgentResponse, DebateState
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)

# ============================================
# BASE AGENT CLASS
# ============================================

class BaseAgent(ABC):
    """
    Abstract base class for all debate agents.
    
    All agents (ProAgent, ConAgent, FactChecker, Moderator) inherit from this
    and must implement the generate() and _build_prompt() methods.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        """
        Initialize agent with LLM client
        
        Args:
            llm_client: FreeLLMClient instance for API calls
        """
        self.client = llm_client
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
        raise NotImplementedError("Subclasses must implement generate()")
    
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
        raise NotImplementedError("Subclasses must implement _build_prompt()")

