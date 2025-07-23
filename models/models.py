from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum, Table, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from utils.snowflake_column import snowflake_id_column, SnowflakeId
import enum
from datetime import datetime

# 枚举定义
class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"

class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskType(str, enum.Enum):
    FEATURE = "feature"
    BUG = "bug"
    IMPROVEMENT = "improvement"
    DOCUMENTATION = "documentation"
    TEST = "test"

class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    USER = "user"

# 关联表
project_members = Table(
    'project_members',
    Base.metadata,
    Column('project_id', BigInteger, ForeignKey('projects.id'), primary_key=True),
    Column('user_id', BigInteger, ForeignKey('users.id'), primary_key=True),
    Column('role', String(50), default='member')
)

# 成员角色枚举
class MemberRole(str, enum.Enum):
    ADMIN = "admin"      # 管理员
    MANAGER = "manager"  # 经理
    MEMBER = "member"    # 普通成员
    VIEWER = "viewer"    # 查看者

organization_members = Table(
    'organization_members',
    Base.metadata,
    Column('organization_id', BigInteger, ForeignKey('organizations.id'), primary_key=True),
    Column('user_id', BigInteger, ForeignKey('users.id'), primary_key=True),
    Column('position', String(100)),  # 职位
    Column('role', Enum(MemberRole), default=MemberRole.MEMBER),
    Column('joined_at', DateTime, default=func.now())
)

# 用户模型
class User(Base):
    __tablename__ = "users"
    
    id = snowflake_id_column()
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    avatar = Column(String(255))
    phone = Column(String(20))
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    created_projects = relationship("Project", back_populates="creator", foreign_keys="Project.creator_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    reported_tasks = relationship("Task", back_populates="reporter", foreign_keys="Task.reporter_id")
    projects = relationship("Project", secondary=project_members, back_populates="members")
    organizations = relationship("Organization", secondary=organization_members, back_populates="members")

# 组织类型枚举
class OrganizationType(str, enum.Enum):
    COMPANY = "company"
    DEPARTMENT = "department"
    TEAM = "team"
    GROUP = "group"

# 组织状态枚举
class OrganizationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"



# 组织模型
class Organization(Base):
    __tablename__ = "organizations"
    
    id = snowflake_id_column()
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)
    type = Column(Enum(OrganizationType), nullable=False)
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE)
    description = Column(Text)
    parent_id = Column(BigInteger, ForeignKey("organizations.id"))
    level = Column(Integer, default=1)
    path = Column(String(500))  # 存储组织路径，如 "/1/2/3"
    manager_id = Column(BigInteger, ForeignKey("users.id"))
    sort = Column(Integer, default=0)
    address = Column(String(255))
    phone = Column(String(20))
    email = Column(String(100))
    website = Column(String(255))
    logo = Column(String(255))
    is_active = Column(Boolean, default=True)  # 保留兼容性
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    parent = relationship("Organization", remote_side=[id], back_populates="children")
    children = relationship("Organization", back_populates="parent")
    manager = relationship("User", foreign_keys=[manager_id])
    projects = relationship("Project", back_populates="organization")
    members = relationship("User", secondary=organization_members, back_populates="organizations")

# 项目模型
class Project(Base):
    __tablename__ = "projects"
    
    id = snowflake_id_column()
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    creator_id = Column(BigInteger, ForeignKey("users.id"))
    organization_id = Column(BigInteger, ForeignKey("organizations.id"))
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    creator = relationship("User", back_populates="created_projects", foreign_keys=[creator_id])
    organization = relationship("Organization", back_populates="projects")
    tasks = relationship("Task", back_populates="project")
    members = relationship("User", secondary=project_members, back_populates="projects")

# 任务模型
class Task(Base):
    __tablename__ = "tasks"
    
    id = snowflake_id_column()
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    type = Column(Enum(TaskType), default=TaskType.FEATURE)
    project_id = Column(BigInteger, ForeignKey("projects.id"))
    assignee_id = Column(BigInteger, ForeignKey("users.id"))
    reporter_id = Column(BigInteger, ForeignKey("users.id"))
    due_date = Column(DateTime)
    estimated_hours = Column(Integer)
    actual_hours = Column(Integer)
    tags = Column(String(500))  # JSON字符串存储标签
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    reporter = relationship("User", back_populates="reported_tasks", foreign_keys=[reporter_id])
    attachments = relationship("TaskAttachment", back_populates="task")
    comments = relationship("TaskComment", back_populates="task")

# 任务附件模型
class TaskAttachment(Base):
    __tablename__ = "task_attachments"
    
    id = snowflake_id_column()
    task_id = Column(BigInteger, ForeignKey("tasks.id"))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    content_type = Column(String(100))
    uploaded_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    
    # 关系
    task = relationship("Task", back_populates="attachments")
    uploader = relationship("User")

# 任务评论模型
class TaskComment(Base):
    __tablename__ = "task_comments"
    
    id = snowflake_id_column()
    task_id = Column(BigInteger, ForeignKey("tasks.id"))
    user_id = Column(BigInteger, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    task = relationship("Task", back_populates="comments")
    user = relationship("User")