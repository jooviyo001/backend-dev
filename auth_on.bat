@echo off
chcp 65001 >nul
echo 🔓 启用鉴权绕过模式...
uv run python auth_toggle.py on
pause