#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表和初始数据
"""

from argparse import Action
import sys
import os
from tkinter import ACTIVE
from fastapi import status
from sqlalchemy.orm import Session
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import engine, SessionLocal
from models.models import Base, User, Organization, Project, Task, UserRole, ProjectStatus, TaskStatus, TaskPriority, TaskType, OrganizationType
from utils.auth import get_password_hash

def create_tables():
    """创建数据库表"""
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成")

def create_initial_data():
    """创建初始数据"""
    db = SessionLocal()
    
    try:
        print("正在创建初始数据...")
        
        # 检查是否已有管理员用户
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            print("管理员用户已存在，跳过创建")
            return
        
        # 创建管理员用户
        admin_password = "admin123"  # 生产环境请修改默认密码
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash(admin_password),
            name="系统管理员",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True
        )
        db.add(admin_user)
        
        # 创建测试用户
        test_users = [
            {
                "username": "manager",
                "email": "manager@example.com",
                "password": "manager123",
                "name": "项目经理",
                "role": UserRole.MANAGER
            },
            {
                "username": "developer1",
                "email": "dev1@example.com",
                "password": "dev123",
                "name": "开发者1",
                "role": UserRole.MEMBER
            },
            {
                "username": "developer2",
                "email": "dev2@example.com",
                "password": "dev123",
                "name": "开发者2",
                "role": UserRole.MEMBER
            }
        ]
        
        users = [admin_user]
        for user_data in test_users:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                name=user_data["name"],
                role=user_data["role"],
                is_active=True,
                is_verified=True
            )
            db.add(user)
            users.append(user)
        
        db.commit()
        
        # 刷新用户对象以获取ID
        for user in users:
            db.refresh(user)
        
        # 创建示例组织
        organization = Organization(
            name="chemi科技公司",
            code="DEMO001",
            type=OrganizationType.COMPANY,
            status=ACTIVE,
            description="这是一个示例组织，用于演示系统功能",
            website="https://example.com",
            is_active=True
        )
        db.add(organization)
        db.commit()
        db.refresh(organization)
        
        # 将用户添加到组织
        for user in users:
            organization.members.append(user)
        
        # 创建示例项目
        project = Project(
            name="示例项目",
            description="这是一个示例项目，用于演示系统功能",
            status=ProjectStatus.ACTIVE,
            start_date=datetime.now(),
            creator_id=admin_user.id,
            organization_id=organization.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # 将用户添加到项目
        for user in users:
            project.members.append(user)
        
        # 创建示例任务
        tasks = [
            {
                "title": "设计系统架构",
                "description": "设计整个系统的技术架构",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "assignee_id": users[1].id  # manager
            },
            {
                "title": "实现用户认证模块",
                "description": "实现用户登录、注册、权限验证等功能",
                "status": TaskStatus.IN_PROGRESS,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "assignee_id": users[2].id  # developer1
            },
            {
                "title": "实现项目管理模块",
                "description": "实现项目的增删改查功能",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
                "type": TaskType.FEATURE,
                "assignee_id": users[3].id  # developer2
            },
            {
                "title": "修复登录页面样式问题",
                "description": "修复登录页面在移动端显示异常的问题",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.LOW,
                "type": TaskType.BUG,
                "assignee_id": users[2].id  # developer1
            }
        ]
        
        for task_data in tasks:
            task = Task(
                title=task_data["title"],
                description=task_data["description"],
                status=task_data["status"],
                priority=task_data["priority"],
                type=task_data["type"],
                project_id=project.id,
                assignee_id=task_data["assignee_id"],
                reporter_id=admin_user.id
            )
            db.add(task)
        
        db.commit()
        
        print("初始数据创建完成")
        print("\n默认账户信息:")
        print("管理员: admin / admin123")
        print("项目经理: manager / manager123")
        print("开发者1: developer1 / dev123")
        print("开发者2: developer2 / dev123")
        
    except Exception as e:
        print(f"创建初始数据时出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """主函数"""
    print("开始初始化数据库...")
    
    # 创建表
    create_tables()
    
    # 创建初始数据
    create_initial_data()
    
    print("数据库初始化完成！")

if __name__ == "__main__":
    main()