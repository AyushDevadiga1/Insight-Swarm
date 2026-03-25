"""
FIX FILE 1 — src/core/models.py
Fixes: P0-1 (Pydantic v2 @validator crash), P2-3 (trust_score=None crash in get_tier_label),
       P2-3 import-inside-validator anti-pattern, P0-6 (model.json() removed in v2)

Drop-in replacement for src/core/models.py.
"""
from pydantic import BaseModel, Field, field_validator   # field_validator replaces validator (Pydantic v2)
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
import logging

_MISSING = object()
_logger = logging.getLogger(__name__)   # module-level — not inside validator


class SourceVerification(BaseModel):
    """Result of verifying a single source."""
    url:    str
    status: Literal[
        "VERIFIED", "NOT_FOUND", "INVALID_URL", "TIMEOUT",
        "CONTENT_MISMATCH", "PAYWALL_RESTRICTED", "ERROR"
    ]
    confidence:      float = Field(default=0.0, ge=0.0, le=1.0)
    content_preview: Optional[str] = None
    error:           Optional[str] = None
    agent_source:    Optional[Literal["PRO", "CON"]] = None
    matched_claim:   Optional[str] = None
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_score:     float = Field(default=0.5, ge=0.0, le=1.0)   # non-Optional: eliminates None crash
    trust_tier:      str   = "GENERAL"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()   # Pydantic v2: model_dump() replaces dict()


class AgentResponse(BaseModel):
    """Structured response from a Pro, Con, Moderator, or FactChecker agent."""
    agent:      Literal["PRO", "CON", "MODERATOR", "FACT_CHECKER"]
    round:      int
    argument:   str
    sources:    List[str] = Field(default_factory=list)
    confidence: float     = Field(default=1.0, ge=0.0, le=1.0)
    verdict:    Optional[str] = None
    reasoning:  Optional[str] = None
    metrics:    Optional[Dict[str, Any]] = None
    timestamp:  Optional[str] = None

    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, key: str, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val

    def to_json(self) -> str:
        """Pydantic v2 safe serialisation — replaces removed .json()"""
        return self.model_dump_json()


class ModeratorVerdict(BaseModel):
    """Structured verdict from the Moderator agent."""
    verdict:    str   = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning:  str   = ""
    metrics:    Optional[Dict[str, Any]] = None

    # Pydantic v2: @field_validator replaces @validator
    @field_validator("verdict", mode="before")
    @classmethod
    def normalise_verdict(cls, v: Any) -> str:
        if not v:
            return "UNKNOWN"
        v = str(v).strip().upper()

        replacements = {
            "PARTIALLY_TRUE":        "PARTIALLY TRUE",
            "PARTIAL":               "PARTIALLY TRUE",
            "PARTLY TRUE":           "PARTIALLY TRUE",
            "PARTLY_TRUE":           "PARTIALLY TRUE",
            "INSUFFICIENT":          "INSUFFICIENT EVIDENCE",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT EVIDENCE",
            "NOT ENOUGH EVIDENCE":   "INSUFFICIENT EVIDENCE",
            "NOT_ENOUGH_EVIDENCE":   "INSUFFICIENT EVIDENCE",
            "UNVERIFIABLE":          "INSUFFICIENT EVIDENCE",
        }
        if v in replacements:
            return replacements[v]

        valid = {
            "TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE",
            "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR", "SYSTEM_ERROR"
        }
        if v in valid:
            return v

        _logger.warning("ModeratorVerdict: unexpected verdict %r, defaulting to UNKNOWN", v)
        return "UNKNOWN"

    def to_json(self) -> str:
        return self.model_dump_json()


class ConsensusResponse(BaseModel):
    """Structured response from the consensus pre-check node."""
    verdict:    str
    reasoning:  str
    confidence: float


class DebateState(BaseModel):
    """Complete state of the debate workflow."""
    claim:         str
    round:         int = 1
    pro_arguments: List[str]        = Field(default_factory=list)
    con_arguments: List[str]        = Field(default_factory=list)
    pro_sources:   List[List[str]]  = Field(default_factory=list)
    con_sources:   List[List[str]]  = Field(default_factory=list)
    verdict:       Optional[str]    = None
    confidence:    Optional[float]  = None
    verification_results:  Optional[List[Dict[str, Any]]] = None
    pro_verification_rate: Optional[float] = None
    con_verification_rate: Optional[float] = None
    moderator_reasoning:   Optional[str]   = None
    metrics:       Optional[Dict[str, Any]] = None
    retry_count:   int  = 0
    is_cached:     Optional[bool] = False

    summary:    Optional[str] = ""
    num_rounds: int           = 3

    pro_evidence:     List[Dict[str, Any]] = Field(default_factory=list)
    con_evidence:     List[Dict[str, Any]] = Field(default_factory=list)
    evidence_sources: List[Dict[str, Any]] = Field(default_factory=list)

    verification_feedback: Optional[str] = None

    pro_model_used:       Optional[str] = None
    con_model_used:       Optional[str] = None
    moderator_model_used: Optional[str] = None
    system_status:        Optional[str] = None

    def __getitem__(self, item: str):
        return getattr(self, item)

    def __setitem__(self, key: str, value):
        if key not in self.model_fields:   # Pydantic v2: model_fields replaces __fields__
            raise KeyError(f"Unknown DebateState field: {key!r}")
        setattr(self, key, value)

    def get(self, key: str, default=None):
        val = getattr(self, key, _MISSING)
        return default if val is _MISSING else val

    def __contains__(self, item: str) -> bool:
        return item in self.model_fields

    def keys(self):
        return self.model_fields.keys()

    def items(self):
        return ((k, getattr(self, k)) for k in self.model_fields.keys())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()   # Pydantic v2

    def to_json(self) -> str:
        """Safe Pydantic v2 JSON serialisation — use instead of .json()"""
        return self.model_dump_json()

    @classmethod
    def from_dict(cls, data: dict) -> "DebateState":
        """Safe Pydantic v2 deserialisation — use instead of .parse_obj()"""
        return cls.model_validate(data)
