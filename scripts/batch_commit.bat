@echo off
setlocal enabledelayedexpansion

echo ########################################################
echo # InsightSwarm Granular Commit Automation             #
echo ########################################################

:: Create a temporary file list
set "TEMP_FILES=git_status_list.txt"
git status --porcelain > %TEMP_FILES%

:: Define commit messages for specific files
set "msg_api_server_py=feat(api): HITL resume endpoint and status API"
set "msg_src_agents_moderator_py=feat(agents): trust-weighted verdicts and influence scores"
set "msg_src_llm_client_py=feat(llm): circuit breakers for provider resilience"
set "msg_src_orchestration_debate_py=feat(orch): claim decomposition and HITL flow"
set "msg_frontend_src_index_css=style(ui): expert HITL review and pulse animations"
set "msg_frontend_src_store_useDebateStore_js=feat(store): state management for pending expert reviews"
set "msg_pytest_ini=config(test): set asyncio_mode to auto for integration suites"
set "msg_api_websocket_hitl_py=feat(back): HITL notification infrastructure via websockets"
set "msg_frontend_src_components_pipeline_HITLReviewPanel_jsx=feat(ui): expert review panel with source overrides"
set "msg_tests_integration_test_novelty_features_py=test(core): integrate novelty verification suite"
set "msg_tests_test_moderator_weighting_py=test(agent): verify trust-weighted scoring formulas"
set "msg_COMPREHENSIVE_NOVELTY_AUDIT_md=docs(audit): novelty implementation audit"
set "msg_FINAL_VERIFICATION_REPORT_md=docs(report): final implementation verification report"
set "msg_D22_progress_md=docs(day): progress report for day 22"
set "msg_src_resilience_retry_handler_py=chore(resilience): remove legacy retry handler"

:: Loop through files in git status and perform granular commits
for /f "tokens=1,2*" %%a in (%TEMP_FILES%) do (
    set "status=%%a"
    set "file=%%b"
    if "%%c" neq "" set "file=%%b %%c"

    echo Staging and committing: !file!
    
    :: Logic for commit message based on file path
    set "clean_file=!file:\=_!"
    set "clean_file=!clean_file:/=_!"
    set "clean_file=!clean_file:.=_!"
    
    set "custom_msg="
    if "!file!"=="api/server.py" set "custom_msg=%msg_api_server_py%"
    if "!file!"=="src/agents/moderator.py" set "custom_msg=%msg_src_agents_moderator_py%"
    if "!file!"=="src/llm/client.py" set "custom_msg=%msg_src_llm_client_py%"
    if "!file!"=="src/orchestration/debate.py" set "custom_msg=%msg_src_orchestration_debate_py%"
    if "!file!"=="frontend/src/index.css" set "custom_msg=%msg_frontend_src_index_css%"
    if "!file!"=="frontend/src/store/useDebateStore.js" set "custom_msg=%msg_frontend_src_store_useDebateStore_js%"
    if "!file!"=="pytest.ini" set "custom_msg=%msg_pytest_ini%"
    if "!file!"=="api/websocket_hitl.py" set "custom_msg=%msg_api_websocket_hitl_py%"
    if "!file!"=="frontend/src/components/pipeline/HITLReviewPanel.jsx" set "custom_msg=%msg_frontend_src_components_pipeline_HITLReviewPanel_jsx%"
    if "!file!"=="tests/integration/test_novelty_features.py" set "custom_msg=%msg_tests_integration_test_novelty_features_py%"
    if "!file!"=="tests/test_moderator_weighting.py" set "custom_msg=%msg_tests_test_moderator_weighting_py%"
    if "!file!"=="COMPREHENSIVE_NOVELTY_AUDIT.md" set "custom_msg=%msg_COMPRE_NOVELTY_AUDIT_md%"
    if "!file!"=="FINAL_VERIFICATION_REPORT.md" set "custom_msg=%msg_FINAL_VERIFICATION_REPORT_md%"
    if "!file!"=="D22/progress.md" set "custom_msg=%msg_D22_progress_md%"
    if "!file!"=="src/resilience/retry_handler.py" set "custom_msg=%msg_src_resilience_retry_handler_py%"
    
    if "!custom_msg!"=="" (
        set "custom_msg=chore(update): update !file!"
    )

    if "!status!"=="D" (
        git rm "!file!"
    ) else (
        git add "!file!"
    )
    
    git commit -m "!custom_msg!"
)

:: Commit the script itself
echo Commit the script itself
git add scripts/batch_commit.bat
git commit -m "chore(git): add granular commit automation script"

:: Clean up
del %TEMP_FILES%
echo ########################################################
echo # DONE: Granular commits finished successfully.        #
echo ########################################################
