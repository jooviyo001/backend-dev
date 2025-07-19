@echo off
REM Script to install Git hooks for the project (Windows version)

setlocal enabledelayedexpansion

echo Installing Git hooks...

REM Check if we're in a git repository
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo Error: Not in a git repository
    exit /b 1
)

REM Get the git directory
for /f "delims=" %%i in ('git rev-parse --git-dir') do set GIT_DIR=%%i
set HOOKS_DIR=%GIT_DIR%\hooks
set PROJECT_HOOKS_DIR=%CD%\.githooks

echo Git directory: %GIT_DIR%
echo Hooks directory: %HOOKS_DIR%
echo Project hooks directory: %PROJECT_HOOKS_DIR%

REM Check if project hooks directory exists
if not exist "%PROJECT_HOOKS_DIR%" (
    echo Error: Project hooks directory not found: %PROJECT_HOOKS_DIR%
    exit /b 1
)

REM Create hooks directory if it doesn't exist
if not exist "%HOOKS_DIR%" (
    mkdir "%HOOKS_DIR%"
    echo Created hooks directory: %HOOKS_DIR%
)

set HOOKS_INSTALLED=0
set HOOKS_FAILED=0

echo Installing hooks...

REM Function to install a hook
REM install_hook hook_name
:install_hook
set hook_name=%1
set source_file=%PROJECT_HOOKS_DIR%\%hook_name%
set target_file=%HOOKS_DIR%\%hook_name%

if not exist "%source_file%" (
    echo Warning: Hook file not found: %source_file%
    set /a HOOKS_FAILED+=1
    goto :eof
)

REM Backup existing hook if it exists
if exist "%target_file%" (
    echo Backing up existing %hook_name% hook
    for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATE=%%c%%a%%b
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a%%b
    set TIMESTAMP=!DATE!_!TIME!
    copy "%target_file%" "%target_file%.backup.!TIMESTAMP!" >nul
)

REM Copy the hook
copy "%source_file%" "%target_file%" >nul
if errorlevel 1 (
    echo Error: Failed to copy %hook_name% hook
    set /a HOOKS_FAILED+=1
    goto :eof
)

echo ✓ Installed %hook_name% hook
set /a HOOKS_INSTALLED+=1
goto :eof

REM Install hooks
call :install_hook pre-commit
call :install_hook commit-msg
call :install_hook pre-push

REM Install any other hooks found in the project hooks directory
echo Checking for additional hooks...
for %%f in ("%PROJECT_HOOKS_DIR%\*") do (
    set "filename=%%~nxf"
    REM Skip if it's a script file or documentation
    if not "!filename!"=="install-hooks.sh" (
        if not "!filename!"=="install-hooks.bat" (
            if not "!filename:~-3!"==".md" (
                if not "!filename:~-4!"==".txt" (
                    if not "!filename!"=="pre-commit" (
                        if not "!filename!"=="commit-msg" (
                            if not "!filename!"=="pre-push" (
                                call :install_hook "!filename!"
                            )
                        )
                    )
                )
            )
        )
    )
)

REM Configure Git to use the hooks directory (Git 2.9+)
echo Configuring Git hooks path...
git config core.hooksPath "%PROJECT_HOOKS_DIR%" 2>nul
if errorlevel 1 (
    echo Warning: Could not configure Git hooks path
    echo Using traditional hooks installation method
) else (
    echo ✓ Configured Git to use project hooks directory
    echo Note: This requires Git 2.9 or later
)

REM Summary
echo.
echo Installation Summary:
echo ✓ Hooks installed: %HOOKS_INSTALLED%
if %HOOKS_FAILED% gtr 0 (
    echo ✗ Hooks failed: %HOOKS_FAILED%
)

echo.
echo Installed hooks:
for %%f in ("%HOOKS_DIR%\*") do (
    if exist "%%f" (
        echo   - %%~nxf
    )
)

echo.
echo Hook descriptions:
echo   pre-commit:  Runs code quality checks before each commit
echo   commit-msg:  Validates commit message format (conventional commits)
echo   pre-push:    Runs comprehensive checks before pushing to remote

echo.
echo Git hooks installation completed!
echo.
echo Next steps:
echo 1. Install development dependencies:
echo    pip install -r requirements-dev.txt
echo.
echo 2. Test the hooks:
echo    git add . ^&^& git commit -m "test: verify hooks installation"
echo.
echo 3. To bypass hooks temporarily (not recommended):
echo    git commit --no-verify
echo    git push --no-verify
echo.
echo 4. To uninstall hooks:
echo    del "%HOOKS_DIR%\pre-commit" "%HOOKS_DIR%\commit-msg" "%HOOKS_DIR%\pre-push"
echo    git config --unset core.hooksPath
echo.
echo Happy coding! 🚀

pause
exit /b 0