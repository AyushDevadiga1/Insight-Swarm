import pytest
import numpy as np
import json
from src.novelty.confidence_calibration import get_calibrator

@pytest.fixture
def calibrator():
    return get_calibrator()

def test_calibrate_returns_native_float(calibrator):
    """
    ISSUE-001 Validation:
    Ensures that values produced through np matrix math are explicitly cast to native float.
    This prevents LangGraph's MemorySaver msgpack serialization from crashing.
    """
    raw_confidence = 0.5
    verdict = "TRUE"
    claim = "The Earth revolves around the sun."
    verification_results = [{"status": "VERIFIED", "trust_score": 0.95}]
    
    # Intentionally trigger underconfidence penalty
    calibrated, metadata = calibrator.calibrate(
        raw_confidence=raw_confidence,
        verdict=verdict,
        claim=claim,
        verification_results=verification_results,
        pro_args=["Abundance of evidence exists."],
        con_args=[],
        pro_sources=[["Science", "Astronomy"]],
        con_sources=[]
    )
    
    # Assert return types are exact class matches to prevent serialization failures
    assert type(calibrated) is float, f"Expected native float, got {type(calibrated)}"
    assert type(metadata["source_quality_score"]) is float
    assert type(metadata["calibrated_confidence"]) is float

    # Regression: verify JSON (and by proxy msgpack) serialization succeeds.
    # json.dumps raises TypeError on numpy scalar types, identical failure mode to msgpack.
    try:
        json.dumps({"calibrated": calibrated, "metadata": metadata})
    except TypeError as e:
        pytest.fail(f"Regression Check: JSON serialization failed — float casting broken: {e}")

def test_edge_cases_no_sources(calibrator):
    """
    Edge Case: Empty results should not crash np.mean or np.log internally.
    """
    calibrated, metadata = calibrator.calibrate(
        raw_confidence=0.9,
        verdict="FALSE",
        claim="Mars has massive flowing rivers.",
        verification_results=[],
        pro_args=[],
        con_args=[],
        pro_sources=[],
        con_sources=[]
    )
    assert 0.0 <= calibrated <= 1.0
    assert metadata["source_quality_score"] == 0.5  # hardcoded default for empty
    
def test_regression_underconfidence_boost(calibrator):
    """
    Regression Test: Validating previous mathematical logic was not severed by type casts.
    If a claim has highly lopsided evidence, a low raw confidence should boost upward.
    """
    calibrated, metadata = calibrator.calibrate(
        raw_confidence=0.4,
        verdict="TRUE",
        claim="Oxygen is required for human respiration.",
        verification_results=[{"status": "VERIFIED", "trust_score": 0.99}],
        pro_args=["Medical science explicitly states humans require oxygen."] * 5,
        con_args=[],
        pro_sources=[["Medical Journal"] * 5],
        con_sources=[]
    )
    
    # Should scale properly avoiding overconfidence
    assert calibrated > 0.4
    assert metadata["underconfidence_detected"] is True
