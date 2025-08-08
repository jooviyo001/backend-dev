#!/usr/bin/env python3
"""
重新初始化数据库脚本
清空现有数据并重新创建，确保admin密码为admin123
"""

import sys
import os
from sqlalchemy.orm import Session
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import engine, SessionLocal
from models import Base, User, Organization, Project, Task, UserRole, ProjectStatus, TaskStatus, TaskPriority, TaskType, OrganizationType
from utils.auth import get_password_hash

def reset_database():
    """重置数据库"""
    print("正在重置数据库...")
    
    # 删除所有表
    Base.metadata.drop_all(bind=engine)
    print("已删除所有表")
    
    # 重新创建表
    Base.metadata.create_all(bind=engine)
    print("已重新创建所有表")

def create_initial_data():
    """创建初始数据"""
    db = SessionLocal()
    
    try:
        print("正在创建初始数据...")
        
        # 创建管理员用户 - 确保密码是admin123
        admin_password = "admin123"
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash(admin_password),
            name="系统管理员",
            role=UserRole.ADMIN,
            organization_name="信息技术部",
            position="系统管理员",
            phone="13800138001",
            is_active=True,
            is_verified=True
        )
        db.add(admin_user)
        
        # 创建超级管理员用户
        superadmin_user = User(
            username="superadmin",
            email="superadmin@example.com",
            password_hash=get_password_hash("super123"),
            name="超级管理员",
            role=UserRole.ADMIN,
            organization_name="信息技术部",
            position="超级管理员",
            phone="13800138002",
            is_active=True,
            is_verified=True
        )
        db.add(superadmin_user)
        
        # 创建测试用户
        test_users = [
            {
                "username": "manager1",
                "email": "manager1@example.com",
                "password": "manager123",
                "name": "项目经理",
                "role": UserRole.MANAGER,
                "organization_name": "项目管理部",
                "position": "项目经理",
                "phone": "13800138011"
            },
            {
                "username": "manager2",
                "email": "manager2@example.com",
                "password": "manager123",
                "name": "部门经理",
                "role": UserRole.MANAGER,
                "organization_name": "技术部",
                "position": "部门经理",
                "phone": "13800138012"
            },
            {
                "username": "developer1",
                "email": "dev1@example.com",
                "password": "dev123",
                "name": "高级开发工程师",
                "role": UserRole.MEMBER,
                "organization_name": "开发部",
                "position": "高级开发工程师",
                "phone": "13800138021"
            },
            {
                "username": "developer2",
                "email": "dev2@example.com",
                "password": "dev123",
                "name": "前端开发工程师",
                "role": UserRole.MEMBER,
                "organization_name": "开发部",
                "position": "前端开发工程师",
                "phone": "13800138022"
            },
            {
                "username": "tester",
                "email": "tester@example.com",
                "password": "test123",
                "name": "测试工程师",
                "role": UserRole.MEMBER,
                "organization_name": "质量保证部",
                "position": "测试工程师",
                "phone": "13800138023"
            },
            {
                "username": "user1",
                "email": "user1@example.com",
                "password": "user123",
                "name": "实习生",
                "role": UserRole.USER,
                "organization_name": "开发部",
                "position": "实习生",
                "phone": "13800138031"
            }
        ]
        
        users = [admin_user, superadmin_user]
        for user_data in test_users:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                name=user_data["name"],
                role=user_data["role"],
                organization_name=user_data["organization_name"],
                position=user_data["position"],
                phone=user_data["phone"],
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
        organizations = [
            {
                "name": "示例科技公司",
                "code": "DEMO001",
                "type": OrganizationType.COMPANY,
                "description": "这是一个示例组织，用于演示系统功能",
                "website": "https://example.com"
            },
            {
                "name": "创新实验室",
                "code": "LAB001",
                "type": OrganizationType.ORGANIZATIN_NAME,
                "description": "专注于技术创新的实验室",
                "website": "https://lab.example.com"
            }
        ]
        
        created_orgs = []
        for org_data in organizations:
            organization = Organization(
                name=org_data["name"],
                code=org_data["code"],
                type=org_data["type"],
                description=org_data["description"],
                website=org_data["website"],
                is_active=True
            )
            db.add(organization)
            created_orgs.append(organization)
        
        db.commit()
        
        # 刷新组织对象以获取ID
        for org in created_orgs:
            db.refresh(org)
        
        # 将用户分配到组织
        # admin和superadmin分配到创新实验室
        admin_user.organization_id = created_orgs[1].id
        superadmin_user.organization_id = created_orgs[1].id
        
        # 其他用户分配到示例科技公司
        for user in users[2:]:  # 跳过admin和superadmin
            user.organization_id = created_orgs[0].id
        
        # 创建示例项目
        project = Project(
            name="示例项目",
            description="这是一个示例项目，用于演示系统功能",
            status=ProjectStatus.ACTIVE,
            start_date=datetime.now(),
            creator_id=admin_user.id,
            organization_id=created_orgs[0].id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # 创建示例任务
        tasks = [
            {
                "title": "设计系统架构",
                "description": "设计整个系统的技术架构",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "assignee_id": users[2].id  # manager1
            },
            {
                "title": "实现用户认证模块",
                "description": "实现用户登录、注册、权限验证等功能",
                "status": TaskStatus.IN_PROGRESS,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "assignee_id": users[4].id  # developer1
            },
            {
                "title": "实现项目管理模块",
                "description": "实现项目的增删改查功能",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
                "type": TaskType.FEATURE,
                "assignee_id": users[5].id  # developer2
            },
            {
                "title": "修复登录页面样式问题",
                "description": "修复登录页面在移动端显示异常的问题",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.LOW,
                "type": TaskType.BUG,
                "assignee_id": users[4].id  # developer1
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
        print("\n✅ 默认账户信息:")
        print("🔑 管理员账户:")
        print("   用户名: admin")
        print("   密码: admin123")
        print("   角色: 系统管理员")
        print()
        print("🔑 超级管理员账户:")
        print("   用户名: superadmin")
        print("   密码: super123")
        print("   角色: 超级管理员")
        print()
        print("🔑 其他测试账户:")
        print("   manager1 / manager123 (项目经理)")
        print("   manager2 / manager123 (部门经理)")
        print("   developer1 / dev123 (高级开发工程师)")
        print("   developer2 / dev123 (前端开发工程师)")
        print("   tester / test123 (测试工程师)")
        print("   user1 / user123 (实习生)")
        
    except Exception as e:
        print(f"创建初始数据时出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """主函数"""
    print("🚀 开始重新初始化数据库...")
    print("⚠️  警告: 这将删除所有现有数据!")
    
    try:
        # 重置数据库
        reset_database()
        
        # 创建初始数据
        create_initial_data()
        
        print("\n🎉 数据库初始化完成!")
        print("现在可以使用 admin / admin123 登录系统")
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()