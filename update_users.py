#!/usr/bin/env python3
"""
用户账户更新脚本
重新更新数据库中的账户，按照角色（admin、manager、member、user）进行分类
"""

import sys
import os
from sqlalchemy.orm import Session
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal
from models.models import User, Organization, UserRole
from utils.auth import get_password_hash

def update_users():
    """更新用户账户"""
    db = SessionLocal()
    
    try:
        print("开始更新用户账户...")
        
        # 删除现有用户（保留数据库结构）
        print("正在清理现有用户数据...")
        db.query(User).delete()
        db.commit()
        
        # 获取示例组织
        organization = db.query(Organization).filter(Organization.name == "示例科技公司").first()
        if not organization:
            print("未找到示例组织，创建新组织...")
            from models.models import OrganizationType
            organization = Organization(
                name="示例科技公司",
                code="DEMO001",
                type=OrganizationType.COMPANY,
                description="这是一个示例组织，用于演示系统功能",
                website="https://example.com",
                is_active=True
            )
            db.add(organization)
            db.commit()
            db.refresh(organization)
        
        # 创建新的用户账户，按角色分类
        users_data = [
            # 系统管理员 (admin)
            {
                "username": "admin",
                "email": "admin@example.com",
                "password": "admin123",
                "full_name": "系统管理员",
                "role": UserRole.ADMIN,
                "department": "信息技术部",
                "position": "系统管理员",
                "phone": "13800138001"
            },
            {
                "username": "superadmin",
                "email": "superadmin@example.com",
                "password": "super123",
                "full_name": "超级管理员",
                "role": UserRole.ADMIN,
                "department": "信息技术部",
                "position": "超级管理员",
                "phone": "13800138002"
            },
            
            # 管理者 (manager)
            {
                "username": "manager1",
                "email": "manager1@example.com",
                "password": "manager123",
                "full_name": "项目经理",
                "role": UserRole.MANAGER,
                "department": "项目管理部",
                "position": "项目经理",
                "phone": "13800138011"
            },
            {
                "username": "manager2",
                "email": "manager2@example.com",
                "password": "manager123",
                "full_name": "部门经理",
                "role": UserRole.MANAGER,
                "department": "技术部",
                "position": "部门经理",
                "phone": "13800138012"
            },
            {
                "username": "teamlead",
                "email": "teamlead@example.com",
                "password": "lead123",
                "full_name": "团队负责人",
                "role": UserRole.MANAGER,
                "department": "开发部",
                "position": "团队负责人",
                "phone": "13800138013"
            },
            
            # 普通成员 (member)
            {
                "username": "developer1",
                "email": "dev1@example.com",
                "password": "dev123",
                "full_name": "高级开发工程师",
                "role": UserRole.MEMBER,
                "department": "开发部",
                "position": "高级开发工程师",
                "phone": "13800138021"
            },
            {
                "username": "developer2",
                "email": "dev2@example.com",
                "password": "dev123",
                "full_name": "前端开发工程师",
                "role": UserRole.MEMBER,
                "department": "开发部",
                "position": "前端开发工程师",
                "phone": "13800138022"
            },
            {
                "username": "designer",
                "email": "designer@example.com",
                "password": "design123",
                "full_name": "UI设计师",
                "role": UserRole.MEMBER,
                "department": "设计部",
                "position": "UI设计师",
                "phone": "13800138023"
            },
            {
                "username": "tester",
                "email": "tester@example.com",
                "password": "test123",
                "full_name": "测试工程师",
                "role": UserRole.MEMBER,
                "department": "质量保证部",
                "position": "测试工程师",
                "phone": "13800138024"
            },
            
            # 普通用户 (user)
            {
                "username": "user1",
                "email": "user1@example.com",
                "password": "user123",
                "full_name": "实习生",
                "role": UserRole.USER,
                "department": "开发部",
                "position": "实习生",
                "phone": "13800138031"
            },
            {
                "username": "user2",
                "email": "user2@example.com",
                "password": "user123",
                "full_name": "助理",
                "role": UserRole.USER,
                "department": "行政部",
                "position": "行政助理",
                "phone": "13800138032"
            },
            {
                "username": "guest",
                "email": "guest@example.com",
                "password": "guest123",
                "full_name": "访客用户",
                "role": UserRole.USER,
                "department": "访客",
                "position": "访客",
                "phone": "13800138033"
            }
        ]
        
        created_users = []
        
        print("正在创建新用户...")
        for user_data in users_data:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"],
                department=user_data["department"],
                position=user_data["position"],
                phone=user_data["phone"],
                organization_id=organization.id,
                is_active=True,
                is_verified=True
            )
            db.add(user)
            created_users.append(user)
        
        db.commit()
        
        # 刷新用户对象以获取ID
        for user in created_users:
            db.refresh(user)
        
        # 将用户添加到组织
        for user in created_users:
            if user not in organization.members:
                organization.members.append(user)
        
        db.commit()
        
        print("用户账户更新完成！")
        print("\n=== 账户信息汇总 ===")
        
        # 按角色分组显示
        role_groups = {
            UserRole.ADMIN: "系统管理员",
            UserRole.MANAGER: "管理者", 
            UserRole.MEMBER: "普通成员",
            UserRole.USER: "普通用户"
        }
        
        for role, role_name in role_groups.items():
            print(f"\n【{role_name}】:")
            role_users = [u for u in created_users if u.role == role]
            for user in role_users:
                print(f"  - {user.username} / {user_data['password'] if any(ud['username'] == user.username for ud in users_data) else '***'} | {user.full_name} | {user.department} - {user.position}")
        
        print(f"\n总计创建用户: {len(created_users)} 个")
        print("所有用户已添加到组织: 示例科技公司")
        
    except Exception as e:
        print(f"更新用户账户时出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """主函数"""
    print("=== 用户账户更新工具 ===")
    print("此工具将重新创建数据库中的用户账户")
    print("按照四个角色进行分类: admin、manager、member、user")
    
    confirm = input("\n确认要继续吗？这将删除现有的所有用户数据！(y/N): ")
    if confirm.lower() != 'y':
        print("操作已取消")
        return
    
    update_users()
    print("\n用户账户更新完成！")

if __name__ == "__main__":
    main()