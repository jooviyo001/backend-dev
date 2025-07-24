@echo off
chcp 65001 >nul
echo 🔍 查看鉴权状态...
uv run python auth_toggle.py status
pause