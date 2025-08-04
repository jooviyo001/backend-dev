from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum
from utils.snowflake import (
    generate_user_id, 
    generate_organization_id, 
    generate_project_id, 
    generate_task_id,
    generate_task_attachment_id,
    generate_task_comment_id
)

# 枚举定义
class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    TODO = "todo"                # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    REVIEW = "review"            # 审核中
    DONE = "done"                # 已完成
    CANCELLED = "cancelled"      # 已取消

class TaskPriority(str, enum.Enum):
    """任务优先级枚举"""
    LOW = "low"        # 低优先级
    MEDIUM = "medium"  # 中等优先级
    HIGH = "high"      # 高优先级
    URGENT = "urgent"  # 紧急

class TaskType(str, enum.Enum):
    """任务类型枚举"""
    FEATURE = "feature"              # 功能开发
    BUG = "bug"                      # 缺陷修复
    IMPROVEMENT = "improvement"      # 改进优化
    DOCUMENTATION = "documentation"  # 文档编写
    TEST = "test"                    # 测试任务

class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    PLANNING = "planning"      # 规划中
    ACTIVE = "active"          # 进行中
    ON_HOLD = "on_hold"        # 暂停
    COMPLETED = "completed"    # 已完成
    ARCHIVED = "archived"      # 已归档

class ProjectPriority(str, enum.Enum):
    """项目优先级枚举"""
    LOW = "low"        # 低优先级
    MEDIUM = "medium"  # 中等优先级
    HIGH = "high"      # 高优先级
    URGENT = "urgent"  # 紧急

class UserRole(str, enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"      # 系统管理员
    MANAGER = "manager"  # 管理者
    MEMBER = "member"    # 普通成员
    USER = "user"        # 普通用户

# 成员角色枚举
class MemberRole(str, enum.Enum):
    """组织成员角色枚举"""
    ADMIN = "admin"      # 管理员
    MANAGER = "manager"  # 经理
    MEMBER = "member"    # 普通成员
    USER = "user"        # 普通用户

# 项目成员关联表
project_members = Table(
    'project_members',
    Base.metadata,
    Column('project_id', String(25), ForeignKey('projects.id'), primary_key=True, comment='项目ID'),
    Column('user_id', String(25), ForeignKey('users.id'), primary_key=True, comment='用户ID'),
    Column('role', String(50), default='member', comment='成员角色')
)

# 组织成员关联表
organization_members = Table(
    'organization_members',
    Base.metadata,
    Column('organization_id', String(25), ForeignKey('organizations.id'), primary_key=True, comment='组织ID'),
    Column('user_id', String(25), ForeignKey('users.id'), primary_key=True, comment='用户ID'),
    Column('position', String(100), comment='职位'),
    Column('role', Enum(MemberRole), default=MemberRole.MEMBER, comment='成员角色'),
    Column('joined_at', DateTime, default=func.now(), comment='加入时间')
)

# 组织类型枚举
class OrganizationType(str, enum.Enum):
    """组织类型枚举"""
    COMPANY = "company"        # 公司
    DEPARTMENT = "department"  # 部门
    TEAM = "team"              # 团队
    GROUP = "group"            # 小组

# 组织状态枚举
class OrganizationStatus(str, enum.Enum):
    """组织状态枚举"""
    ACTIVE = "active"      # 活跃
    INACTIVE = "inactive"  # 非活跃

# 用户模型
class User(Base):
    """用户表模型"""
    __tablename__ = "users"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_user_id, comment='用户ID，格式：U + 雪花算法ID')
    username = Column(String(50), unique=True, index=True, nullable=False, comment='用户名，唯一标识')
    email = Column(String(100), unique=True, index=True, nullable=False, comment='邮箱地址，唯一标识')
    password_hash = Column(String(255), nullable=False, comment='密码哈希值')
    name = Column(String(100), comment='用户真实姓名')
    avatar = Column(String(255), comment='头像URL地址')
    phone = Column(String(20), comment='手机号码')
    position = Column(String(100), comment='用户岗位/职位')
    department = Column(String(100), comment='用户所属部门')
    organization_id = Column(String(25), ForeignKey("organizations.id"), comment='用户所属组织ID')
    role = Column(Enum(UserRole), default=UserRole.MEMBER, comment='用户角色')
    is_active = Column(Boolean, default=True, comment='是否激活状态')
    is_verified = Column(Boolean, default=False, comment='是否已验证邮箱')
    last_login = Column(DateTime, comment='最后登录时间')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    
    # 关系
    organization = relationship("Organization", foreign_keys=[organization_id])
    created_projects = relationship("Project", back_populates="creator", foreign_keys="Project.creator_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    reported_tasks = relationship("Task", back_populates="reporter", foreign_keys="Task.reporter_id")
    projects = relationship("Project", secondary=project_members, back_populates="members")
    organizations = relationship("Organization", secondary=organization_members, back_populates="members")


# 组织模型
class Organization(Base):
    """组织表模型"""
    __tablename__ = "organizations"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_organization_id, comment='组织ID，格式：O + 雪花算法ID')
    name = Column(String(100), nullable=False, comment='组织名称')
    code = Column(String(20), unique=True, nullable=False, index=True, comment='组织编码，唯一标识')
    type = Column(Enum(OrganizationType), nullable=False, comment='组织类型')
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE, comment='组织状态')
    description = Column(Text, comment='组织描述')
    parent_id = Column(String(25), ForeignKey("organizations.id"), comment='父组织ID')
    level = Column(Integer, default=1, comment='组织层级')
    path = Column(String(500), comment='组织路径，如 "/1/2/3"')
    manager_id = Column(String(25), ForeignKey("users.id"), comment='组织管理员ID')
    sort = Column(Integer, default=0, comment='排序字段')
    address = Column(String(255), comment='组织地址')
    phone = Column(String(20), comment='联系电话')
    email = Column(String(100), comment='联系邮箱')
    website = Column(String(255), comment='官方网站')
    logo = Column(String(255), comment='组织Logo URL')
    is_active = Column(Boolean, default=True, comment='是否激活状态，保留兼容性')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    parent = relationship("Organization", remote_side=[id], back_populates="children")
    children = relationship("Organization", back_populates="parent")
    manager = relationship("User", foreign_keys=[manager_id])
    projects = relationship("Project", back_populates="organization")
    members = relationship("User", secondary=organization_members, back_populates="organizations")

