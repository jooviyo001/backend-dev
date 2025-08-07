from pydantic import BaseModel
from typing import Optional


# 仪表盘统计数据
class DashboardStats(BaseModel):
    totalProjects: int
    activeProjects: int
    totalTasks: int
    completedTasks: int
    overdueTasks: int
    totalUsers: int
    activeUsers: int
    projectProgress: float
    taskCompletionRate: float
    recentActivity: int
    completedProjects: int
    myTasks: int
    teamMembers: int


# 最近任务
class RecentTask(BaseModel):
    id: str
    title: str
    status: str
    priority: str
    dueDate: Optional[str]
    projectName: str
    assigneeName: str


# 项目进度
class ProjectProgress(BaseModel):
    projectId: str
    projectName: str
    progress: float
    totalTasks: int
    completedTasks: int
    status: str


# 任务状态分布
class TaskStatusDistribution(BaseModel):
    status: str
    count: int
    percentage: float


# 最近活动
class RecentActivity(BaseModel):
    id: str
    type: str  # project|task|user
    action: str  # created|updated|deleted
    description: str
    userId: str
    userName: str
    targetId: str
    targetName: str
    createdAt: str


# 用户工作负载
class UserWorkload(BaseModel):
    userId: str
    userName: str
    totalTasks: int
    completedTasks: int
    inProgressTasks: int
    overdueTasks: int
    workloadPercentage: float


# 项目趋势
class ProjectTrend(BaseModel):
    period: str
    totalProjects: int
    completedProjects: int
    activeProjects: int
    date: str


# 任务趋势
class TaskTrend(BaseModel):
    period: str
    totalTasks: int
    completedTasks: int
    activeTasks: int
    date: str