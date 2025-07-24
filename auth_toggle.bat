@echo off
chcp 65001 >nul
echo 🔄 切换鉴权绕过状态...
uv run python auth_toggle.py toggle
pause