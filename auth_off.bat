@echo off
chcp 65001 >nul
echo 🔒 禁用鉴权绕过模式...
uv run python auth_toggle.py off
pause