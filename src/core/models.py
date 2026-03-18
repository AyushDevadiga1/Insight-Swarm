from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

_MISSING = object()


class SourceVerification(BaseModel):
    """Result of verifying a single source."""
    url: str
    status: Literal["VERIFIED", "NOT_FOUND", "INVALID_URL", "TIMEOUT", "CONTENT_MISMATCH", "ERROR"]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    content_preview: Optional[str] = None
    error:   Optional[str] = None
    agent_source: Optional[Literal["PRO", "CON"]] = None
    matched_claim:   Optional[str] = None
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_score: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    trust_tier:  Optional[str]   = "GENERAL"

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()


class AgentResponse(BaseModel):
    """Structured response from a Pro, Con, Moderator, or FactChecker agent."""
    agent: Literal["PRO", "CON", "MODERATOR", "FACT_CHECKER"]
    round: int
    argument: str
    sources:  List[str]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verdict:   Optional[str] = None
    reasoning: Optional[str] = None
    metrics:   Optional[Dict[str, Any]] = None
    # Timestamp set by agents so the UI can show when each argument was generated
    timestamp: Optional[str] = None

    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, key: str, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val


class ModeratorVerdict(BaseModel):
    """Structured verdict from the Moderator agent."""
    verdict: Literal[
        "TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE",
        "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning:  str
    metrics:    Optional[Dict[str, Any]] = None


class ConsensusResponse(BaseModel):
    """Structured response from the consensus pre-check node."""
    verdict:    str
    reasoning:  str
    confidence: float


class DebateState(BaseModel):
    """Complete state of the debate workflow."""
    claim: str
    round: int = 1
    pro_arguments: List[str] = Field(default_factory=list)
    con_arguments: List[str] = Field(default_factory=list)
    pro_sources:   List[List[str]] = Field(default_factory=list)
    con_sources:   List[List[str]] = Field(default_factory=list)
    verdict:    Optional[str]   = None
    confidence: Optional[float] = None
    verification_results:    Optional[List[Dict[str, Any]]] = None
    pro_verification_rate:   Optional[float] = None
    con_verification_rate:   Optional[float] = None
    moderator_reasoning:     Optional[str]   = None
    metrics:     Optional[Dict[str, Any]] = None
    retry_count: int = 0
    is_cached:   Optional[bool] = False

    # Context management
    summary:    Optional[str] = ""
    num_rounds: int = 3

    # Pre-debate evidence (Tavily)
    pro_evidence:     List[Dict[str, Any]] = Field(default_factory=list)
    con_evidence:     List[Dict[str, Any]] = Field(default_factory=list)
    evidence_sources: List[Dict[str, Any]] = Field(default_factory=list)

    # Verification feedback between rounds
    verification_feedback: Optional[str] = None

    # Model provenance (optional, for logging)
    pro_model_used:       Optional[str] = None
    con_model_used:       Optional[str] = None
    moderator_model_used: Optional[str] = None
    system_status:        Optional[str] = None

    # TypedDict-style access helpers (migration compatibility)
    def __getitem__(self, item: str):
        return getattr(self, item)

    def __setitem__(self, key: str, value):
        if key not in self.__fields__:
            raise KeyError(f"Unknown DebateState field: {key!r}")
        setattr(self, key, value)

    def get(self, key: str, default=None):
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
