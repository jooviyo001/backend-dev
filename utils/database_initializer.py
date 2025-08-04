#!/usr/bin/env python3
"""
数据库初始化器
用于在开发环境中初始化数据库结构和数据
注意：生产环境不应使用此脚本
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import engine, SessionLocal
from models.models import (
    Base, User, Organization, Project, Task, TaskAttachment, TaskComment,
    UserRole, ProjectStatus, TaskStatus, TaskPriority, TaskType,
    OrganizationType, OrganizationStatus
)
from utils.auth import get_password_hash
from utils.snowflake import generate_snowflake_id


class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, force_init: bool = False):
        """
        初始化数据库初始化器
        
        Args:
            force_init: 是否强制初始化（删除现有数据）
        """
        self.force_init = force_init
        self.db = SessionLocal()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
    
    def check_environment(self) -> bool:
        """检查是否为开发环境"""
        env = os.getenv('ENVIRONMENT', 'development').lower()
        debug = os.getenv('DEBUG', 'true').lower() == 'true'
        
        if env == 'production' and not self.force_init:
            print("❌ 检测到生产环境，拒绝执行数据库初始化")
            print("   如果确实需要在生产环境初始化，请设置 force_init=True")
            return False
            
        if not debug and not self.force_init:
            print("❌ 检测到非调试模式，拒绝执行数据库初始化")
            return False
            
        print(f"✅ 环境检查通过 (环境: {env}, 调试模式: {debug})")
        return True
    
    def drop_all_tables(self):
        """删除所有表（仅开发环境）"""
        if not self.force_init:
            return
            
        print("🗑️  正在删除所有表...")
        try:
            Base.metadata.drop_all(bind=engine)
            print("✅ 所有表已删除")
        except Exception as e:
            print(f"❌ 删除表时出错: {e}")
            raise
    
    def create_tables(self):
        """创建数据库表"""
        print("🏗️  正在创建数据库表...")
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库表创建完成")
        except Exception as e:
            print(f"❌ 创建表时出错: {e}")
            raise
    
    def check_existing_data(self) -> bool:
        """检查是否已有数据"""
        try:
            user_count = self.db.query(User).count()
            org_count = self.db.query(Organization).count()
            
            if user_count > 0 or org_count > 0:
                print(f"📊 检测到现有数据 (用户: {user_count}, 组织: {org_count})")
                if not self.force_init:
                    print("⚠️  数据库已有数据，跳过初始化")
                    return True
                else:
                    print("🔄 强制模式，将清除现有数据")
                    
            return False
        except Exception as e:
            print(f"⚠️  检查现有数据时出错: {e}")
            return False
    
    def create_users(self) -> List[User]:
        """创建用户数据"""
        print("👥 正在创建用户数据...")
        
        users_data = [
            {
                "username": "admin",
                "email": "admin@example.com",
                "password": "admin123",
                "name": "系统管理员",
                "role": UserRole.ADMIN,
                "phone": "13800138000"
            },
            {
                "username": "manager",
                "email": "manager@example.com",
                "password": "manager123",
                "name": "项目经理",
                "role": UserRole.MANAGER,
                "phone": "13800138001"
            },
            {
                "username": "member",
                "email": "member@example.com",
                "password": "member123",
                "name": "普通成员",
                "role": UserRole.MEMBER,
                "phone": "13800138002"
            },
            {
                "username": "alice",
                "email": "alice@example.com",
                "password": "alice123",
                "name": "Alice Wang",
                "role": UserRole.MEMBER,
                "phone": "13800138003"
            },
            {
                "username": "user",
                "email": "user@example.com",
                "password": "user123",
                "name": "普通用户",
                "role": UserRole.MEMBER,
                "phone": "13800138004"
            }
        ]
        
        users = []
        for user_data in users_data:
            user = User(
                id=generate_snowflake_id(),
                username=user_data["username"],
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                name=user_data["name"],
                role=user_data["role"],
                phone=user_data.get("phone"),
                is_active=True,
                is_verified=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.db.add(user)
            users.append(user)
        
        self.db.commit()
        
        # 刷新用户对象以获取ID
        for user in users:
            self.db.refresh(user)
        
        print(f"✅ 创建了 {len(users)} 个用户")
        return users
    
    def create_organizations(self, users: List[User]) -> List[Organization]:
        """创建组织数据"""
        print("🏢 正在创建组织数据...")
        
        orgs_data = [
            {
                "name": "示例科技公司",
                "code": "TECH001",
                "type": OrganizationType.COMPANY,
                "description": "一家专注于软件开发的科技公司",
                "website": "https://example-tech.com"
            },
            {
                "name": "创新实验室",
                "code": "LAB001",
                "type": OrganizationType.DEPARTMENT,
                "description": "专注于前沿技术研究的实验室",
                "website": "https://innovation-lab.com"
            }
        ]
        
        organizations = []
        for i, org_data in enumerate(orgs_data):
            org = Organization(
                id=generate_snowflake_id(),
                name=org_data["name"],
                code=org_data["code"],
                type=org_data["type"],
                status=OrganizationStatus.ACTIVE,
                description=org_data["description"],
                website=org_data["website"],
                level=1,
                sort=i,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.db.add(org)
            organizations.append(org)
        
        self.db.commit()
        
        # 刷新组织对象
        for org in organizations:
            self.db.refresh(org)
        
        # 将用户分配到组织
        for i, user in enumerate(users):
            org_index = i % len(organizations)
            organizations[org_index].members.append(user)
        
        self.db.commit()
        
        print(f"✅ 创建了 {len(organizations)} 个组织")
        return organizations
    
    def create_projects(self, users: List[User], organizations: List[Organization]) -> List[Project]:
        """创建项目数据"""
        print("📋 正在创建项目数据...")
        
        projects_data = [
            {
                "name": "项目管理系统",
                "description": "基于FastAPI和Vue.js的现代化项目管理系统",
                "status": ProjectStatus.ACTIVE,
                "start_date": datetime.now() - timedelta(days=30),
                "end_date": datetime.now() + timedelta(days=60)
            },
            {
                "name": "移动端应用",
                "description": "配套的移动端应用程序",
                "status": ProjectStatus.PLANNING,
                "start_date": datetime.now() + timedelta(days=7),
                "end_date": datetime.now() + timedelta(days=120)
            },
            {
                "name": "数据分析平台",
                "description": "企业级数据分析和可视化平台",
                "status": ProjectStatus.ACTIVE,
                "start_date": datetime.now() - timedelta(days=15),
                "end_date": datetime.now() + timedelta(days=90)
            }
        ]
        
        projects = []
        admin_user = next(u for u in users if u.role == UserRole.ADMIN)
        
        for i, project_data in enumerate(projects_data):
            org = organizations[i % len(organizations)]
            project = Project(
                id=generate_snowflake_id(),
                name=project_data["name"],
                description=project_data["description"],
                status=project_data["status"],
                start_date=project_data["start_date"],
                end_date=project_data["end_date"],
                creator_id=admin_user.id,
                organization_id=org.id,
                is_archived=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.db.add(project)
            projects.append(project)
        
        self.db.commit()
        
        # 刷新项目对象
        for project in projects:
            self.db.refresh(project)
        
        # 将用户分配到项目
        for project in projects:
            # 每个项目分配2-3个用户
            project_users = users[:3] if project == projects[0] else users[1:4]
            for user in project_users:
                project.members.append(user)
        
        self.db.commit()
        
        print(f"✅ 创建了 {len(projects)} 个项目")
        return projects
    
    def create_tasks(self, users: List[User], projects: List[Project]) -> List[Task]:
        """创建任务数据"""
        print("📝 正在创建任务数据...")
        
        tasks_data = [
            # 项目管理系统的任务
            {
                "title": "设计系统架构",
                "description": "设计整个系统的技术架构，包括前后端分离、数据库设计等",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "estimated_hours": 16,
                "actual_hours": 18,
                "project_index": 0
            },
            {
                "title": "实现用户认证模块",
                "description": "实现JWT认证、权限控制、密码加密等安全功能",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "estimated_hours": 24,
                "actual_hours": 26,
                "project_index": 0
            },
            {
                "title": "开发项目管理功能",
                "description": "实现项目的创建、编辑、删除、成员管理等功能",
                "status": TaskStatus.IN_PROGRESS,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "estimated_hours": 32,
                "actual_hours": 20,
                "project_index": 0
            },
            {
                "title": "任务管理模块",
                "description": "实现任务的增删改查、状态流转、分配等功能",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
                "type": TaskType.FEATURE,
                "estimated_hours": 28,
                "project_index": 0
            },
            {
                "title": "修复登录页面样式",
                "description": "修复登录页面在移动端显示异常的问题",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.LOW,
                "type": TaskType.BUG,
                "estimated_hours": 4,
                "project_index": 0
            },
            # 移动端应用的任务
            {
                "title": "移动端UI设计",
                "description": "设计移动端应用的用户界面和交互流程",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "estimated_hours": 40,
                "project_index": 1
            },
            {
                "title": "API接口对接",
                "description": "移动端与后端API的对接和调试",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
                "type": TaskType.FEATURE,
                "estimated_hours": 20,
                "project_index": 1
            },
            # 数据分析平台的任务
            {
                "title": "数据可视化组件",
                "description": "开发图表、仪表盘等数据可视化组件",
                "status": TaskStatus.IN_PROGRESS,
                "priority": TaskPriority.HIGH,
                "type": TaskType.FEATURE,
                "estimated_hours": 36,
                "actual_hours": 15,
                "project_index": 2
            },
            {
                "title": "数据导入功能",
                "description": "支持Excel、CSV等格式的数据导入",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
                "type": TaskType.FEATURE,
                "estimated_hours": 16,
                "project_index": 2
            }
        ]
        
        tasks = []
        admin_user = next(u for u in users if u.role == UserRole.ADMIN)
        developers = [u for u in users if u.role == UserRole.MEMBER]
        
        for i, task_data in enumerate(tasks_data):
            project = projects[task_data["project_index"]]
            assignee = developers[i % len(developers)]
            
            task = Task(
                id=generate_snowflake_id(),
                title=task_data["title"],
                description=task_data["description"],
                status=task_data["status"],
                priority=task_data["priority"],
                type=task_data["type"],
                project_id=project.id,
                assignee_id=assignee.id,
                reporter_id=admin_user.id,
                estimated_hours=task_data.get("estimated_hours"),
                actual_hours=task_data.get("actual_hours"),
                due_date=datetime.now() + timedelta(days=7 + i * 2),
                created_at=datetime.now() - timedelta(days=i),
                updated_at=datetime.now() - timedelta(days=max(0, i-1))
            )
            self.db.add(task)
            tasks.append(task)
        
        self.db.commit()
        
        print(f"✅ 创建了 {len(tasks)} 个任务")
        return tasks
    
    def create_task_comments(self, users: List[User], tasks: List[Task]):
        """创建任务评论数据"""
        print("💬 正在创建任务评论数据...")
        
        comments_data = [
            "这个功能的实现思路很清晰，赞！",
            "建议增加单元测试覆盖",
            "代码review已完成，可以合并",
            "需要优化一下性能，目前响应时间较长",
            "UI界面需要调整，与设计稿不符",
            "已完成测试，功能正常",
            "发现一个边界情况的bug，已记录",
            "文档需要更新",
            "这个方案可行，开始实施",
            "需要与产品经理确认需求细节"
        ]
        
        comments = []
        for i, task in enumerate(tasks[:6]):  # 只为前6个任务添加评论
            # 每个任务添加1-3个评论
            comment_count = (i % 3) + 1
            for j in range(comment_count):
                user = users[j % len(users)]
                comment_text = comments_data[(i * 3 + j) % len(comments_data)]
                
                comment = TaskComment(
                    id=generate_snowflake_id(),
                    content=comment_text,
                    task_id=task.id,
                    user_id=user.id,
                    created_at=datetime.now() - timedelta(hours=i * 2 + j),
                    updated_at=datetime.now() - timedelta(hours=i * 2 + j)
                )
                self.db.add(comment)
                comments.append(comment)
        
        self.db.commit()
        print(f"✅ 创建了 {len(comments)} 条任务评论")
    
    def print_summary(self, users: List[User], organizations: List[Organization], 
                     projects: List[Project], tasks: List[Task]):
        """打印初始化摘要"""
        print("\n" + "="*60)
        print("🎉 数据库初始化完成！")
        print("="*60)
        
        print(f"📊 数据统计:")
        print(f"   👥 用户: {len(users)}")
        print(f"   🏢 组织: {len(organizations)}")
        print(f"   📋 项目: {len(projects)}")
        print(f"   📝 任务: {len(tasks)}")
        
        print(f"\n🔑 默认账户信息:")
        for user in users:
            # 从用户数据中获取原始密码（这里硬编码，实际应该从配置获取）
            password_map = {
                "admin": "admin123",
                "manager": "manager123", 
                "developer": "dev123",
                "alice": "alice123",
                "bob": "bob123"
            }
            password = password_map.get(user.username, "默认密码")
            print(f"   {user.role.value}: {user.username} / {password}")
        
        print(f"\n🌐 API文档地址: http://localhost:8000/docs")
        print("="*60)
    
    def initialize(self) -> bool:
        """执行完整的数据库初始化"""
        try:
            # 环境检查
            if not self.check_environment():
                return False
            
            # 检查现有数据
            if self.check_existing_data():
                return True
            
            # 删除现有表（如果强制模式）
            if self.force_init:
                self.drop_all_tables()
            
            # 创建表结构
            self.create_tables()
            
            # 创建初始数据
            users = self.create_users()
            organizations = self.create_organizations(users)
            projects = self.create_projects(users, organizations)
            tasks = self.create_tasks(users, projects)
            self.create_task_comments(users, tasks)
            
            # 打印摘要
            self.print_summary(users, organizations, projects, tasks)
            
            return True
            
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            self.db.rollback()
            raise
        finally:
            self.db.close()


def init_database(force: bool = False) -> bool:
    """
    初始化数据库
    
    Args:
        force: 是否强制初始化（删除现有数据）
        
    Returns:
        bool: 初始化是否成功
    """
    with DatabaseInitializer(force_init=force) as initializer:
        return initializer.initialize()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库初始化工具")
    parser.add_argument("--force", action="store_true", help="强制初始化（删除现有数据）")
    
    args = parser.parse_args()
    
    success = init_database(force=args.force)
    sys.exit(0 if success else 1)