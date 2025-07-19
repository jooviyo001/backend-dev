@echo off
REM Script to configure Git settings for the project (Windows version)

setlocal enabledelayedexpansion

echo Configuring Git settings for the project...

REM Check if we're in a git repository
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo Error: Not in a git repository
    exit /b 1
)

REM Get project root directory
for /f "delims=" %%i in ('git rev-parse --show-toplevel') do set PROJECT_ROOT=%%i
echo Project root: %PROJECT_ROOT%

REM Function to check user info
echo Checking user information...

for /f "delims=" %%i in ('git config --get user.name 2^>nul') do set USER_NAME=%%i
for /f "delims=" %%i in ('git config --get user.email 2^>nul') do set USER_EMAIL=%%i

if "%USER_NAME%"=="" (
    echo Git user name is not set
    set /p USER_NAME="Enter your name: "
    if not "!USER_NAME!"=="" (
        git config --global user.name "!USER_NAME!"
        echo ✓ Set user name: !USER_NAME!
    )
) else (
    echo ✓ User name: %USER_NAME%
)

if "%USER_EMAIL%"=="" (
    echo Git user email is not set
    set /p USER_EMAIL="Enter your email: "
    if not "!USER_EMAIL!"=="" (
        git config --global user.email "!USER_EMAIL!"
        echo ✓ Set user email: !USER_EMAIL!
    )
) else (
    echo ✓ User email: %USER_EMAIL%
)

echo.
echo Configuring project-specific settings...

REM Set commit message template
if exist "%PROJECT_ROOT%\.gitmessage" (
    git config commit.template "%PROJECT_ROOT%\.gitmessage"
    echo ✓ Set commit message template
)

REM Set hooks path
if exist "%PROJECT_ROOT%\.githooks" (
    git config core.hooksPath "%PROJECT_ROOT%\.githooks"
    echo ✓ Set hooks path
)

REM Set line ending handling
git config core.autocrlf input
echo ✓ Set line ending handling (autocrlf)

git config core.eol lf
echo ✓ Set end of line character

REM Set file mode handling (useful for Windows)
git config core.filemode false
echo ✓ Set file mode tracking

REM Set default branch name
git config --global init.defaultBranch main
echo ✓ Set default branch name

REM Set pull strategy
git config --global pull.rebase false
echo ✓ Set pull strategy (merge)

REM Set push strategy
git config --global push.default simple
echo ✓ Set push strategy

REM Set merge strategy
git config merge.ff false
echo ✓ Set merge fast-forward strategy

echo.
echo Configuring helpful aliases...

REM Basic aliases
git config --global alias.st status
echo ✓ Set status alias

git config --global alias.co checkout
echo ✓ Set checkout alias

git config --global alias.br branch
echo ✓ Set branch alias

git config --global alias.ci commit
echo ✓ Set commit alias

git config --global alias.unstage "reset HEAD --"
echo ✓ Set unstage alias

git config --global alias.last "log -1 HEAD"
echo ✓ Set last commit alias

REM Advanced aliases
git config --global alias.lg "log --color --graph --pretty=format:'%%Cred%%h%%Creset -%%C(yellow)%%d%%Creset %%s %%Cgreen(%%cr) %%C(bold blue)<%%an>%%Creset' --abbrev-commit"
echo ✓ Set pretty log alias

git config --global alias.tree "log --graph --pretty=format:'%%Cred%%h%%Creset -%%C(yellow)%%d%%Creset %%s %%Cgreen(%%cr) %%C(bold blue)<%%an>%%Creset' --abbrev-commit --all"
echo ✓ Set tree log alias

git config --global alias.amend "commit --amend --no-edit"
echo ✓ Set amend alias

git config --global alias.fixup "commit --fixup"
echo ✓ Set fixup alias

git config --global alias.squash "commit --squash"
echo ✓ Set squash alias

git config --global alias.wip "commit -am 'WIP'"
echo ✓ Set work in progress alias

git config --global alias.undo "reset --soft HEAD~1"
echo ✓ Set undo last commit alias

git config --global alias.stash-all "stash save --include-untracked"
echo ✓ Set stash all alias

echo.
echo Configuring diff and merge tools...

REM Check for VS Code
where code >nul 2>&1
if not errorlevel 1 (
    echo VS Code detected
    set /p VSCODE_CHOICE="Configure VS Code as diff/merge tool? (y/N): "
    if /i "!VSCODE_CHOICE!"=="y" (
        git config --global diff.tool vscode
        git config --global difftool.vscode.cmd "code --wait --diff $LOCAL $REMOTE"
        git config --global merge.tool vscode
        git config --global mergetool.vscode.cmd "code --wait $MERGED"
        git config --global mergetool.keepBackup false
        echo ✓ Configured VS Code as diff/merge tool
    )
) else (
    echo VS Code not found in PATH
)

echo.
echo Configuring security settings...

REM Security settings
git config --global transfer.fsckobjects true
echo ✓ Set transfer fsck

git config --global fetch.fsckobjects true
echo ✓ Set fetch fsck

git config --global receive.fsckObjects true
echo ✓ Set receive fsck

echo.
echo Configuring performance settings...

REM Performance settings
git config --global core.preloadindex true
echo ✓ Set preload index

git config --global core.fscache true
echo ✓ Set filesystem cache

git config --global gc.auto 256
echo ✓ Set garbage collection auto

echo.
echo Current Git configuration summary:
echo User Information:
for /f "delims=" %%i in ('git config --get user.name 2^>nul') do echo   Name: %%i
for /f "delims=" %%i in ('git config --get user.email 2^>nul') do echo   Email: %%i

echo.
echo Project Settings:
for /f "delims=" %%i in ('git config --get commit.template 2^>nul') do echo   Commit template: %%i
for /f "delims=" %%i in ('git config --get core.hooksPath 2^>nul') do echo   Hooks path: %%i
for /f "delims=" %%i in ('git config --get core.autocrlf 2^>nul') do echo   Line endings: %%i
for /f "delims=" %%i in ('git config --get init.defaultBranch 2^>nul') do echo   Default branch: %%i

echo.
echo Tools:
for /f "delims=" %%i in ('git config --get diff.tool 2^>nul') do echo   Diff tool: %%i
for /f "delims=" %%i in ('git config --get merge.tool 2^>nul') do echo   Merge tool: %%i

echo.
echo Git configuration completed!
echo.
echo Next steps:
echo 1. Test commit message template:
echo    git commit (will open editor with template)
echo.
echo 2. Test aliases:
echo    git st (status)
echo    git lg (pretty log)
echo    git tree (branch tree)
echo.
echo 3. Install Git hooks:
echo    .githooks\install-hooks.bat
echo.
echo 4. View current config:
echo    git config --list
echo.
echo Happy coding! 🚀

pause
exit /b 0