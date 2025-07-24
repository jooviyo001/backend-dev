#!/usr/bin/env python3
"""
调试环境变量加载
"""
import os
from dotenv import load_dotenv

print("🔍 调试环境变量加载...")

# 加载环境变量
load_dotenv()

# 检查环境变量
debug_skip_auth = os.getenv("DEBUG_SKIP_AUTH", "false")
print(f"DEBUG_SKIP_AUTH (原始值): '{debug_skip_auth}'")
print(f"DEBUG_SKIP_AUTH (转换后): {debug_skip_auth.lower() == 'true'}")

# 检查.env文件内容
print("\n📋 .env文件中的DEBUG_SKIP_AUTH配置:")
try:
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'DEBUG_SKIP_AUTH' in line:
                print(f"第{i}行: {line.strip()}")
except Exception as e:
    print(f"读取.env文件失败: {e}")

# 测试auth模块
print("\n🔧 测试auth模块...")
try:
    from utils.auth import DEBUG_SKIP_AUTH as auth_debug_skip
    print(f"utils.auth.DEBUG_SKIP_AUTH: {auth_debug_skip}")
except Exception as e:
    print(f"导入auth模块失败: {e}")