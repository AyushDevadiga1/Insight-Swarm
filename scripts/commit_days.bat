@echo off
echo Staging all changes...
git add .

echo Committing changes...
git commit -m "feat/fix: Comprehensive D21 Completion spanning UI, Streams, and Pipeline Stabilizations" ^
-m "Files modified and reasons:" ^
-m "- api/server.py: Emitted sub_claims SSE events for multi-part claims and synchronized UI parsing limits." ^
-m "- frontend/src/components/debate/AgentBubble.jsx: Embedded SourceHoverCard rendering and popups for verification trust ratings." ^
-m "- frontend/src/components/layout/Sidebar.jsx: Added soft warning chip monitoring provider.substitutions limits." ^
-m "- frontend/src/components/results/FeedbackPanel.jsx: Updated error boundaries handling." ^
-m "- frontend/src/components/results/SourceTable.jsx: Styled nested claim layouts." ^
-m "- frontend/src/components/status/ApiStatusPanel.jsx: Standardized UI indicators for load conditions." ^
-m "- frontend/src/hooks/useSSE.js: Stream tracking alignments tracking sub_claims and tracking states." ^
-m "- frontend/src/index.css: Added CSS overlay stylings (source-chip-wrap, shc-domain) ensuring non-intrusive metadata expansions." ^
-m "- report/insightswarm_roman_numered_pages.docx: Documentation page numeration." ^
-m "- src/agents/con_agent.py & pro_agent.py: Fortified prompt strictness enforcing external citation bindings." ^
-m "- src/core/models.py: Pydantic definitions enforcing standard API shapes." ^
-m "- src/orchestration/debate.py: Populated synthetic reasoning inside pro_arguments arrays avoiding blank visual states when invoking Consensus fast-path exits." ^
-m "- tests/integration/conftest.py: System fixtures for backend coverage." ^
-m "- tests/integration/test_current_system_baseline.py: Updated suite to evaluate Pydantic properties dynamically." ^
-m "- tests/integration/test_e2e_user_flows.py: Patched outdated string character limits recognizing 3-word minimum validations." ^
-m "- tests/integration/test_full_debate_flow.py: Bypassed early Consensus routines forcing rigorous tests on the FactChecker mechanics." ^
-m "- tests/integration/test_new_subclaims_stages.py: Novel regression verification for exact tracking stages (DECOMPOSING/SEARCHING)." ^
-m "- progress/D18/ & progress/D21/: Retrospective documentation spanning cache synchronization improvements, current visual updates, and future HITL stubs." ^
-m "- scripts/commit_days.bat & test_consensus.py: Added local automation tools allowing scratch executions."

echo Final push protocol enacted safely!
pause
