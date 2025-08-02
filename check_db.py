#!/usr/bin/env python3
"""
检查数据库状态
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) FROM users'))
        user_count = result.scalar()
        print(f'用户数量: {user_count}')
        
        # 检查是否有position、department和organization_id字段
        try:
            result = conn.execute(text('SELECT position, department, organization_id FROM users LIMIT 1'))
            print('position、department和organization_id字段已存在')
        except Exception as e:
            print('某些字段不存在，需要添加')
            print(f'错误详情: {e}')
            
except Exception as e:
    print(f'数据库连接错误: {e}')