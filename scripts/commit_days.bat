@echo off
echo Grouping commits by feature / component...

:: Frontend Commits
git add frontend/src/components/debate/AgentBubble.jsx
git add frontend/src/hooks/useSSE.js
git add frontend/src/index.css
git commit -m "feat(ui): Embed SourceHoverCard overlays, style metadata chips, and align SSE hooks"

git add frontend/src/components/layout/Sidebar.jsx
git commit -m "feat(ui): Add soft warning chip monitoring provider substitutions and fallbacks"

git add frontend/src/components/results/FeedbackPanel.jsx
git add frontend/src/components/results/SourceTable.jsx
git add frontend/src/components/status/ApiStatusPanel.jsx
git commit -m "fix(ui): Standardize panel alignments, error boundaries, and nested claim visual states"

:: Backend / Core Orchesteration Commits
git add api/server.py
git commit -m "feat(api): Emit sub_claims SSE events for multi-part queries and synchronize parsing limits"

git add src/orchestration/debate.py
git commit -m "fix(core): Populate synthetic reasoning in pro_arguments resolving consensus blank debate tabs"

git add src/core/models.py
git commit -m "feat(core): Update Pydantic schemas enforcing unified API shapes"

git add src/agents/con_agent.py
git add src/agents/pro_agent.py
git commit -m "fix(agents): Fortify prompts enforcing strict external citation compliance"

:: Test Suites Commits
git add tests/integration/test_current_system_baseline.py
git add tests/integration/conftest.py
git commit -m "test(integration): Update legacy baseline checking Pydantic properties dynamically and fix fixtures"

git add tests/integration/test_e2e_user_flows.py
git commit -m "test(integration): Patch string length boundary validations mapping to newer 3-word rule"

git add tests/integration/test_full_debate_flow.py
git commit -m "test(integration): Modify FactChecker execution triggers to bypass Consensus short circuits"

git add tests/integration/test_new_subclaims_stages.py
git add test_consensus.py
git commit -m "test(integration): Add novel stage regression checks (DECOMPOSING/SEARCHING) and scratchpad testing script"

:: Progress, Docs, Scripts Commits
git add progress/D18/progress.md
git add progress/D21/progress.md
git commit -m "docs: Retrospective documentation spanning Cache sync improvements and D21 UI enhancements"

git add progress/D21/HITL_design_stub.md
git commit -m "docs: Stub futuristic HITL (Human-in-the-Loop) design architecture specs"

git add report/insightswarm_roman_numered_pages.docx
git commit -m "docs: Update final roman numbered page reporting format"

git add scripts/commit_days.bat
git commit -m "chore: Update local automation commit script for individualized staging"

echo ==============================================
echo All Individual Commits Have Been Executed Successfully!
echo Remember to run 'git push -f' if you previously pushed the singular commit to remote!
echo ==============================================
pause
