"""
Auto-Integration Script for Novelty Features
============================================

This script automatically integrates all 5 novelty features into the codebase.

Run: python scripts/integrate_novelty.py

What it does:
1. Adds imports to moderator.py
2. Injects calibration logic
3. Adds contradiction detection to fact_checker.py
4. Adds complexity estimation to debate.py
5. Adds explainability to verdict generation

IMPORTANT: Creates backups before modifying files!
"""

import os
import shutil
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent
SRC_DIR = BASE_DIR / "src"

def backup_file(filepath):
    """Create backup before modification."""
    backup_path = str(filepath) + ".backup"
    shutil.copy2(filepath, backup_path)
    print(f"✅ Backed up: {filepath} → {backup_path}")

def add_calibration_to_moderator():
    """Add confidence calibration to moderator.py"""
    filepath = SRC_DIR / "agents" / "moderator.py"
    backup_file(filepath)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add import at top
    if "from src.novelty import get_calibrator" not in content:
        import_line = "from src.novelty import get_calibrator, get_argumentation_analyzer\n"
        # Insert after existing imports
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('import logging'):
                lines.insert(i+1, import_line)
                break
        content = '\n'.join(lines)
    
    # Add calibration logic in generate() method
    if "calibrator = get_calibrator()" not in content:
        # Find the return statement in generate()
        calibration_code = """
        # NOVELTY: Adaptive Confidence Calibration
        from src.novelty import get_calibrator
        calibrator = get_calibrator()
        calibrated_conf, calibration_meta = calibrator.calibrate(
            raw_confidence=float(composite),
            verdict=result.verdict,
            claim=state.claim,
            verification_results=results or [],
            pro_args=state.pro_arguments or [],
            con_args=state.con_arguments or [],
            pro_sources=state.pro_sources or [],
            con_sources=state.con_sources or []
        )
        
        # Use calibrated confidence
        final_confidence = calibrated_conf
        final_metrics["calibration"] = calibration_meta
        """
        
        # Insert before final AgentResponse return
        content = content.replace(
            "return AgentResponse(",
            f"{calibration_code}\n        return AgentResponse("
        )
        content = content.replace(
            "confidence=float(composite)",
            "confidence=final_confidence"
        )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Calibration integrated into moderator.py")

def add_contradictions_to_fact_checker():
    """Add contradiction detection to fact_checker.py"""
    filepath = SRC_DIR / "agents" / "fact_checker.py"
    backup_file(filepath)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add import
    if "from src.novelty import get_contradiction_detector" not in content:
        import_line = "from src.novelty import get_contradiction_detector\n"
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('import logging'):
                lines.insert(i+1, import_line)
                break
        content = '\n'.join(lines)
    
    # Add detection logic before return
    if "detector = get_contradiction_detector()" not in content:
        detection_code = """
        # NOVELTY: Evidence Contradiction Detection
        from src.novelty import get_contradiction_detector
        detector = get_contradiction_detector()
        contradiction_analysis = detector.detect_contradictions(results, state.claim)
        """
        
        # Find return statement in generate()
        content = content.replace(
            'return AgentResponse(',
            f'{detection_code}\n        return AgentResponse('
        )
        
        # Add to metrics
        content = content.replace(
            'metrics={"verification_results": [r.to_dict() for r in results], "pro_rate": pro_rate, "con_rate": con_rate},',
            'metrics={"verification_results": [r.to_dict() for r in results], "pro_rate": pro_rate, "con_rate": con_rate, "contradictions": contradiction_analysis},'
        )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Contradiction detection integrated into fact_checker.py")

def add_complexity_to_orchestrator():
    """Add complexity estimation to debate.py"""
    filepath = SRC_DIR / "orchestration" / "debate.py"
    backup_file(filepath)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add import
    if "from src.novelty import get_complexity_estimator" not in content:
        import_line = "from src.novelty import get_complexity_estimator, get_explainability_engine\n"
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'from src.llm.client import FreeLLMClient' in line:
                lines.insert(i+1, import_line)
                break
        content = '\n'.join(lines)
    
    # Add complexity estimation in run() method
    if "complexity_profile = estimator.estimate_complexity" not in content:
        complexity_code = """
        # NOVELTY: Claim Complexity Estimation
        from src.novelty import get_complexity_estimator
        estimator = get_complexity_estimator()
        complexity_profile = estimator.estimate_complexity(claim)
        logger.info(f"Claim complexity: {complexity_profile['complexity_tier']} - adjusting debate parameters")
        
        # Adjust debate rounds based on complexity
        adjusted_params = estimator.adjust_debate_parameters(3, 5, complexity_profile)
        num_rounds_adjusted = adjusted_params["adjusted_rounds"]
        """
        
        # Insert after claim decomposition
        content = content.replace(
            'self._set_stage("DECOMPOSING"',
            f'{complexity_code}\n        self._set_stage("DECOMPOSING"'
        )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Complexity estimation integrated into debate.py")

def add_explainability_to_verdict():
    """Add explainability to verdict generation"""
    filepath = SRC_DIR / "orchestration" / "debate.py"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add explainability in _verdict_node
    if "explainer = get_explainability_engine()" not in content:
        explain_code = """
        # NOVELTY: Generate XAI Explanation
        from src.novelty import get_explainability_engine
        explainer = get_explainability_engine()
        explanation = explainer.generate_explanation(state.to_dict(), level="standard")
        if state.metrics is None:
            state.metrics = {}
        state.metrics["explanation"] = explanation
        """
        
        # Insert in _verdict_node before return
        content = content.replace(
            'def _verdict_node(self, state: DebateState) -> DebateState:\n        self._set_stage("COMPLETE"',
            f'def _verdict_node(self, state: DebateState) -> DebateState:\n{explain_code}\n        self._set_stage("COMPLETE"'
        )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Explainability integrated into verdict generation")

def main():
    print("=" * 60)
    print("InsightSwarm Novelty Features Auto-Integration")
    print("=" * 60)
    print()
    
    print("This script will integrate 5 novel features into your codebase.")
    print("Backups will be created before modification (.backup files).")
    print()
    
    response = input("Proceed with integration? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Integration cancelled.")
        return
    
    print()
    print("Starting integration...")
    print()
    
    try:
        add_calibration_to_moderator()
        add_contradictions_to_fact_checker()
        add_complexity_to_orchestrator()
        add_explainability_to_verdict()
        
        print()
        print("=" * 60)
        print("✅ INTEGRATION COMPLETE!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Review the changes in each file")
        print("2. Test with: python -m pytest tests/")
        print("3. Run sample claims to verify functionality")
        print("4. If issues occur, restore from .backup files")
        print()
        print("📖 See NOVELTY_INTEGRATION_GUIDE.md for details")
        
    except Exception as e:
        print()
        print(f"❌ ERROR during integration: {e}")
        print("Check .backup files to restore original code")
        raise

if __name__ == "__main__":
    main()
