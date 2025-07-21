from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from utils.auth import get_current_user

router = APIRouter()

# 响应模型
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

class RecentTask(BaseModel):
    id: str
    title: str
    status: str
    priority: str
    dueDate: Optional[str]
    projectName: str
    assigneeName: str

class ProjectProgress(BaseModel):
    projectId: str
    projectName: str
    progress: float
    totalTasks: int
    completedTasks: int
    status: str

class TaskStatusDistribution(BaseModel):
    status: str
    count: int
    percentage: float

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

class UserWorkload(BaseModel):
    userId: str
    userName: str
    totalTasks: int
    completedTasks: int
    inProgressTasks: int
    overdueTasks: int
    workloadPercentage: float

class ProjectTrend(BaseModel):
    period: str
    totalProjects: int
    completedProjects: int
    activeProjects: int
    date: str

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    dateFrom: Optional[str] = Query(None, description="日期范围开始"),
    dateTo: Optional[str] = Query(None, description="日期范围结束"),
    departmentId: Optional[str] = Query(None, description="部门ID"),
    current_user=Depends(get_current_user)
):
    """获取仪表盘统计数据"""
    # TODO: 实现实际的统计逻辑
    return DashboardStats(
        totalProjects=50,
        activeProjects=30,
        totalTasks=200,
        completedTasks=150,
        overdueTasks=10,
        totalUsers=100,
        activeUsers=80,
        projectProgress=75.5,
        taskCompletionRate=75.0,
        recentActivity=25,
        completedProjects=15,
        myTasks=8,
        teamMembers=12
    )

@router.get("/recent-tasks", response_model=List[RecentTask])
async def get_recent_tasks(
    limit: int = Query(5, description="限制数量，默认5"),
    current_user=Depends(get_current_user)
):
    """获取最近任务列表"""
    # TODO: 实现实际的查询逻辑
    return [
        RecentTask(
            id="1",
            title="示例任务1",
            status="in_progress",
            priority="high",
            dueDate="2024-01-15",
            projectName="示例项目",
            assigneeName="张三"
        )
    ]

@router.get("/project-progress", response_model=List[ProjectProgress])
async def get_project_progress(
    limit: int = Query(10, description="限制数量，默认10"),
    current_user=Depends(get_current_user)
):
    """获取项目进度数据"""
    # TODO: 实现实际的查询逻辑
    return [
        ProjectProgress(
            projectId="1",
            projectName="示例项目",
            progress=75.5,
            totalTasks=20,
            completedTasks=15,
            status="active"
        )
    ]

@router.get("/task-status-distribution", response_model=List[TaskStatusDistribution])
async def get_task_status_distribution(
    projectId: Optional[str] = Query(None, description="项目ID"),
    dateFrom: Optional[str] = Query(None, description="日期范围开始"),
    dateTo: Optional[str] = Query(None, description="日期范围结束"),
    current_user=Depends(get_current_user)
):
    """获取任务状态分布数据"""
    # TODO: 实现实际的统计逻辑
    return [
        TaskStatusDistribution(status="todo", count=50, percentage=25.0),
        TaskStatusDistribution(status="in_progress", count=80, percentage=40.0),
        TaskStatusDistribution(status="completed", count=70, percentage=35.0)
    ]

@router.get("/recent-activities", response_model=List[RecentActivity])
async def get_recent_activities(
    limit: int = Query(20, description="限制数量，默认20"),
    current_user=Depends(get_current_user)
):
    """获取最近活动记录"""
    # TODO: 实现实际的查询逻辑
    return [
        RecentActivity(
            id="1",
            type="task",
            action="created",
            description="创建了新任务",
            userId="1",
            userName="张三",
            targetId="1",
            targetName="示例任务",
            createdAt=datetime.now().isoformat()
        )
    ]

@router.get("/user-workload", response_model=List[UserWorkload])
async def get_user_workload(
    departmentId: Optional[str] = Query(None, description="部门ID"),
    limit: Optional[int] = Query(None, description="限制数量"),
    current_user=Depends(get_current_user)
):
    """获取用户工作负载数据"""
    # TODO: 实现实际的查询逻辑
    return [
        UserWorkload(
            userId="1",
            userName="张三",
            totalTasks=20,
            completedTasks=15,
            inProgressTasks=3,
            overdueTasks=2,
            workloadPercentage=85.0
        )
    ]

@router.get("/project-trends", response_model=List[ProjectTrend])
async def get_project_trends(
    period: str = Query("month", description="时间周期 (week|month|quarter|year)"),
    departmentId: Optional[str] = Query(None, description="部门ID"),
    current_user=Depends(get_current_user)
):
    """获取项目统计趋势数据"""
    # TODO: 实现实际的统计逻辑
    return [
        ProjectTrend(
            period=period,
            totalProjects=50,
            completedProjects=15,
            activeProjects=30,
            date=datetime.now().strftime("%Y-%m-%d")
        )
    ]