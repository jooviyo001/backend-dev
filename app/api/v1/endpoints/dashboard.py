from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.organization import Organization
from app.schemas.base import BaseResponse

router = APIRouter()

# 仪表盘相关的 Pydantic 模式
from pydantic import BaseModel, Field
from typing import Optional

class DashboardOverview(BaseModel):
    """仪表盘概览数据"""
    total_projects: int = Field(..., description="项目总数")
    active_projects: int = Field(..., description="活跃项目数")
    total_tasks: int = Field(..., description="任务总数")
    completed_tasks: int = Field(..., description="已完成任务数")
    overdue_tasks: int = Field(..., description="逾期任务数")
    total_users: int = Field(..., description="用户总数")
    active_users: int = Field(..., description="活跃用户数")
    total_organizations: int = Field(..., description="组织总数")

class ProjectStatusChart(BaseModel):
    """项目状态图表数据"""
    labels: List[str] = Field(..., description="状态标签")
    data: List[int] = Field(..., description="对应数据")
    colors: List[str] = Field(..., description="颜色配置")

class TaskPriorityChart(BaseModel):
    """任务优先级图表数据"""
    labels: List[str] = Field(..., description="优先级标签")
    data: List[int] = Field(..., description="对应数据")
    colors: List[str] = Field(..., description="颜色配置")

class RecentActivity(BaseModel):
    """最近活动"""
    id: str
    type: str = Field(..., description="活动类型：project, task, user")
    title: str = Field(..., description="活动标题")
    description: str = Field(..., description="活动描述")
    user_name: str = Field(..., description="操作用户")
    created_at: datetime = Field(..., description="创建时间")

class ProgressTrend(BaseModel):
    """进度趋势数据"""
    date: str = Field(..., description="日期")
    completed_tasks: int = Field(..., description="完成任务数")
    created_tasks: int = Field(..., description="创建任务数")
    project_progress: float = Field(..., description="项目平均进度")

class UserPerformance(BaseModel):
    """用户绩效数据"""
    user_id: str
    user_name: str
    completed_tasks: int = Field(..., description="完成任务数")
    assigned_tasks: int = Field(..., description="分配任务数")
    completion_rate: float = Field(..., description="完成率")
    avg_completion_time: Optional[float] = Field(None, description="平均完成时间（小时）")

class DashboardData(BaseModel):
    """仪表盘完整数据"""
    overview: DashboardOverview
    project_status_chart: ProjectStatusChart
    task_priority_chart: TaskPriorityChart
    recent_activities: List[RecentActivity]
    progress_trend: List[ProgressTrend]
    top_performers: List[UserPerformance]

