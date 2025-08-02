#!/usr/bin/env python3
"""
验证admin用户密码
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import get_db
from models.models import User
from utils.auth import verify_password

def verify_admin_password():
    """验证admin用户密码"""
    db = next(get_db())
    
    try:
        admin_user = db.query(User).filter(User.username == 'admin').first()
        if admin_user:
            print(f'Admin用户: {admin_user.username}')
            print(f'邮箱: {admin_user.email}')
            print(f'角色: {admin_user.role}')
            print(f'状态: {admin_user.is_active}')
            
            # 验证密码
            is_valid = verify_password('admin123', admin_user.password_hash)
            print(f'密码验证 (admin123): {"✓ 正确" if is_valid else "✗ 错误"}')
            
            return is_valid
        else:
            print('未找到admin用户')
            return False
    finally:
        db.close()

if __name__ == "__main__":
    verify_admin_password()