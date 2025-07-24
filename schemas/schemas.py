from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Any
from datetime import datetime
from models.models import TaskStatus, TaskPriority, TaskType, ProjectStatus, ProjectPriority, UserRole, OrganizationType, OrganizationStatus, MemberRole

# 基础响应模式
class BaseResponse(BaseModel):
    code: str = "200"
    message: str = "操作成功"
    data: Optional[Any] = None
    # 使用datetime类型，并通过Field设置默认值工厂函数
    timestamp: datetime = Field(default_factory=datetime.now)
    
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
    role: UserRole = UserRole.MEMBER

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    avatar: Optional[str] = None
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 认证相关模式
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
class RegisterResponse(BaseResponse):
    data: UserResponse

# 用户状态切换模式
class UserStatusToggle(BaseModel):
    status: str = Field(..., description="用户状态: active 或 inactive")
    
    @validator('status')
    def validate_status(cls, v):
        if v not in ['active', 'inactive']:
            raise ValueError('状态必须是 active 或 inactive')
        return v

# 组织相关模式
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="组织名称")
    code: str = Field(..., min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$", description="组织编码")
    type: OrganizationType = Field(..., description="组织类型")
    description: Optional[str] = Field(None, max_length=200, description="组织描述")
    parent_id: Optional[int] = Field(None, description="父组织ID")
    manager_id: Optional[int] = Field(None, description="负责人ID")
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
    manager_id: Optional[int] = Field(None, description="负责人ID")
    sort: Optional[int] = Field(None, ge=0, le=999, description="排序权重")
    address: Optional[str] = Field(None, max_length=255, description="地址")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    website: Optional[str] = Field(None, max_length=255, description="网站")

# 组织响应模式
class OrganizationResponse(BaseModel):
    id: int
    name: str
    code: str
    type: OrganizationType
    status: OrganizationStatus
    description: Optional[str] = None
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None
    level: int
    path: Optional[str] = None
    manager_id: Optional[int] = None
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
    id: int
    name: str
    code: str
    type: OrganizationType
    status: OrganizationStatus
    parent_id: Optional[int] = None
    level: int
    member_count: int = 0
    children: List['OrganizationTreeNode'] = []
    
    class Config:
        from_attributes = True

# 组织成员模式
class OrganizationMemberBase(BaseModel):
    user_id: int = Field(..., description="用户ID")
    position: Optional[str] = Field(None, max_length=100, description="职位")
    role: MemberRole = Field(MemberRole.MEMBER, description="角色")

class OrganizationMemberCreate(OrganizationMemberBase):
    pass

class OrganizationMemberUpdate(BaseModel):
    position: Optional[str] = Field(None, max_length=100, description="职位")
    role: Optional[MemberRole] = Field(None, description="角色")

class OrganizationMemberResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int
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
    parent_id: Optional[int] = Field(None, description="新父组织ID")

# 批量操作模式
class OrganizationBatchDelete(BaseModel):
    ids: List[int] = Field(..., min_items=1, description="组织ID数组")

# 项目相关模式
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: ProjectPriority = ProjectPriority.MEDIUM
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[int] = None

# 项目创建模式
class ProjectCreate(ProjectBase):
    manager_id: Optional[int] = Field(None, description="项目经理ID")
    member_ids: Optional[List[int]] = Field(default_factory=list, description="项目成员ID列表")

# 项目更新模式
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    manager_id: Optional[int] = None
    organization_id: Optional[int] = None

# 项目响应模式
class ProjectResponse(ProjectBase):
    id: int
    creator_id: int
    manager_id: Optional[int] = None
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
    project_id: int
    assignee_id: Optional[int] = None
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
    project_id: Optional[int] = None
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[int] = None
    actual_hours: Optional[int] = None
    tags: Optional[List[str]] = None

class TaskResponse(TaskBase):
    id: int
    reporter_id: int
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
    ids: List[int]

class BatchAssignRequest(BaseModel):
    task_ids: List[int]
    assignee_id: int

# 附件相关模式
class AttachmentResponse(BaseModel):
    id: int
    task_id: int
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    uploaded_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# 评论相关模式
class CommentBase(BaseModel):
    content: str

# 评论创建模式
class CommentCreate(CommentBase):
    task_id: int
    user_id: int

# 评论响应模式
class CommentResponse(CommentBase):
    id: int
    task_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    user: Optional[UserResponse] = None
    
    class Config:
        from_attributes = True