@router.get("/overview", response_model=BaseResponse[DashboardOverview])
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取仪表盘概览数据"""
    # 检查缓存
    cache_key = f"dashboard_overview:{current_user.id}"
    cached_overview = await redis_client.get(cache_key)
    if cached_overview:
        return BaseResponse(
            data=DashboardOverview(**cached_overview),
            message="获取成功"
        )
    
    # 构建基础查询（根据用户权限）
    if current_user.role in ["admin", "manager"]:
        # 管理员可以看到所有数据
        project_filter = select(Project.id)
        task_filter = select(Task.id)
        user_filter = select(User.id)
        org_filter = select(Organization.id)
    else:
        # 普通用户只能看到相关数据
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        project_filter = user_projects
        task_filter = select(Task.id).where(
            or_(
                Task.assignee_id == current_user.id,
                Task.reporter_id == current_user.id,
                Task.project_id.in_(user_projects)
            )
        )
        user_filter = select(User.id).where(User.id == current_user.id)
        org_filter = select(Organization.id).where(
            Organization.members.any(User.id == current_user.id)
        )
    
    # 项目统计
    total_projects_result = await db.execute(
        select(func.count()).select_from(project_filter.subquery())
    )
    total_projects = total_projects_result.scalar()
    
    active_projects_result = await db.execute(
        select(func.count()).select_from(
            project_filter.where(Project.status.in_(["planning", "active"])).subquery()
        )
    )
    active_projects = active_projects_result.scalar()
    
    # 任务统计
    total_tasks_result = await db.execute(
        select(func.count()).select_from(task_filter.subquery())
    )
    total_tasks = total_tasks_result.scalar()
    
    completed_tasks_result = await db.execute(
        select(func.count()).select_from(
            task_filter.where(Task.status == "done").subquery()
        )
    )
    completed_tasks = completed_tasks_result.scalar()
    
    # 逾期任务统计
    now = datetime.now()
    overdue_tasks_result = await db.execute(
        select(func.count()).select_from(
            task_filter.where(
                and_(
                    Task.due_date < now,
                    Task.status.notin_(["done", "cancelled"])
                )
            ).subquery()
        )
    )
    overdue_tasks = overdue_tasks_result.scalar()
    
    # 用户统计
    total_users_result = await db.execute(
        select(func.count()).select_from(user_filter.subquery())
    )
    total_users = total_users_result.scalar()
    
    # 活跃用户（最近30天有登录）
    thirty_days_ago = now - timedelta(days=30)
    active_users_result = await db.execute(
        select(func.count()).select_from(
            user_filter.where(User.last_login >= thirty_days_ago).subquery()
        )
    )
    active_users = active_users_result.scalar()
    
    # 组织统计
    total_organizations_result = await db.execute(
        select(func.count()).select_from(org_filter.subquery())
    )
    total_organizations = total_organizations_result.scalar()
    
    overview = DashboardOverview(
        total_projects=total_projects,
        active_projects=active_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        total_users=total_users,
        active_users=active_users,
        total_organizations=total_organizations
    )
    
    # 缓存结果
    await redis_client.set(cache_key, overview.dict(), expire=1800)  # 30分钟缓存
    
    return BaseResponse(
        data=overview,
        message="获取成功"
    )

@router.get("/charts/project-status", response_model=BaseResponse[ProjectStatusChart])
async def get_project_status_chart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取项目状态图表数据"""
    # 检查缓存
    cache_key = f"project_status_chart:{current_user.id}"
    cached_chart = await redis_client.get(cache_key)
    if cached_chart:
        return BaseResponse(
            data=ProjectStatusChart(**cached_chart),
            message="获取成功"
        )
    
    # 构建查询
    if current_user.role in ["admin", "manager"]:
        base_query = select(Project)
    else:
        base_query = select(Project).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
    
    # 按状态统计
    status_labels = ["planning", "active", "on_hold", "completed", "cancelled"]
    status_names = ["规划中", "进行中", "暂停", "已完成", "已取消"]
    status_colors = ["#3498db", "#2ecc71", "#f39c12", "#27ae60", "#e74c3c"]
    
    status_data = []
    for status in status_labels:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(Project.status == status).subquery()
            )
        )
        status_data.append(count_result.scalar())
    
    chart = ProjectStatusChart(
        labels=status_names,
        data=status_data,
        colors=status_colors
    )
    
    # 缓存结果
    await redis_client.set(cache_key, chart.dict(), expire=1800)
    
    return BaseResponse(
        data=chart,
        message="获取成功"
    )

