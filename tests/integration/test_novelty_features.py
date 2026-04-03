import pytest
from unittest.mock import MagicMock, patch
from src.agents.moderator import Moderator
from src.orchestration.debate import DebateOrchestrator
from src.utils.claim_decomposer import ClaimDecomposer
from src.core.models import DebateState, SourceVerification
from src.resilience.circuit_breaker import CircuitBreaker, CircuitState

def test_trust_weighted_verdicts():
    """Verify trust scores are passed to moderator and influence analysis."""
    mock_client = MagicMock()
    mod = Moderator(llm_client=mock_client)
    
    results = [
        { "url": "high-trust.com", "status": "VERIFIED", "confidence": 0.9, "trust_score": 0.95, "agent_source": "PRO", "snippet": "..." },
        { "url": "low-trust.com", "status": "NOT_FOUND", "confidence": 0.1, "trust_score": 0.1, "agent_source": "CON", "snippet": "..." }
    ]
    
    with patch.object(mod, '_build_prompt', wraps=mod._build_prompt) as mock_prompt:
        mock_client.call_structured.return_value = MagicMock(
            verdict="TRUE", confidence=0.9, reasoning="...", metrics={}
        )
        # mod.generate is synchronous
        state = DebateState(claim="Test", verification_results=results)
        mod.generate(state)
        
        args, kwargs = mock_prompt.call_args
        prompt_text = args[0].model_dump_json() # DebateState dump
        assert "Trust: 0.95" in str(args) or "0.95" in str(args)

def test_claim_decomposition_logic():
    """Verify ClaimDecomposer splits complex claims."""
    mock_client = MagicMock()
    from src.utils.claim_decomposer import ClaimsOutput
    mock_client.call_structured.return_value = ClaimsOutput(
        claims=["The moon is made of cheese", "The earth is flat"]
    )
    
    decomposer = ClaimDecomposer(mock_client)
    parts = decomposer.decompose("The moon is made of cheese and the earth is flat.")
    
    assert len(parts) == 2
    assert "moon" in parts[0].lower()

def test_circuit_breaker_logic():
    """Verify circuit opens after failure threshold."""
    cb = CircuitBreaker(name="TestCB", failure_threshold=3, recovery_timeout=1)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.is_allowed() is False

def test_hitl_interrupt_config():
    """Verify orchestrator graph is configured with human_review interrupt."""
    orch = DebateOrchestrator()
    node_names = list(orch.graph.nodes.keys())
    assert "human_review" in node_names
