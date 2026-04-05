@echo off
setlocal enabledelayedexpansion

:: ========================================================
:: InsightSwarm Daily Commit Automation (Windows Batch)
:: Created for: 2026-04-05
:: ========================================================

:: Define ESC character for ANSI colors
for /f "tokens=1 delims=" %%a in ('powershell -Command "[char]27"') do set "ESC=%%a"
set "GREEN=%ESC%[92m"
set "CYAN=%ESC%[96m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "RESET=%ESC%[0m"

cls
echo %CYAN%########################################################%RESET%
echo %CYAN%#                                                      #%RESET%
echo %CYAN%#   %GREEN%InsightSwarm%CYAN% - Daily Commit Automation          #%RESET%
echo %CYAN%#   %YELLOW%Date: 2026-04-05%CYAN%                             #%RESET%
echo %CYAN%#                                                      #%RESET%
echo %CYAN%########################################################%RESET%
echo.

:: Check if git is initialized
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%Error: Not a git repository.%RESET%
    pause
    exit /b
)

:: Get Git Status Summary
echo %YELLOW%Summary of changes for today:%RESET%
git status --short
echo.

:: Create a temporary file list for iteration
set "TEMP_FILE_LIST=%temp%\insight_swarm_git_files.txt"
git status --porcelain > "%TEMP_FILE_LIST%"

:: Ask for a global commit prefix/message
echo %CYAN%Enter a global commit message (or press ENTER for default):%RESET%
set /p USER_MSG="> "

if "%USER_MSG%"=="" (
    set "USER_MSG=feat(daily): automated daily commit for 2026-04-05"
)

echo.
echo %GREEN%Starting batch commit process...%RESET%
echo.

:: Process each file
for /f "usebackq tokens=1,2*" %%a in ("%TEMP_FILE_LIST%") do (
    set "STATUS=%%a"
    set "FILE_PATH=%%b"
    if "%%c" neq "" set "FILE_PATH=%%b %%c"

    :: Handle untracked files with space in path
    if "!STATUS!"=="??" (
        echo %CYAN%[NEW] %RESET%!FILE_PATH!
        git add "!FILE_PATH!"
        git commit -m "feat: add !FILE_PATH!" --quiet
    ) else if "!STATUS!"=="M" (
        echo %YELLOW%[MOD] %RESET%!FILE_PATH!
        git add "!FILE_PATH!"
        git commit -m "feat(update): refinement of !FILE_PATH!" --quiet
    ) else if "!STATUS!"=="D" (
        echo %RED%[DEL] %RESET%!FILE_PATH!
        git rm "!FILE_PATH!" --quiet
        git commit -m "feat(remove): cleanup of !FILE_PATH!" --quiet
    ) else (
        echo %RESET%[OTH] !FILE_PATH!
        git add "!FILE_PATH!"
        git commit -m "!USER_MSG! (!FILE_PATH!)" --quiet
    )
)

:: Alternative: One big commit if preferred?
:: For "batch bat commits file for today", individual is usually cooler but slower.
:: I'll keep individual for "atomic" feel as per history.

:: Finalize
echo.
echo %GREEN%########################################################%RESET%
echo %GREEN%#  Batch Commit Completed Successfully!                #%RESET%
echo %GREEN%########################################################%RESET%
echo.

:: Optional: Push
echo %YELLOW%Would you like to push to origin? (y/n)%RESET%
set /p PUSH_CHOICE="> "
if /i "%PUSH_CHOICE%"=="y" (
    echo %CYAN%Pushing to origin...%RESET%
    git push
)

:: Cleanup
if exist "%TEMP_FILE_LIST%" del "%TEMP_FILE_LIST%"

echo.
echo %CYAN%Press any key to exit...%RESET%
pause >nul