@router.get("/charts/task-priority", response_model=BaseResponse[TaskPriorityChart])
async def get_task_priority_chart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取任务优先级图表数据"""
    # 检查缓存
    cache_key = f"task_priority_chart:{current_user.id}"
    cached_chart = await redis_client.get(cache_key)
    if cached_chart:
        return BaseResponse(
            data=TaskPriorityChart(**cached_chart),
            message="获取成功"
        )
    
    # 构建查询
    if current_user.role in ["admin", "manager"]:
        base_query = select(Task)
    else:
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        base_query = select(Task).where(
            or_(
                Task.assignee_id == current_user.id,
                Task.reporter_id == current_user.id,
                Task.project_id.in_(user_projects)
            )
        )
    
    # 按优先级统计
    priority_labels = ["low", "medium", "high", "urgent"]
    priority_names = ["低", "中", "高", "紧急"]
    priority_colors = ["#95a5a6", "#3498db", "#f39c12", "#e74c3c"]
    
    priority_data = []
    for priority in priority_labels:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(Task.priority == priority).subquery()
            )
        )
        priority_data.append(count_result.scalar())
    
    chart = TaskPriorityChart(
        labels=priority_names,
        data=priority_data,
        colors=priority_colors
    )
    
    # 缓存结果
    await redis_client.set(cache_key, chart.dict(), expire=1800)
    
    return BaseResponse(
        data=chart,
        message="获取成功"
    )

@router.get("/recent-activities", response_model=BaseResponse[List[RecentActivity]])
async def get_recent_activities(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取最近活动"""
    # 检查缓存
    cache_key = f"recent_activities:{current_user.id}:{limit}"
    cached_activities = await redis_client.get(cache_key)
    if cached_activities:
        return BaseResponse(
            data=[RecentActivity(**activity) for activity in cached_activities],
            message="获取成功"
        )
    
    activities = []
    
    # 获取最近的项目活动
    if current_user.role in ["admin", "manager"]:
        recent_projects = await db.execute(
            select(Project).order_by(Project.created_at.desc()).limit(limit // 3)
        )
    else:
        recent_projects = await db.execute(
            select(Project).where(
                or_(
                    Project.manager_id == current_user.id,
                    Project.members.any(User.id == current_user.id)
                )
            ).order_by(Project.created_at.desc()).limit(limit // 3)
        )
    
    for project in recent_projects.scalars():
        # 获取项目经理信息
        manager_result = await db.execute(
            select(User).where(User.id == project.manager_id)
        )
        manager = manager_result.scalar_one_or_none()
        
        activities.append(RecentActivity(
            id=project.id,
            type="project",
            title=f"项目创建：{project.name}",
            description=project.description or "无描述",
            user_name=manager.name if manager else "未知用户",
            created_at=project.created_at
        ))
    
    # 获取最近的任务活动
    if current_user.role in ["admin", "manager"]:
        recent_tasks = await db.execute(
            select(Task).order_by(Task.created_at.desc()).limit(limit // 3)
        )
    else:
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        recent_tasks = await db.execute(
            select(Task).where(
                or_(
                    Task.assignee_id == current_user.id,
                    Task.reporter_id == current_user.id,
                    Task.project_id.in_(user_projects)
                )
            ).order_by(Task.created_at.desc()).limit(limit // 3)
        )
    
    for task in recent_tasks.scalars():
        # 获取报告人信息
        reporter_result = await db.execute(
            select(User).where(User.id == task.reporter_id)
        )
        reporter = reporter_result.scalar_one_or_none()
        
        activities.append(RecentActivity(
            id=task.id,
            type="task",
            title=f"任务创建：{task.title}",
            description=task.description or "无描述",
            user_name=reporter.name if reporter else "未知用户",
            created_at=task.created_at
        ))
    
    # 获取最近的用户活动
    if current_user.role in ["admin", "manager"]:
        recent_users = await db.execute(
            select(User).order_by(User.created_at.desc()).limit(limit // 3)
        )
        
        for user in recent_users.scalars():
            activities.append(RecentActivity(
                id=user.id,
                type="user",
                title=f"用户注册：{user.username}",
                description=f"新用户 {user.name} 加入系统",
                user_name="系统",
                created_at=user.created_at
            ))
    
    # 按时间排序并限制数量
    activities.sort(key=lambda x: x.created_at, reverse=True)
    activities = activities[:limit]
    
    # 缓存结果
    await redis_client.set(
        cache_key, 
        [activity.dict() for activity in activities], 
        expire=900  # 15分钟缓存
    )
    
    return BaseResponse(
        data=activities,
        message="获取成功"
    )

@router.get("/progress-trend", response_model=BaseResponse[List[ProgressTrend]])
async def get_progress_trend(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取进度趋势数据"""
    # 检查缓存
    cache_key = f"progress_trend:{current_user.id}:{days}"
    cached_trend = await redis_client.get(cache_key)
    if cached_trend:
        return BaseResponse(
            data=[ProgressTrend(**trend) for trend in cached_trend],
            message="获取成功"
        )
    
    trends = []
    now = datetime.now()
    
    for i in range(days):
        date = now - timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        # 构建查询
        if current_user.role in ["admin", "manager"]:
            task_query = select(Task)
            project_query = select(Project)
        else:
            user_projects = select(Project.id).where(
                or_(
                    Project.manager_id == current_user.id,
                    Project.members.any(User.id == current_user.id)
                )
            )
            task_query = select(Task).where(
                or_(
                    Task.assignee_id == current_user.id,
                    Task.reporter_id == current_user.id,
                    Task.project_id.in_(user_projects)
                )
            )
            project_query = select(Project).where(
                or_(
                    Project.manager_id == current_user.id,
                    Project.members.any(User.id == current_user.id)
                )
            )
        
        # 当天完成的任务数
        completed_tasks_result = await db.execute(
            select(func.count()).select_from(
                task_query.where(
                    and_(
                        Task.completed_date >= date_start,
                        Task.completed_date < date_end
                    )
                ).subquery()
            )
        )
        completed_tasks = completed_tasks_result.scalar()
        
        # 当天创建的任务数
        created_tasks_result = await db.execute(
            select(func.count()).select_from(
                task_query.where(
                    and_(
                        Task.created_at >= date_start,
                        Task.created_at < date_end
                    )
                ).subquery()
            )
        )
        created_tasks = created_tasks_result.scalar()
        
        # 项目平均进度
        avg_progress_result = await db.execute(
            select(func.avg(Project.progress)).select_from(project_query.subquery())
        )
        avg_progress = avg_progress_result.scalar() or 0.0
        
        trends.append(ProgressTrend(
            date=date.strftime("%Y-%m-%d"),
            completed_tasks=completed_tasks,
            created_tasks=created_tasks,
            project_progress=round(avg_progress, 2)
        ))
    
    # 按日期正序排列
    trends.reverse()
    
    # 缓存结果
    await redis_client.set(
        cache_key,
        [trend.dict() for trend in trends],
        expire=3600  # 1小时缓存
    )
    
    return BaseResponse(
        data=trends,
        message="获取成功"
    )

@router.get("/top-performers", response_model=BaseResponse[List[UserPerformance]])
async def get_top_performers(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取绩效排行榜"""
    # 检查缓存
    cache_key = f"top_performers:{current_user.id}:{limit}"
    cached_performers = await redis_client.get(cache_key)
    if cached_performers:
        return BaseResponse(
            data=[UserPerformance(**performer) for performer in cached_performers],
            message="获取成功"
        )
    
    # 构建用户查询
    if current_user.role in ["admin", "manager"]:
        users_result = await db.execute(select(User))
    else:
        # 普通用户只能看到同项目的用户
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        users_result = await db.execute(
            select(User).where(
                or_(
                    User.id == current_user.id,
                    User.managed_projects.any(Project.id.in_(user_projects)),
                    User.projects.any(Project.id.in_(user_projects))
                )
            )
        )
    
    users = users_result.scalars().all()
    performers = []
    
    for user in users:
        # 统计用户任务数据
        completed_tasks_result = await db.execute(
            select(func.count(Task.id)).where(
                and_(
                    Task.assignee_id == user.id,
                    Task.status == "done"
                )
            )
        )
        completed_tasks = completed_tasks_result.scalar()
        
        assigned_tasks_result = await db.execute(
            select(func.count(Task.id)).where(Task.assignee_id == user.id)
        )
        assigned_tasks = assigned_tasks_result.scalar()
        
        # 计算完成率
        completion_rate = (completed_tasks / assigned_tasks * 100) if assigned_tasks > 0 else 0
        
        # 计算平均完成时间（简化计算）
        avg_completion_time = None
        if completed_tasks > 0:
            # 这里可以添加更复杂的计算逻辑
            avg_completion_time = 24.0  # 示例值
        
        performers.append(UserPerformance(
            user_id=user.id,
            user_name=user.name,
            completed_tasks=completed_tasks,
            assigned_tasks=assigned_tasks,
            completion_rate=round(completion_rate, 2),
            avg_completion_time=avg_completion_time
        ))
    
    # 按完成率排序
    performers.sort(key=lambda x: x.completion_rate, reverse=True)
    performers = performers[:limit]
    
    # 缓存结果
    await redis_client.set(
        cache_key,
        [performer.dict() for performer in performers],
        expire=3600  # 1小时缓存
    )
    
    return BaseResponse(
        data=performers,
        message="获取成功"
    )

@router.get("/", response_model=BaseResponse[DashboardData])
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("dashboard:view"))
):
    """获取完整的仪表盘数据"""
    # 检查缓存
    cache_key = f"dashboard_data:{current_user.id}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return BaseResponse(
            data=DashboardData(**cached_data),
            message="获取成功"
        )
    
    # 并发获取各部分数据
    import asyncio
    
    overview_task = get_dashboard_overview(db, current_user)
    project_chart_task = get_project_status_chart(db, current_user)
    task_chart_task = get_task_priority_chart(db, current_user)
    activities_task = get_recent_activities(10, db, current_user)
    trend_task = get_progress_trend(7, db, current_user)
    performers_task = get_top_performers(5, db, current_user)
    
    results = await asyncio.gather(
        overview_task,
        project_chart_task,
        task_chart_task,
        activities_task,
        trend_task,
        performers_task
    )
    
    dashboard_data = DashboardData(
        overview=results[0].data,
        project_status_chart=results[1].data,
        task_priority_chart=results[2].data,
        recent_activities=results[3].data,
        progress_trend=results[4].data,
        top_performers=results[5].data
    )
    
    # 缓存结果
    await redis_client.set(cache_key, dashboard_data.dict(), expire=1800)  # 30分钟缓存
    
    return BaseResponse(
        data=dashboard_data,
        message="获取成功"
    )