# 项目模型
class Project(Base):
    """项目表模型"""
    __tablename__ = "projects"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_project_id, comment='项目ID，格式：P + 雪花算法ID')
    name = Column(String(100), nullable=False, comment='项目名称')
    description = Column(Text, comment='项目描述')
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING, comment='项目状态')
    priority = Column(Enum(ProjectPriority), default=ProjectPriority.MEDIUM, comment='项目优先级')
    start_date = Column(DateTime, comment='项目开始日期')
    end_date = Column(DateTime, comment='项目结束日期')
    creator_id = Column(String(25), ForeignKey("users.id"), comment='项目创建者ID')
    manager_id = Column(String(25), ForeignKey("users.id"), comment='项目管理者ID')
    organization_id = Column(String(25), ForeignKey("organizations.id"), comment='所属组织ID')
    is_archived = Column(Boolean, default=False, comment='是否已归档')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    creator = relationship("User", back_populates="created_projects", foreign_keys=[creator_id])
    manager = relationship("User", foreign_keys=[manager_id])
    organization = relationship("Organization", back_populates="projects")
    tasks = relationship("Task", back_populates="project")
    members = relationship("User", secondary=project_members, back_populates="projects")

# 任务模型
class Task(Base):
    """任务表模型"""
    __tablename__ = "tasks"
    # 任务ID，格式：T + 雪花算法ID
    id = Column(String(25), primary_key=True, index=True, default=generate_task_id, comment='任务ID，格式：T + 雪花算法ID')
    title = Column(String(200), nullable=False, comment='任务标题')
    description = Column(Text, comment='任务描述')
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, comment='任务状态')
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, comment='任务优先级')
    type = Column(Enum(TaskType), default=TaskType.FEATURE, comment='任务类型')
    project_id = Column(String(25), ForeignKey("projects.id"), comment='任务所属项目ID')
    assignee_id = Column(String(25), ForeignKey("users.id"), comment='任务负责人ID')
    reporter_id = Column(String(25), ForeignKey("users.id"), comment='任务报告人ID')
    due_date = Column(DateTime, comment='任务截止时间')
    estimated_hours = Column(Integer, comment='任务预估工时')
    actual_hours = Column(Integer, comment='任务实际工时')
    parent_task_id = Column(String(25), ForeignKey('tasks.id'), nullable=True, comment='父任务ID')
    tags = Column(String(500), comment='任务标签')  # JSON字符串存储标签
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关系
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_tasks")
    parent_task = relationship("Task", remote_side=[id], back_populates="sub_tasks")
    sub_tasks = relationship("Task", back_populates="parent_task")
    attachments = relationship("TaskAttachment", back_populates="task")
    comments = relationship("TaskComment", back_populates="task")

# 任务附件模型
class TaskAttachment(Base):
    """任务附件表模型"""
    __tablename__ = "task_attachments"
    
    id = Column(String(27), primary_key=True, index=True, default=generate_task_attachment_id, comment='任务附件ID，格式：TA + 雪花算法ID')
    task_id = Column(String(25), ForeignKey("tasks.id"), comment='任务附件所属任务ID')
    filename = Column(String(255), nullable=False, comment='附件文件名')
    original_filename = Column(String(255), nullable=False, comment='附件原始文件名')
    file_path = Column(String(500), nullable=False, comment='附件文件路径')
    file_size = Column(Integer, comment='附件文件大小')
    content_type = Column(String(100), comment='附件文件类型')
    uploaded_by = Column(String(25), ForeignKey("users.id"), comment='附件上传人ID')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    task = relationship("Task", back_populates="attachments")
    uploader = relationship("User")

# 任务评论模型
class TaskComment(Base):
    """任务评论表模型"""
    __tablename__ = "task_comments"
    
    id = Column(String(27), primary_key=True, index=True, default=generate_task_comment_id, comment='任务评论ID，格式：TC + 雪花算法ID')
    task_id = Column(String(25), ForeignKey("tasks.id"), comment='评论所属任务ID')
    user_id = Column(String(25), ForeignKey("users.id"), comment='评论用户ID')
    content = Column(Text, nullable=False, comment='评论内容')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    task = relationship("Task", back_populates="comments")
    user = relationship("User")