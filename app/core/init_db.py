from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import async_session, engine
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task
from app.models.file import File
from app.models import Base
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def create_tables():
    """创建数据库表"""
    try:
        async with engine.begin() as conn:
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"创建数据库表失败: {e}")
        raise

async def create_admin_user(db: AsyncSession):
    """创建管理员用户"""
    try:
        # 检查是否已存在管理员用户
        result = await db.execute(
            select(User).where(User.username == settings.admin_username)
        )
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            logger.info(f"管理员用户 {settings.admin_username} 已存在")
            return existing_admin
        
        # 创建管理员用户
        admin_user = User(
            username=settings.admin_username,
            name="系统管理员",
            email=settings.admin_email,
            hashed_password=get_password_hash(settings.admin_password),
            role="admin",
            status="active",
            department="IT部门",
            phone="13800138000",
            is_verified=True
        )
        
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
        
        logger.info(f"管理员用户 {settings.admin_username} 创建成功")
        return admin_user
        
    except Exception as e:
        logger.error(f"创建管理员用户失败: {e}")
        await db.rollback()
        raise

async def create_sample_organization(db: AsyncSession, admin_user: User):
    """创建示例组织"""
    try:
        # 检查是否已存在示例组织
        result = await db.execute(
            select(Organization).where(Organization.name == "示例公司")
        )
        existing_org = result.scalar_one_or_none()
        
        if existing_org:
            logger.info("示例组织已存在")
            return existing_org
        
        # 创建根组织
        root_org = Organization(
            name="示例公司",
            description="这是一个示例公司，用于演示项目管理系统",
            type="company",
            email="contact@example.com",
            phone="400-123-4567",
            address="北京市朝阳区示例大厦"
        )
        
        db.add(root_org)
        await db.flush()  # 获取ID但不提交
        
        # 创建子部门
        departments = [
            {
                "name": "技术部",
                "description": "负责产品研发和技术支持",
                "type": "department"
            },
            {
                "name": "产品部",
                "description": "负责产品规划和需求管理",
                "type": "department"
            },
            {
                "name": "运营部",
                "description": "负责产品运营和市场推广",
                "type": "department"
            }
        ]
        
        created_departments = []
        for dept_data in departments:
            dept = Organization(
                name=dept_data["name"],
                description=dept_data["description"],
                type=dept_data["type"],
                parent_id=root_org.id
            )
            db.add(dept)
            created_departments.append(dept)
        
        # 将管理员添加到根组织
        root_org.members.append(admin_user)
        
        await db.commit()
        
        # 刷新所有对象
        await db.refresh(root_org)
        for dept in created_departments:
            await db.refresh(dept)
        
        logger.info("示例组织创建成功")
        return root_org
        
    except Exception as e:
        logger.error(f"创建示例组织失败: {e}")
        await db.rollback()
        raise

