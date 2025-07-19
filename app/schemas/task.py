from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskType(str, Enum):
    TASK = "task"
    BUG = "bug"
    FEATURE = "feature"
    IMPROVEMENT = "improvement"

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    type: TaskType = TaskType.TASK
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    estimated_hours: Optional[int] = None
    tags: Optional[List[str]] = None
    parent_task_id: Optional[str] = None

class TaskCreate(TaskBase):
    project_id: str
    assignee_id: Optional[str] = None
    reporter_id: str
    
    @validator('due_date')
    def validate_due_date(cls, v, values):
        if v and values.get('start_date') and v <= values['start_date']:
            raise ValueError('截止日期必须晚于开始日期')
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    type: Optional[TaskType] = None
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    estimated_hours: Optional[int] = None
    tags: Optional[List[str]] = None
    assignee_id: Optional[str] = None
    parent_task_id: Optional[str] = None

class TaskStatusUpdate(BaseModel):
    status: TaskStatus

class TaskAssign(BaseModel):
    assignee_id: str

class TaskResponse(TaskBase):
    id: str
    project_id: str
    assignee_id: Optional[str] = None
    reporter_id: str
    actual_hours: int
    completed_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TaskDetailResponse(TaskResponse):
    project: Optional[dict] = None
    assignee: Optional[dict] = None
    reporter: Optional[dict] = None
    parent_task: Optional[dict] = None
    subtasks: Optional[List[dict]] = None

class TaskStatistics(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_type: dict[str, int]
    overdue_tasks: int
    completed_this_week: int
    assigned_to_me: int
    reported_by_me: int

class TaskSearchParams(BaseModel):
    keyword: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    type: Optional[TaskType] = None
    project_id: Optional[str] = None
    assignee_id: Optional[str] = None
    reporter_id: Optional[str] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None
    parent_task_id: Optional[str] = None

class BatchTaskStatusUpdate(BaseModel):
    task_ids: List[str]
    status: TaskStatus

class BatchTaskAssign(BaseModel):
    task_ids: List[str]
    assignee_id: str

class BatchTaskPriorityUpdate(BaseModel):
    task_ids: List[str]
    priority: TaskPriority