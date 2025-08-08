from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from models import ProjectStatus, ProjectPriority

if TYPE_CHECKING:
    from .user import UserResponse
    from .task import TaskListResponse

# 项目相关模式
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: ProjectPriority = ProjectPriority.MEDIUM
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0, description="项目预算，数值类型，≥0")
    tags: Optional[List[str]] = Field(default_factory=list, description="项目标签，字符串数组")

# 项目创建模式
class ProjectCreate(ProjectBase):
    manager_id: Optional[str] = Field(None, description="项目经理ID")
    member_ids: Optional[List[str]] = Field(default_factory=list, description="项目成员ID列表")

    @field_validator('manager_id', mode='before')
    @classmethod
    def convert_nan_to_none(cls, v):
        if isinstance(v, str) and v.lower() == 'nan':
            return None
        return v

# 项目更新模式
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None  # 项目优先级
    start_date: Optional[datetime] = None  # 项目开始日期
    end_date: Optional[datetime] = None  # 项目结束日期
    manager_id: Optional[str] = None  # 项目负责人ID
    member_ids: Optional[List[str]] = Field(default_factory=list, description="项目成员ID列表")
    organization_id: Optional[str] = None  # 组织ID
    is_archived: Optional[bool] = False  # 是否已归档，布尔类型，默认false
    budget: Optional[float] = Field(None, ge=0, description="项目预算，数值类型，≥0")
    tags: Optional[List[str]] = Field(None, description="项目标签，字符串数组")

    @field_validator('manager_id', mode='before')
    @classmethod
    def convert_nan_to_none(cls, v):
        if isinstance(v, str) and v.lower() == 'nan':
            return None
        return v

# 项目响应模式
class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    budget: Optional[float] = None  # 项目预算，数值类型，≥0
    tags: Optional[List[str]] = None  # 项目标签，字符串数组
    is_archived: bool = False  # 是否已归档，布尔类型，默认false
    created_at: datetime
    updated_at: datetime
    creator: Optional["UserResponse"] = None
    members: Optional[List["UserResponse"]] = None
    # 添加tasks字段，但使用简化版的任务列表响应模型
    tasks: Optional[List["TaskListResponse"]] = None
    
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
        from_attributes = True