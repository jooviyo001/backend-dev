from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from models.enums import TaskStatus, TaskPriority, TaskType

if TYPE_CHECKING:
    from .user import UserResponse

# 任务相关模式
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    type: TaskType = TaskType.FEATURE
    project_id: str
    assignee_id: Optional[str] = None
    start_date: Optional[datetime] = None  # 任务开始日期
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    tags: Optional[List[str]] = None

# 任务创建模式
class TaskCreate(TaskBase):
    # 对于ID的处理应该是以原来的字符串为准，不更改提取
    @field_validator('project_id', 'assignee_id', mode='before')
    @classmethod
    def normalize_id_format(cls, v):
        """标准化ID格式，保留带前缀的ID格式"""
        if not v:
            return v
        if isinstance(v, str):
            # 如果已经是带前缀的格式，直接返回
            if (v.startswith('P') and v[1:].isdigit()) or \
               (v.startswith('U') and v[1:].isdigit()) or \
               (v.startswith('T') and v[1:].isdigit()) or \
               (v.startswith('O') and v[1:].isdigit()):
                return v
            # 如果是纯数字，需要根据字段名添加前缀
            if v.isdigit():
                # 这里我们保持原样，让后端处理
                return v
        return v
    
    @field_validator('start_date', 'due_date', mode='before')
    @classmethod
    def parse_datetime_string(cls, v):
        """解析日期时间字符串，支持多种格式"""
        if not v:
            return v
        if isinstance(v, str):
            try:
                # 尝试解析 "YYYY-MM-DD HH:MM:SS" 格式
                if len(v) == 19 and ' ' in v:
                    return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                # 尝试解析 "YYYY-MM-DD" 格式
                elif len(v) == 10:
                    return datetime.strptime(v, "%Y-%m-%d")
                # 尝试解析 ISO 格式
                else:
                    return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                # 如果解析失败，返回原值让 Pydantic 处理
                return v
        return v

# 任务更新模式
class TaskUpdate(BaseModel):
    title: Optional[str] = None  # 任务标题
    description: Optional[str] = None  # 任务描述
    status: Optional[TaskStatus] = None  # 任务状态
    priority: Optional[TaskPriority] = None  # 任务优先级
    type: Optional[TaskType] = None  # 任务类型
    project_id: Optional[str] = None  # 项目ID
    assignee_id: Optional[str] = None  # 负责人ID
    reporter_id: Optional[str] = None  # 报告人ID
    start_date: Optional[datetime] = None  # 开始日期
    due_date: Optional[datetime] = None  # 截止日期
    estimated_hours: Optional[float] = None  # 预估工时
    actual_hours: Optional[float] = None  # 实际工时
    tags: Optional[List[str]] = None  # 标签

# 更新任务响应模式
class TaskResponse(TaskBase):
    id: str
    reporter_id: Optional[str] = None  # 报告人ID
    reporter_name: Optional[str] = None  # 报告人姓名
    assignee_name: Optional[str] = None  # 负责人姓名
    project_name: Optional[str] = None  # 项目名称
    actual_hours: Optional[float] = None  # 实际工时
    start_date: Optional[datetime] = None  # 任务开始日期
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """自定义验证方法，从关联对象中填充名称字段，只返回ID和名称"""
        # 先调用父类的验证
        instance = super().model_validate(obj, **kwargs)
        
        # 从关联的reporter对象中获取名称
        if hasattr(obj, 'reporter') and obj.reporter:
            instance.reporter_name = obj.reporter.name
        
        # 从关联的assignee对象中获取名称
        if hasattr(obj, 'assignee') and obj.assignee:
            instance.assignee_name = obj.assignee.name
        
        # 从关联的project对象中获取项目名称
        if hasattr(obj, 'project') and obj.project:
            instance.project_name = obj.project.name
            
        # 不包含完整的用户对象，只保留ID和名称字段
        return instance
    
    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v):
        """解析tags字段，支持JSON字符串转换为列表"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                return json.loads(v) if v else []
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []
    
    class Config:
        from_attributes = True  # 允许从 ORM 模型创建

# 任务列表响应模式（简化版，用于列表展示）
class TaskListResponse(BaseModel):
    id: str  # 任务ID
    title: str  # 任务标题
    project_name: Optional[str] = None  # 所属项目
    assignee_name: Optional[str] = None  # 负责人
    priority: TaskPriority  # 优先级
    status: TaskStatus  # 状态
    due_date: Optional[datetime] = None  # 截止日期
    created_at: datetime  # 创建日期
    updated_at: datetime  # 更新时间
    
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
    ids: List[str] = Field(..., min_length=1, description="任务ID数组")

class BatchAssignRequest(BaseModel):
    task_ids: List[str] = Field(..., min_length=1, description="任务ID数组")
    assignee_id: str = Field(..., description="分配者ID")

# 任务批量状态更新模式
class TaskBatchStatusUpdate(BaseModel):
    task_ids: List[str] = Field(..., min_length=1, description="任务ID数组")
    status: TaskStatus = Field(..., description="目标状态")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """验证状态只能是待办、进行中、完成"""
        allowed_statuses = [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE]
        if v not in allowed_statuses:
            raise ValueError(f"状态只能是: {', '.join([s.value for s in allowed_statuses])}")
        return v

class TaskBatchAssigneeUpdate(BaseModel):
    """批量分配任务的请求模式"""
    task_ids: List[str] = Field(..., description="任务ID列表")
    assignee_id: str = Field(..., description="分配给的用户ID")

# 附件相关模式
class AttachmentResponse(BaseModel):
    id: str
    task_id: str
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    uploaded_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# 评论相关模式
class CommentBase(BaseModel):
    content: str

# 评论创建模式
class CommentCreate(CommentBase):
    task_id: str
    user_id: str

# 评论响应模式
class CommentResponse(CommentBase):
    id: str
    task_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    user: Optional["UserResponse"] = None
    
    class Config:
        from_attributes = True