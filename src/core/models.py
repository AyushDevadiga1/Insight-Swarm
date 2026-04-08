"""
src/core/models.py — Final production version.
ADDED: human_verdict_override field (HITL).
ADDED: parse_obj() classmethod alias for Pydantic v1 compat — used in tests.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Dict, Any, Optional, Literal
import logging

_MISSING = object()
_logger  = logging.getLogger(__name__)


class SourceVerification(BaseModel):
    url:             str
    status:          Literal["VERIFIED","NOT_FOUND","INVALID_URL","TIMEOUT",
                              "CONTENT_MISMATCH","PAYWALL_RESTRICTED","ERROR"]
    confidence:      float = Field(default=0.0, ge=0.0, le=1.0)
    content_preview: Optional[str]   = None
    error:           Optional[str]   = None
    agent_source:    Optional[Literal["PRO","CON"]] = None
    matched_claim:   Optional[str]   = None
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_score:     float = Field(default=0.5, ge=0.0, le=1.0)
    trust_tier:      str   = "GENERAL"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AgentArgumentResponse(BaseModel):
    """Slim schema for Pro/Con LLM calls."""
    argument:   str
    sources:    list  = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentResponse(BaseModel):
    agent:      Literal["PRO","CON","MODERATOR","FACT_CHECKER"]
    round:      int
    argument:   str
    sources:    List[str]            = Field(default_factory=list)
    confidence: float                = Field(default=1.0, ge=0.0, le=1.0)
    verdict:    Optional[str]        = None
    reasoning:  Optional[str]        = None
    metrics:    Optional[Dict[str,Any]] = None
    timestamp:  Optional[str]        = None

    def __getitem__(self, item: str):        return getattr(self, item)
    def get(self, key: str, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val
    def to_json(self) -> str:                return self.model_dump_json()


class ModeratorVerdict(BaseModel):
    verdict:    str   = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning:  str   = ""
    metrics:    Optional[Dict[str,Any]] = None

    @field_validator("verdict", mode="before")
    @classmethod
    def normalise_verdict(cls, v: Any) -> str:
        if not v:
            return "UNKNOWN"
        v = str(v).strip().upper()
        replacements = {
            "PARTIALLY_TRUE":"PARTIALLY TRUE","PARTIAL":"PARTIALLY TRUE",
            "PARTLY TRUE":"PARTIALLY TRUE","PARTLY_TRUE":"PARTIALLY TRUE",
            "INSUFFICIENT":"INSUFFICIENT EVIDENCE","INSUFFICIENT_EVIDENCE":"INSUFFICIENT EVIDENCE",
            "NOT ENOUGH EVIDENCE":"INSUFFICIENT EVIDENCE","NOT_ENOUGH_EVIDENCE":"INSUFFICIENT EVIDENCE",
            "UNVERIFIABLE":"INSUFFICIENT EVIDENCE",
        }
        if v in replacements:
            return replacements[v]
        valid = {"TRUE","FALSE","PARTIALLY TRUE","INSUFFICIENT EVIDENCE",
                 "CONSENSUS_SETTLED","RATE_LIMITED","UNKNOWN","ERROR","SYSTEM_ERROR"}
        if v in valid:
            return v
        _logger.warning("ModeratorVerdict: unexpected verdict %r, defaulting to UNKNOWN", v)
        return "UNKNOWN"

    def to_json(self) -> str: return self.model_dump_json()


class ConsensusResponse(BaseModel):
    verdict:    str
    reasoning:  str
    confidence: float


class DebateState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    claim:         str
    round:         int = 1
    pro_arguments: List[str]       = Field(default_factory=list)
    con_arguments: List[str]       = Field(default_factory=list)
    pro_sources:   List[List[str]] = Field(default_factory=list)
    con_sources:   List[List[str]] = Field(default_factory=list)
    verdict:       str   = "UNKNOWN"
    confidence:    float = Field(default=0.0, ge=0.0, le=1.0)
    verification_results:  List[Dict[str,Any]] = Field(default_factory=list)
    pro_verification_rate: float = 0.0
    con_verification_rate: float = 0.0
    moderator_reasoning:   str   = ""
    metrics:       Dict[str,Any] = Field(default_factory=dict)
    retry_count:   int   = 0
    is_cached:     bool  = False
    summary:       str   = ""
    num_rounds:    int   = 3
    pro_evidence:     List[Dict[str,Any]] = Field(default_factory=list)
    con_evidence:     List[Dict[str,Any]] = Field(default_factory=list)
    evidence_sources: List[Dict[str,Any]] = Field(default_factory=list)
    verification_feedback: str = ""
    sub_claims:           List[str]      = Field(default_factory=list)
    pro_model_used:       Optional[str]  = None
    con_model_used:       Optional[str]  = None
    moderator_model_used: Optional[str]  = None
    system_status:        Optional[str]  = None
    # HITL: set by /api/debate/resume when a human overrides the verdict
    human_verdict_override: Optional[str] = None

    def __getitem__(self, item: str):        return getattr(self, item)
    def __setitem__(self, key: str, value):
        if key not in self.model_fields:
            raise KeyError(f"Unknown DebateState field: {key!r}")
        setattr(self, key, value)
    def get(self, key: str, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val
    def __contains__(self, item: str) -> bool: return item in self.model_fields
    def keys(self):   return self.model_fields.keys()
    def items(self):  return ((k, getattr(self, k)) for k in self.model_fields.keys())
    def to_dict(self) -> Dict[str,Any]: return self.model_dump()
    def to_json(self) -> str:           return self.model_dump_json()

    @classmethod
    def from_dict(cls, data: dict) -> "DebateState":
        return cls.model_validate(data)

    @classmethod
    def parse_obj(cls, data: dict) -> "DebateState":
        """Pydantic v1 compatibility alias for model_validate().
        Kept for tests written against the v1 API."""
        return cls.model_validate(data)
