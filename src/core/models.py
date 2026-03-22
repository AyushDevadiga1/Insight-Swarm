from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

_MISSING = object()

class SourceVerification(BaseModel):
    """Result of verifying a single source."""
    url: str
    status: Literal["VERIFIED", "NOT_FOUND", "INVALID_URL", "TIMEOUT", "CONTENT_MISMATCH", "PAYWALL_RESTRICTED", "ERROR"]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    content_preview: Optional[str] = None
    error: Optional[str] = None
    agent_source: Optional[Literal["PRO", "CON"]] = None
    matched_claim: Optional[str] = None
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_score: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    trust_tier: Optional[str] = "GENERAL"

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()

class AgentResponse(BaseModel):
    """Structured response from a Pro or Con agent."""
    agent: Optional[Literal["PRO", "CON", "MODERATOR", "FACT_CHECKER"]] = None
    round: Optional[int] = 1
    argument: str = ""
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verdict: Optional[str] = None
    reasoning: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def __getitem__(self, item):
        return getattr(self, item)

    def get(self, key, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val

from pydantic import validator

class ModeratorVerdict(BaseModel):
    """Structured verdict from the Moderator agent."""
    verdict: str = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

    _VALID_VERDICTS = {
        "TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE",
        "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR"
    }

    @validator("verdict", pre=True, always=True)
    def normalise_verdict(cls, v):
        if not v:
            return "UNKNOWN"
        v = str(v).strip().upper()
        # Handle common LLM variants
        replacements = {
            "PARTIALLY_TRUE": "PARTIALLY TRUE",
            "PARTIAL": "PARTIALLY TRUE",
            "PARTLY TRUE": "PARTIALLY TRUE",
            "PARTLY_TRUE": "PARTIALLY TRUE",
            "INSUFFICIENT": "INSUFFICIENT EVIDENCE",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT EVIDENCE",
            "NOT ENOUGH EVIDENCE": "INSUFFICIENT EVIDENCE",
            "NOT_ENOUGH_EVIDENCE": "INSUFFICIENT EVIDENCE",
        }
        if v in replacements:
            return replacements[v]
        if v in ["TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE", "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR"]:
            return v
        # Unrecognised — log and fall back safely
        import logging
        logging.getLogger(__name__).warning(
            f"ModeratorVerdict: unexpected verdict string '{v}', defaulting to UNKNOWN"
        )
        return "UNKNOWN"

class DebateState(BaseModel):
    """Complete state of the debate workflow."""
    claim: str
    round: int = 1
    pro_arguments: List[str] = Field(default_factory=list)
    con_arguments: List[str] = Field(default_factory=list)
    pro_sources: List[List[str]] = Field(default_factory=list)
    con_sources: List[List[str]] = Field(default_factory=list)
    verdict: Optional[str] = None
    confidence: Optional[float] = None
    verification_results: Optional[List[Dict[str, Any]]] = None
    pro_verification_rate: Optional[float] = None
    con_verification_rate: Optional[float] = None
    moderator_reasoning: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    retry_count: int = 0
    is_cached: Optional[bool] = False
    
    # Phase 5: Advanced Intelligence
    summary: Optional[str] = ""
    num_rounds: int = 3
    pro_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    con_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    # Tavily pre-fetched evidence shared at debate start
    evidence_sources: List[Dict[str, Any]] = Field(default_factory=list)
    verification_feedback: Optional[str] = None
    pro_model_used: Optional[str] = None
    con_model_used: Optional[str] = None
    moderator_model_used: Optional[str] = None
    system_status: Optional[str] = None
    # Compatibility with TypedDict-style access during migration
    def __getitem__(self, item):
        return getattr(self, item)
    
    def __setitem__(self, key, value):
        if key not in self.__fields__:
            raise KeyError(f"Unknown DebateState field: {key!r}")
        setattr(self, key, value)
        
    def get(self, key, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val

    def __contains__(self, item: str) -> bool:
        return item in self.__fields__

    def keys(self):
        return self.__fields__.keys()

    def items(self):
        return ((k, getattr(self, k)) for k in self.__fields__.keys())

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()

class ConsensusResponse(BaseModel):
    verdict: str
    reasoning: str
    confidence: float
