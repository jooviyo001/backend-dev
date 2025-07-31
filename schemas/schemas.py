from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Any
from datetime import datetime
from models.models import TaskStatus, TaskPriority, TaskType, ProjectStatus, ProjectPriority, UserRole, OrganizationType, OrganizationStatus, MemberRole

def default_timestamp() -> str:
    """返回格式化的当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 基础响应模式
class BaseResponse(BaseModel):
    code: str = "200"
    message: str = "操作成功"
    data: Optional[Any] = None
    # 使用字符串类型的格式化时间戳
    timestamp: str = Field(default_factory=default_timestamp)
    
# 分页响应模式
class PaginationResponse(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[Any]

# 用户相关模式
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    role: UserRole = UserRole.MEMBER

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = Field(None, description="用户是否已验证")
    avatar: Optional[str] = None
    password: Optional[str] = Field(None, description="新密码")
    status: Optional[str] = Field(None, description="用户状态")
    
    @validator('department', pre=True)
    def convert_department(cls, v):
        """处理department字段，如果是数组则取第一个元素"""
        if isinstance(v, list) and len(v) > 0:
            return v[0]
        return v
    
    @validator('status')
    def validate_status(cls, v):
        """验证status字段"""
        if v is not None and v not in ['active', 'inactive']:
            raise ValueError('状态必须是 active 或 inactive')
        return v

class UserProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    avatar: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[UserRole] = None

# 用户返回体定义
class UserResponse(UserBase):
    id: str  # 支持雪花ID格式，如 'U208228089547722752'
    is_active: bool
    is_verified: bool
    position: Optional[str] = None  # 职位
    department: Optional[str] = None  # 部门
    organization_id: Optional[str] = None  # 所属组织ID
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    avatar: Optional[str] = None
    
    class Config:
        from_attributes = True

# 认证相关模式
class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

class LoginRequest(BaseModel):
    username: str
    password: str

# 登录响应模式
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# 注册模式
class RegisterRequest(UserCreate):
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('密码不匹配')
        return v

# 注册响应模式
class RegisterResponse(BaseModel):
    data: Optional[UserResponse] = None



# 组织相关模式
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="组织名称")
    code: str = Field(..., min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$", description="组织编码")
    type: OrganizationType = Field(..., description="组织类型")
    description: Optional[str] = Field(None, max_length=200, description="组织描述")
    parent_id: Optional[str] = Field(None, description="父组织ID")  # 改为str
    manager_id: Optional[str] = Field(None, description="负责人ID")  # 改为str
    sort: int = Field(0, ge=0, le=999, description="排序权重")
    address: Optional[str] = Field(None, max_length=255, description="地址")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    website: Optional[str] = Field(None, max_length=255, description="网站")

# 组织创建模式
class OrganizationCreate(OrganizationBase):
    status: OrganizationStatus = Field(OrganizationStatus.ACTIVE, description="组织状态")

# 组织更新模式
class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="组织名称")
    code: Optional[str] = Field(None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$", description="组织编码")
    type: Optional[OrganizationType] = Field(None, description="组织类型")
    status: Optional[OrganizationStatus] = Field(None, description="组织状态")
    description: Optional[str] = Field(None, max_length=200, description="组织描述")
    manager_id: Optional[str] = Field(None, description="负责人ID")  # 改为str
    sort: Optional[int] = Field(None, ge=0, le=999, description="排序权重")
    address: Optional[str] = Field(None, max_length=255, description="地址")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    website: Optional[str] = Field(None, max_length=255, description="网站")

# 组织响应模式
class OrganizationResponse(BaseModel):
    id: str  # 改为str
    name: str
    code: str
    type: OrganizationType
    status: OrganizationStatus
    description: Optional[str] = None
    parent_id: Optional[str] = None  # 改为str
    parent_name: Optional[str] = None
    level: int
    path: Optional[str] = None
    manager_id: Optional[str] = None  # 改为str
    manager_name: Optional[str] = None
    member_count: int = 0
    child_count: int = 0
    sort: int
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo: Optional[str] = None
    is_active: bool  # 保留兼容性
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 组织树节点模式
class OrganizationTreeNode(BaseModel):
    id: str  # 改为str
    name: str
    code: str
    type: OrganizationType
    status: OrganizationStatus
    parent_id: Optional[str] = None  # 改为str
    level: int
    children: List["OrganizationTreeNode"] = [] # 递归引用自身

# 任务相关模式
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="任务标题")
    description: Optional[str] = Field(None, max_length=500, description="任务描述")
    project_id: str = Field(..., description="所属项目ID")  # 改为str
    assignee_id: Optional[str] = Field(None, description="执行人ID")  # 改为str
    reporter_id: Optional[str] = Field(None, description="报告人ID")  # 改为str
    status: TaskStatus = Field(TaskStatus.TODO, description="任务状态")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="任务优先级")
    type: TaskType = Field(TaskType.FEATURE, description="任务类型")
    due_date: Optional[datetime] = Field(None, description="截止日期")
    parent_task_id: Optional[str] = Field(None, description="父任务ID")  # 改为str
    
class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="任务标题")
    description: Optional[str] = Field(None, max_length=500, description="任务描述")
    project_id: Optional[str] = Field(None, description="所属项目ID")  # 改为str
    assignee_id: Optional[str] = Field(None, description="执行人ID")  # 改为str
    reporter_id: Optional[str] = Field(None, description="报告人ID")  # 改为str
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    priority: Optional[TaskPriority] = Field(None, description="任务优先级")
    type: Optional[TaskType] = Field(None, description="任务类型")
    due_date: Optional[datetime] = Field(None, description="截止日期")
    parent_task_id: Optional[str] = Field(None, description="父任务ID")  # 改为str

class TaskResponse(BaseModel):
    id: str  # 改为str
    title: str
    description: Optional[str] = None
    project_id: str  # 改为str
    project_name: Optional[str] = None
    assignee_id: Optional[str] = None  # 改为str
    assignee_name: Optional[str] = None
    reporter_id: Optional[str] = None  # 改为str
    reporter_name: Optional[str] = None
    status: TaskStatus
    priority: TaskPriority
    type: TaskType
    due_date: Optional[datetime] = None
    parent_task_id: Optional[str] = None  # 改为str
    parent_task_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 组织成员模式
class OrganizationMemberBase(BaseModel):
    user_id: str = Field(..., description="用户ID")  # 改为str
    position: Optional[str] = Field(None, max_length=100, description="职位")
    role: MemberRole = Field(MemberRole.MEMBER, description="角色")

class OrganizationMemberCreate(OrganizationMemberBase):
    pass

class OrganizationMemberUpdate(BaseModel):
    position: Optional[str] = Field(None, max_length=100, description="职位")
    role: Optional[MemberRole] = Field(None, description="角色")

class OrganizationMemberResponse(BaseModel):
    id: str  # 改为str
    organization_id: str  # 改为str
    user_id: str  # 改为str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_avatar: Optional[str] = None
    position: Optional[str] = None
    role: MemberRole
    joined_at: datetime
    
    class Config:
        from_attributes = True

# 组织统计模式
class OrganizationStatistics(BaseModel):
    total: int = 0
    by_type: dict = {}
    by_status: dict = {}
    total_members: int = 0
    average_members_per_org: float = 0.0
    max_level: int = 0

# 组织移动模式
class OrganizationMove(BaseModel):
    parent_id: Optional[str] = Field(None, description="新父组织ID")  # 改为str

# 批量操作模式
class OrganizationBatchDelete(BaseModel):
    ids: List[str] = Field(..., min_length=1, description="组织ID数组")  # 改为str

# 项目相关模式
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: ProjectPriority = ProjectPriority.MEDIUM
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[str] = None  # 改为str

# 项目创建模式
class ProjectCreate(ProjectBase):
    manager_id: Optional[str] = Field(None, description="项目经理ID")  # 改为str
    member_ids: Optional[List[str]] = Field(default_factory=list, description="项目成员ID列表")  # 改为str

# 项目更新模式
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    manager_id: Optional[str] = None  # 改为str
    organization_id: Optional[str] = None  # 改为str

# 项目响应模式
class ProjectResponse(BaseModel):
    id: str  # 改为str
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[str] = None  # 改为str
    creator_id: str  # 改为str
    manager_id: Optional[str] = None  # 改为str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    manager: Optional[UserResponse] = None
    organization: Optional[OrganizationResponse] = None
    
    class Config:
        from_attributes = True

# 任务相关模式
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    type: TaskType = TaskType.FEATURE
    project_id: str  # 改为str
    assignee_id: Optional[str] = None  # 改为str
    due_date: Optional[datetime] = None
    estimated_hours: Optional[int] = None
    tags: Optional[List[str]] = None

# 任务创建模式
class TaskCreate(TaskBase):
    pass

# 任务更新模式
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    type: Optional[TaskType] = None
    project_id: Optional[str] = None  # 改为str
    assignee_id: Optional[str] = None  # 改为str
    due_date: Optional[datetime] = None
    estimated_hours: Optional[int] = None
    actual_hours: Optional[int] = None
    tags: Optional[List[str]] = None

class TaskResponse(TaskBase):
    id: str  # 改为str
    reporter_id: Optional[str] = None  # 改为str
    actual_hours: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectResponse] = None
    assignee: Optional[UserResponse] = None
    reporter: Optional[UserResponse] = None
    
    class Config:
        from_attributes = True

# 任务统计模式
class TaskStatistics(BaseModel):
    total: int
    todo: int
    in_progress: int
    review: int
    done: int
    cancelled: int
    overdue: int

# 批量操作模式
class BatchDeleteRequest(BaseModel):
    ids: List[str] = Field(..., min_length=1, description="任务ID数组")  # 改为str

class BatchAssignRequest(BaseModel):
    task_ids: List[str] = Field(..., min_length=1, description="任务ID数组")  # 改为str
    assignee_id: str = Field(..., description="分配者ID")  # 改为str

# 附件相关模式
class AttachmentResponse(BaseModel):
    id: str  # 改为str
    task_id: str  # 改为str
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    uploaded_by: str  # 改为str
    created_at: datetime
    
    class Config:
        from_attributes = True

# 评论相关模式
class CommentBase(BaseModel):
    content: str

# 评论创建模式
class CommentCreate(CommentBase):
    task_id: str  # 改为str
    user_id: str  # 改为str

# 评论响应模式
class CommentResponse(CommentBase):
    id: str  # 改为str
    task_id: str  # 改为str
    user_id: str  # 改为str
    created_at: datetime
    updated_at: datetime
    user: Optional[UserResponse] = None
    
    class Config:
        from_attributes = True