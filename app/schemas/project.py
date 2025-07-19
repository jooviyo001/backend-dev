from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INACTIVE = "inactive"

class ProjectPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: ProjectPriority = ProjectPriority.MEDIUM
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = None
    estimated_hours: Optional[int] = None
    tags: Optional[List[str]] = None
    organization_id: Optional[str] = None

class ProjectCreate(ProjectBase):
    manager_id: str
    member_ids: Optional[List[str]] = None
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and values.get('start_date') and v <= values['start_date']:
            raise ValueError('结束日期必须晚于开始日期')
        return v

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = None
    estimated_hours: Optional[int] = None
    tags: Optional[List[str]] = None
    manager_id: Optional[str] = None
    organization_id: Optional[str] = None

class ProjectProgressUpdate(BaseModel):
    progress: float
    
    @validator('progress')
    def validate_progress(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('进度必须在0-100之间')
        return v

class ProjectMemberAdd(BaseModel):
    user_ids: List[str]
    role: str = "developer"

class ProjectMemberRemove(BaseModel):
    user_ids: List[str]

class ProjectResponse(ProjectBase):
    id: str
    progress: float
    actual_cost: float
    actual_hours: int
    manager_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProjectDetailResponse(ProjectResponse):
    manager: Optional[dict] = None
    members: Optional[List[dict]] = None
    organization: Optional[dict] = None
    task_count: Optional[int] = None
    completed_task_count: Optional[int] = None

class ProjectStatistics(BaseModel):
    total: int
    planning: int
    active: int
    completed: int
    cancelled: int
    inactive: int
    by_priority: dict[str, int]
    total_budget: float
    total_actual_cost: float
    average_progress: float
    overdue_projects: int

class ProjectSearchParams(BaseModel):
    keyword: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    manager_id: Optional[str] = None
    organization_id: Optional[str] = None
    start_date_from: Optional[datetime] = None
    start_date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None

class BatchProjectStatusUpdate(BaseModel):
    project_ids: List[str]
    status: ProjectStatus

class BatchProjectMemberAssign(BaseModel):
    project_ids: List[str]
    user_ids: List[str]
    role: str = "developer"