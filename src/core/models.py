"""
src/core/models.py — Final production version.
ADDED: human_verdict_override field (HITL).
ADDED: parse_obj() classmethod alias for Pydantic v1 compat — used in tests.
"""
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MISSING = object()
_logger  = logging.getLogger(__name__)


class SourceVerification(BaseModel):
    url:             str
    status:          Literal["VERIFIED","NOT_FOUND","INVALID_URL","TIMEOUT",
                              "CONTENT_MISMATCH","PAYWALL_RESTRICTED","ERROR"]
    confidence:      float = Field(default=0.0, ge=0.0, le=1.0)
    content_preview: str | None   = None
    error:           str | None   = None
    agent_source:    Literal["PRO", "CON"] | None = None
    matched_claim:   str | None   = None
    similarity_score: float | None = Field(default=None, ge=0.0, le=100.0)
    trust_score:     float = Field(default=0.5, ge=0.0, le=1.0)
    trust_tier:      str   = "GENERAL"

    def to_dict(self) -> dict[str, Any]:
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
    sources:    list[str]            = Field(default_factory=list)
    confidence: float                = Field(default=1.0, ge=0.0, le=1.0)
    verdict:    str | None        = None
    reasoning:  str | None        = None
    metrics:    dict[str, Any] | None = None
    timestamp:  str | None        = None

    def __getitem__(self, item: str):        return getattr(self, item)
    def get(self, key: str, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val
    def to_json(self) -> str:                return self.model_dump_json()


class ModeratorVerdict(BaseModel):
    verdict:    str   = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning:  str   = ""
    metrics:    dict[str, Any] | None = None

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
    pro_arguments: list[str]       = Field(default_factory=list)
    con_arguments: list[str]       = Field(default_factory=list)
    pro_sources:   list[list[str]] = Field(default_factory=list)
    con_sources:   list[list[str]] = Field(default_factory=list)
    verdict:       str   = "UNKNOWN"
    confidence:    float = Field(default=0.0, ge=0.0, le=1.0)
    verification_results:  list[dict[str,Any]] = Field(default_factory=list)
    pro_verification_rate: float = 0.0
    con_verification_rate: float = 0.0
    moderator_reasoning:   str   = ""
    metrics:       dict[str,Any] = Field(default_factory=dict)
    retry_count:   int   = 0
    is_cached:     bool  = False
    summary:       str   = ""
    num_rounds:    int   = 3
    pro_evidence:     list[dict[str,Any]] = Field(default_factory=list)
    con_evidence:     list[dict[str,Any]] = Field(default_factory=list)
    evidence_sources: list[dict[str,Any]] = Field(default_factory=list)
    verification_feedback: str = ""
    sub_claims:           list[str]      = Field(default_factory=list)
    pro_model_used:       str | None  = None
    con_model_used:       str | None  = None
    moderator_model_used: str | None  = None
    system_status:        str | None  = None
    # HITL: set by /api/debate/resume when a human overrides the verdict
    human_verdict_override: str | None = None

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
    def items(self):  return ((k, getattr(self, k)) for k in self.model_fields)
    def to_dict(self) -> dict[str,Any]: return self.model_dump()
    def to_json(self) -> str:           return self.model_dump_json()

    @classmethod
    def from_dict(cls, data: dict) -> "DebateState":
        return cls.model_validate(data)

    @classmethod
    def parse_obj(cls, data: dict) -> "DebateState":
        """Pydantic v1 compatibility alias for model_validate().
        Kept for tests written against the v1 API."""
        return cls.model_validate(data)
