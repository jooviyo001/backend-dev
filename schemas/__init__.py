# 基础模式
from .base import BaseResponse, PaginationResponse, default_timestamp

# 用户相关模式
from .user import (
    UserBase, UserCreate, UserUpdate, UserProfileUpdateRequest, UserResponse,
    ChangePasswordRequest, LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    NotificationSettings, NotificationSettingsResponse, NotificationSettingsUpdate,
    LanguageSettings, LanguageSettingsResponse, LanguageSettingsUpdate, UserStatusUpdate
)

# 组织相关模式
from .organization import (
    OrganizationBase, OrganizationCreate, OrganizationUpdate, OrganizationStatusUpdate,
    OrganizationBatchUpdate, OrganizationResponse, OrganizationTreeNode,
    OrganizationMemberBase, OrganizationMemberCreate, OrganizationMemberUpdate,
    OrganizationMemberResponse, OrganizationStatistics, OrganizationMove,
    OrganizationBatchDelete
)

# 项目相关模式
from .project import ProjectBase, ProjectCreate, ProjectUpdate, ProjectResponse

# 任务相关模式
from .task import (
    TaskBase, TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    TaskStatistics, BatchDeleteRequest, BatchAssignRequest, TaskBatchStatusUpdate,
    TaskBatchAssigneeUpdate, TaskStatusUpdate, TaskStatusUpdateResponse,
    AttachmentResponse, CommentBase, CommentCreate, CommentResponse
)

# 缺陷相关模式
from .defect import DefectBase, DefectResponse, DefectCreate, DefectUpdate

# 职位相关模式
from .positions import (
    PositionBase, PositionCreate, PositionUpdate, PositionResponse, PositionListResponse
)

# 仪表盘相关模式
from .dashboard import (
    DashboardStats, RecentTask, ProjectProgress, TaskStatusDistribution,
    RecentActivity, UserWorkload, ProjectTrend, TaskTrend
)

__all__ = [
    # 基础模式
    "BaseResponse", "PaginationResponse", "default_timestamp",
    
    # 用户相关模式
    "UserBase", "UserCreate", "UserUpdate", "UserProfileUpdateRequest", "UserResponse",
    "ChangePasswordRequest", "LoginRequest", "LoginResponse", "RegisterRequest", "RegisterResponse",
    "NotificationSettings", "NotificationSettingsResponse", "NotificationSettingsUpdate",
    "LanguageSettings", "LanguageSettingsResponse", "LanguageSettingsUpdate", "UserStatusUpdate",
    
    # 组织相关模式
    "OrganizationBase", "OrganizationCreate", "OrganizationUpdate", "OrganizationStatusUpdate",
    "OrganizationBatchUpdate", "OrganizationResponse", "OrganizationTreeNode",
    "OrganizationMemberBase", "OrganizationMemberCreate", "OrganizationMemberUpdate",
    "OrganizationMemberResponse", "OrganizationStatistics", "OrganizationMove",
    "OrganizationBatchDelete",
    
    # 项目相关模式
    "ProjectBase", "ProjectCreate", "ProjectUpdate", "ProjectResponse",
    
    # 任务相关模式
    "TaskBase", "TaskCreate", "TaskUpdate", "TaskResponse", "TaskListResponse",
    "TaskStatistics", "BatchDeleteRequest", "BatchAssignRequest", "TaskBatchStatusUpdate",
    "TaskBatchAssigneeUpdate", "TaskStatusUpdate", "TaskStatusUpdateResponse",
    "AttachmentResponse", "CommentBase", "CommentCreate", "CommentResponse",
    
    # 缺陷相关模式
    "DefectBase", "DefectResponse", "DefectCreate", "DefectUpdate",
    
    # 职位相关模式
    "PositionBase", "PositionCreate", "PositionUpdate", "PositionResponse", "PositionListResponse",
    
    # 仪表盘相关模式
    "DashboardStats", "RecentTask", "ProjectProgress", "TaskStatusDistribution",
    "RecentActivity", "UserWorkload", "ProjectTrend", "TaskTrend",
]

# 解决前向引用问题，重建模型
ProjectResponse.model_rebuild()
TaskResponse.model_rebuild()
UserResponse.model_rebuild()