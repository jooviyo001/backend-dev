from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Any
from datetime import datetime
from models.models import TaskStatus, TaskPriority, TaskType, ProjectStatus, UserRole

# 基础响应模式
class BaseResponse(BaseModel):
    code: str = "200"
    message: str = "操作成功"
    data: Optional[Any] = None
    # 这里的时间需要使用格式“yyyy-MM-dd HH:mm:ss”
    timestamp: datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
    role: UserRole = UserRole.DEVELOPER

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

# 组织相关模式
class OrganizationBase(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None

# 组织创建模式
class OrganizationCreate(OrganizationBase):
    pass

# 组织更新模式
class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None

# 组织更新模式
class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None

# 组织响应模式
class OrganizationResponse(OrganizationBase):
    id: int
    logo: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 项目相关模式
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[int] = None

# 项目创建模式
class ProjectCreate(ProjectBase):
    pass

# 项目更新模式
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[int] = None

# 项目更新模式
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[int] = None

# 项目响应模式
class ProjectResponse(ProjectBase):
    id: int
    creator_id: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
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