async def create_sample_users(db: AsyncSession, organization: Organization):
    """创建示例用户"""
    try:
        sample_users_data = [
            {
                "username": "manager1",
                "name": "张经理",
                "email": "manager1@example.com",
                "role": "manager",
                "department": "技术部"
            },
            {
                "username": "developer1",
                "name": "李开发",
                "email": "developer1@example.com",
                "role": "user",
                "department": "技术部"
            },
            {
                "username": "developer2",
                "name": "王程序员",
                "email": "developer2@example.com",
                "role": "user",
                "department": "技术部"
            },
            {
                "username": "product1",
                "name": "陈产品",
                "email": "product1@example.com",
                "role": "user",
                "department": "产品部"
            },
            {
                "username": "operation1",
                "name": "刘运营",
                "email": "operation1@example.com",
                "role": "user",
                "department": "运营部"
            }
        ]
        
        created_users = []
        for user_data in sample_users_data:
            # 检查用户是否已存在
            result = await db.execute(
                select(User).where(User.username == user_data["username"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info(f"用户 {user_data['username']} 已存在")
                created_users.append(existing_user)
                continue
            
            user = User(
                username=user_data["username"],
                name=user_data["name"],
                email=user_data["email"],
                hashed_password=get_password_hash("password123"),
                role=user_data["role"],
                status="active",
                department=user_data["department"],
                is_verified=True
            )
            
            db.add(user)
            created_users.append(user)
            
            # 将用户添加到组织
            organization.members.append(user)
        
        await db.commit()
        
        # 刷新所有用户对象
        for user in created_users:
            await db.refresh(user)
        
        logger.info(f"创建了 {len(created_users)} 个示例用户")
        return created_users
        
    except Exception as e:
        logger.error(f"创建示例用户失败: {e}")
        await db.rollback()
        raise

async def create_sample_projects(db: AsyncSession, manager: User, organization: Organization, users: list):
    """创建示例项目"""
    try:
        from datetime import datetime, timedelta
        
        sample_projects_data = [
            {
                "name": "项目管理系统开发",
                "description": "开发一个功能完整的项目管理系统，包括用户管理、项目管理、任务管理等功能",
                "status": "active",
                "priority": "high",
                "progress": 65,
                "budget": 500000.00,
                "actual_cost": 320000.00,
                "start_date": datetime.now() - timedelta(days=30),
                "end_date": datetime.now() + timedelta(days=60)
            },
            {
                "name": "移动端APP开发",
                "description": "开发配套的移动端应用，支持iOS和Android平台",
                "status": "planning",
                "priority": "medium",
                "progress": 15,
                "budget": 300000.00,
                "actual_cost": 45000.00,
                "start_date": datetime.now() + timedelta(days=15),
                "end_date": datetime.now() + timedelta(days=120)
            },
            {
                "name": "数据分析平台",
                "description": "构建数据分析和报表平台，为业务决策提供数据支持",
                "status": "completed",
                "priority": "medium",
                "progress": 100,
                "budget": 200000.00,
                "actual_cost": 185000.00,
                "start_date": datetime.now() - timedelta(days=90),
                "end_date": datetime.now() - timedelta(days=10)
            }
        ]
        
        created_projects = []
        for project_data in sample_projects_data:
            # 检查项目是否已存在
            result = await db.execute(
                select(Project).where(Project.name == project_data["name"])
            )
            existing_project = result.scalar_one_or_none()
            
            if existing_project:
                logger.info(f"项目 {project_data['name']} 已存在")
                created_projects.append(existing_project)
                continue
            
            project = Project(
                name=project_data["name"],
                description=project_data["description"],
                status=project_data["status"],
                priority=project_data["priority"],
                progress=project_data["progress"],
                budget=project_data["budget"],
                actual_cost=project_data["actual_cost"],
                start_date=project_data["start_date"],
                end_date=project_data["end_date"],
                manager_id=manager.id,
                organization_id=organization.id
            )
            
            # 添加项目成员
            for user in users[:3]:  # 添加前3个用户作为项目成员
                project.members.append(user)
            
            db.add(project)
            created_projects.append(project)
        
        await db.commit()
        
        # 刷新所有项目对象
        for project in created_projects:
            await db.refresh(project)
        
        logger.info(f"创建了 {len(created_projects)} 个示例项目")
        return created_projects
        
    except Exception as e:
        logger.error(f"创建示例项目失败: {e}")
        await db.rollback()
        raise

async def create_sample_tasks(db: AsyncSession, projects: list, users: list):
    """创建示例任务"""
    try:
        from datetime import datetime, timedelta
        
        # 为第一个项目创建任务
        if projects:
            project = projects[0]  # 项目管理系统开发
            
            sample_tasks_data = [
                {
                    "title": "需求分析",
                    "description": "收集和分析项目需求，编写需求文档",
                    "status": "completed",
                    "priority": "high",
                    "type": "analysis",
                    "estimated_hours": 40.0,
                    "due_date": datetime.now() - timedelta(days=20),
                    "completed_date": datetime.now() - timedelta(days=18),
                    "tags": ["需求", "分析", "文档"]
                },
                {
                    "title": "系统架构设计",
                    "description": "设计系统整体架构，包括数据库设计和API设计",
                    "status": "completed",
                    "priority": "high",
                    "type": "design",
                    "estimated_hours": 60.0,
                    "due_date": datetime.now() - timedelta(days=15),
                    "completed_date": datetime.now() - timedelta(days=12),
                    "tags": ["架构", "设计", "数据库"]
                },
                {
                    "title": "用户管理模块开发",
                    "description": "开发用户注册、登录、权限管理等功能",
                    "status": "completed",
                    "priority": "high",
                    "type": "development",
                    "estimated_hours": 80.0,
                    "due_date": datetime.now() - timedelta(days=5),
                    "completed_date": datetime.now() - timedelta(days=3),
                    "tags": ["开发", "用户管理", "认证"]
                },
                {
                    "title": "项目管理模块开发",
                    "description": "开发项目创建、编辑、成员管理等功能",
                    "status": "in_progress",
                    "priority": "high",
                    "type": "development",
                    "estimated_hours": 100.0,
                    "due_date": datetime.now() + timedelta(days=10),
                    "tags": ["开发", "项目管理"]
                },
                {
                    "title": "任务管理模块开发",
                    "description": "开发任务创建、分配、状态跟踪等功能",
                    "status": "todo",
                    "priority": "medium",
                    "type": "development",
                    "estimated_hours": 120.0,
                    "due_date": datetime.now() + timedelta(days=20),
                    "tags": ["开发", "任务管理"]
                },
                {
                    "title": "前端界面开发",
                    "description": "开发用户界面，包括响应式设计和用户体验优化",
                    "status": "in_progress",
                    "priority": "medium",
                    "type": "development",
                    "estimated_hours": 150.0,
                    "due_date": datetime.now() + timedelta(days=25),
                    "tags": ["前端", "UI", "响应式"]
                },
                {
                    "title": "系统测试",
                    "description": "进行功能测试、性能测试和安全测试",
                    "status": "todo",
                    "priority": "high",
                    "type": "testing",
                    "estimated_hours": 80.0,
                    "due_date": datetime.now() + timedelta(days=35),
                    "tags": ["测试", "质量保证"]
                },
                {
                    "title": "部署上线",
                    "description": "配置生产环境并部署系统",
                    "status": "todo",
                    "priority": "medium",
                    "type": "deployment",
                    "estimated_hours": 30.0,
                    "due_date": datetime.now() + timedelta(days=45),
                    "tags": ["部署", "运维"]
                }
            ]
            
            created_tasks = []
            for i, task_data in enumerate(sample_tasks_data):
                # 检查任务是否已存在
                result = await db.execute(
                    select(Task).where(
                        Task.title == task_data["title"],
                        Task.project_id == project.id
                    )
                )
                existing_task = result.scalar_one_or_none()
                
                if existing_task:
                    logger.info(f"任务 {task_data['title']} 已存在")
                    created_tasks.append(existing_task)
                    continue
                
                # 分配任务给不同的用户
                assignee = users[i % len(users)] if users else None
                reporter = users[0] if users else None  # 第一个用户作为报告人
                
                task = Task(
                    title=task_data["title"],
                    description=task_data["description"],
                    status=task_data["status"],
                    priority=task_data["priority"],
                    type=task_data["type"],
                    estimated_hours=task_data["estimated_hours"],
                    due_date=task_data["due_date"],
                    completed_date=task_data.get("completed_date"),
                    project_id=project.id,
                    assignee_id=assignee.id if assignee else None,
                    reporter_id=reporter.id if reporter else None,
                    tags=task_data["tags"]
                )
                
                db.add(task)
                created_tasks.append(task)
            
            await db.commit()
            
            # 刷新所有任务对象
            for task in created_tasks:
                await db.refresh(task)
            
            logger.info(f"为项目 {project.name} 创建了 {len(created_tasks)} 个示例任务")
            return created_tasks
        
        return []
        
    except Exception as e:
        logger.error(f"创建示例任务失败: {e}")
        await db.rollback()
        raise

async def init_database():
    """初始化数据库"""
    logger.info("开始初始化数据库...")
    
    try:
        # 创建数据库表
        await create_tables()
        
        # 如果启用了自动创建管理员用户
        if settings.auto_create_admin:
            async with async_session() as db:
                # 创建管理员用户
                admin_user = await create_admin_user(db)
                
                # 创建示例组织
                organization = await create_sample_organization(db, admin_user)
                
                # 创建示例用户
                sample_users = await create_sample_users(db, organization)
                
                # 获取经理用户
                manager_user = next(
                    (user for user in sample_users if user.role == "manager"),
                    admin_user
                )
                
                # 创建示例项目
                projects = await create_sample_projects(
                    db, manager_user, organization, sample_users
                )
                
                # 创建示例任务
                await create_sample_tasks(db, projects, sample_users)
        
        logger.info("数据库初始化完成")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 运行初始化
    asyncio.run(init_database())