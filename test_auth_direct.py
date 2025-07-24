#!/usr/bin/env python3
"""
直接测试auth模块的鉴权绕过功能
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.auth import DEBUG_SKIP_AUTH, get_current_user, require_permission
from models.database import get_db
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

print(f"🔍 DEBUG_SKIP_AUTH: {DEBUG_SKIP_AUTH}")

# 测试不带认证凭据的情况
print("\n🧪 测试不带认证凭据的get_current_user...")

try:
    # 模拟数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
    # 测试不带认证凭据
    user = get_current_user(credentials=None, db=db)
    print(f"✅ 成功获取用户: {user.username} (角色: {user.role})")
    
except Exception as e:
    print(f"❌ 获取用户失败: {e}")

print("\n🧪 测试require_permission...")
try:
    # 创建权限检查器
    permission_checker = require_permission("project:read")
    print("✅ 权限检查器创建成功")
except Exception as e:
    print(f"❌ 权限检查器创建失败: {e}")

print("\n✅ 测试完成")