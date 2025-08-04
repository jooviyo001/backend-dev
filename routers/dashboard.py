import re
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from models.database import get_db
from models.models import User, Project, Task, Organization, ProjectStatus, TaskStatus, TaskPriority
from utils.auth import get_current_active_user
from utils.response_utils import list_response
from schemas.schemas import BaseResponse

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

# 任务趋势
@router.get("/stats", response_model=BaseResponse)
async def get_dashboard_stats(
    dateFrom: Optional[str] = Query(None, description="日期范围开始"),
    dateTo: Optional[str] = Query(None, description="日期范围结束"),
    departmentId: Optional[str] = Query(None, description="部门ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取仪表盘统计数据"""
    
    # 解析日期范围
    date_filter = []
    if dateFrom:
        try:
            start_date = datetime.fromisoformat(dateFrom.replace('Z', '+00:00'))
            date_filter.append(Project.created_at >= start_date)
        except ValueError:
            pass
    
    if dateTo:
        try:
            end_date = datetime.fromisoformat(dateTo.replace('Z', '+00:00'))
            date_filter.append(Project.created_at <= end_date)
        except ValueError:
            pass
    
    # 项目统计
    project_query = db.query(Project)
    if date_filter:
        project_query = project_query.filter(and_(*date_filter))
    
    total_projects = project_query.count()
    active_projects = project_query.filter(Project.status == ProjectStatus.ACTIVE).count()
    completed_projects = project_query.filter(Project.status == ProjectStatus.COMPLETED).count()
    
    # 任务统计
    task_query = db.query(Task)
    if date_filter:
        # 对任务也应用日期过滤
        task_date_filter = []
        if dateFrom:
            try:
                start_date = datetime.fromisoformat(dateFrom.replace('Z', '+00:00'))
                task_date_filter.append(Task.created_at >= start_date)
            except ValueError:
                pass
        if dateTo:
            try:
                end_date = datetime.fromisoformat(dateTo.replace('Z', '+00:00'))
                task_date_filter.append(Task.created_at <= end_date)
            except ValueError:
                pass
        if task_date_filter:
            task_query = task_query.filter(and_(*task_date_filter))
    
    total_tasks = task_query.count()
    completed_tasks = task_query.filter(Task.status == TaskStatus.DONE).count()
    
    # 逾期任务统计
    now = datetime.now()
    overdue_tasks = task_query.filter(
        and_(
            Task.due_date < now,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
        )
    ).count()
    
    # 用户统计
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # 当前用户的任务统计
    my_tasks = db.query(Task).filter(Task.assignee_id == current_user.id).count()
    
    # 计算项目进度（基于任务完成率）
    project_progress = 0.0
    if total_tasks > 0:
        project_progress = (completed_tasks / total_tasks) * 100
    
    # 任务完成率
    task_completion_rate = 0.0
    if total_tasks > 0:
        task_completion_rate = (completed_tasks / total_tasks) * 100
    
    # 最近活动数量（最近7天的任务和项目创建数）
    seven_days_ago = now - timedelta(days=7)
    recent_activity = (
        db.query(Task).filter(Task.created_at >= seven_days_ago).count() +
        db.query(Project).filter(Project.created_at >= seven_days_ago).count()
    )
    
    # 团队成员数量（当前用户参与的项目的所有成员）
    user_projects = db.query(Project).join(Project.members).filter(
        Project.members.any(User.id == current_user.id)
    ).all()
    
    team_members = set()
    for project in user_projects:
        for member in project.members:
            team_members.add(member.id)
    
    stats = DashboardStats(
        totalProjects=total_projects,
        activeProjects=active_projects,
        totalTasks=total_tasks,
        completedTasks=completed_tasks,
        overdueTasks=overdue_tasks,
        totalUsers=total_users,
        activeUsers=active_users,
        projectProgress=round(project_progress, 1),
        taskCompletionRate=round(task_completion_rate, 1),
        recentActivity=recent_activity,
        completedProjects=completed_projects,
        myTasks=my_tasks,
        teamMembers=len(team_members)
    )
    
    return BaseResponse(
        message="获取仪表盘统计数据成功",
        data=stats
    )

@router.get("/recent-tasks", response_model=BaseResponse)
async def get_recent_tasks(
    limit: int = Query(5, description="限制数量，默认5"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取最近任务列表"""
    
    # 查询最近创建的任务，包含项目和分配人信息
    tasks = db.query(Task).join(Project).join(User, Task.assignee_id == User.id, isouter=True)\
        .order_by(Task.created_at.desc())\
        .limit(limit)\
        .all()
    
    recent_tasks = []
    for task in tasks:
        recent_task = RecentTask(
            id=str(task.id),
            title=task.title,
            status=task.status.value,
            priority=task.priority.value,
            dueDate=task.due_date.isoformat() if task.due_date else None,
            projectName=task.project.name if task.project else "未分配项目",
            assigneeName=task.assignee.name if task.assignee else "未分配"
        )
        recent_tasks.append(recent_task)
    
    return BaseResponse(
        message="获取最近任务列表成功",
        data=recent_tasks
    )


@router.get("/project-progress", response_model=BaseResponse)
async def get_project_progress(
    limit: int = Query(10, description="限制数量，默认10"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取项目进度数据"""
    
    # 查询项目及其任务统计
    projects = db.query(Project)\
        .filter(Project.is_archived == False)\
        .order_by(Project.created_at.desc())\
        .limit(limit)\
        .all()
    
    project_progress_list = []
    for project in projects:
        # 统计项目的任务数量
        total_tasks = db.query(Task).filter(Task.project_id == project.id).count()
        completed_tasks = db.query(Task).filter(
            and_(Task.project_id == project.id, Task.status == TaskStatus.DONE)
        ).count()
        
        # 计算进度百分比
        progress = 0.0
        if total_tasks > 0:
            progress = (completed_tasks / total_tasks) * 100
        
        project_progress_item = ProjectProgress(
            projectId=str(project.id),
            projectName=project.name,
            progress=round(progress, 1),
            totalTasks=total_tasks,
            completedTasks=completed_tasks,
            status=project.status.value
        )
        project_progress_list.append(project_progress_item)
    
    return BaseResponse(
        message="获取项目进度数据成功",
        items=project_progress_list
    )

# 替换为当前用户的任务状态分布数据
@router.get("/task-status-distribution", response_model=BaseResponse)
async def get_task_status_distribution(
    projectId: Optional[str] = Query(None, description="项目ID"),
    dateFrom: Optional[str] = Query(None, description="日期范围开始"),
    dateTo: Optional[str] = Query(None, description="日期范围结束"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取任务状态分布数据"""
    
    # 构建查询条件
    query = db.query(Task.status, func.count(Task.id).label('count'))
    
    # 项目过滤
    if projectId:
        # ID格式处理函数
        def extract_id(id_str):
            """提取ID的数字部分，兼容多种格式"""
            if not id_str:
                return None
            # 如果是纯数字，直接返回
            if id_str.isdigit():
                return int(id_str)
            # 如果是以P开头的新格式，提取数字部分
            if id_str.startswith('P') and id_str[1:].isdigit():
                return int(id_str[1:])
            return None
        
        extracted_project_id = extract_id(projectId)
        if extracted_project_id:
            query = query.filter(Task.project_id == extracted_project_id)
    
    # 日期过滤
    if dateFrom:
        try:
            start_date = datetime.fromisoformat(dateFrom.replace('Z', '+00:00'))
            query = query.filter(Task.created_at >= start_date)
        except ValueError:
            pass
    
    if dateTo:
        try:
            end_date = datetime.fromisoformat(dateTo.replace('Z', '+00:00'))
            query = query.filter(Task.created_at <= end_date)
        except ValueError:
            pass
    
    # 按状态分组统计
    status_counts = query.group_by(Task.status).all()
    
    # 计算总数
    total_count = sum(count for _, count in status_counts)
    
    # 构建结果
    distribution = []
    for status, count in status_counts:
        percentage = (count / total_count * 100) if total_count > 0 else 0
        distribution.append(TaskStatusDistribution(
            status=status.value,
            count=count,
            percentage=round(percentage, 1)
        ))
    
    # 如果没有数据，返回默认的状态分布
    if not distribution:
        for status in TaskStatus:
            distribution.append(TaskStatusDistribution(
                status=status.value,
                count=0,
                percentage=0.0
            ))
    
    return BaseResponse(
        message="获取任务状态分布数据成功",
        data=distribution
    )

# 替换为当前用户的最近活动记录
@router.get("/recent-activities", response_model=BaseResponse)
async def get_recent_activities(
    limit: int = Query(20, description="限制数量，默认20"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取最近活动记录"""
    
    # 查询最近的任务活动（创建、更新等）
    recent_tasks = db.query(Task).join(Project).join(User, Task.assignee_id == User.id, isouter=True)\
        .order_by(Task.updated_at.desc())\
        .limit(limit)\
        .all()
    
    activities = []
    for task in recent_tasks:
        # 判断活动类型
        action = "updated"
        if task.created_at == task.updated_at:
            action = "created"
        
        activity = RecentActivity(
            id=str(task.id),
            type="task",
            action=action,
            description=f"{'创建' if action == 'created' else '更新'}了任务: {task.title}",
            userId=str(task.assignee_id) if task.assignee_id else str(current_user.id),
            userName=task.assignee.name if task.assignee else current_user.name,
            targetId=str(task.id),
            targetName=task.title,
            createdAt=task.updated_at.isoformat()
        )
        activities.append(activity)
    
    return BaseResponse(
        message="获取最近活动记录成功",
        data=activities
    )

# 替换为当前用户的用户工作负载数据
@router.get("/user-workload", response_model=BaseResponse)
async def get_user_workload(
    departmentId: Optional[str] = Query(None, description="部门ID"),
    limit: Optional[int] = Query(10, description="限制数量，默认10"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取用户工作负载数据"""
    
    # 构建用户查询
    query = db.query(User).filter(User.is_active == True)
    
    # 部门过滤（如果有部门字段的话）
    if departmentId:
        # ID格式处理函数
        def extract_id(id_str):
            """提取ID的数字部分，兼容多种格式"""
            if not id_str:
                return None
            # 如果是纯数字，直接返回
            if id_str.isdigit():
                return int(id_str)
            # 如果是以O开头的新格式，提取数字部分
            if id_str.startswith('O') and id_str[1:].isdigit():
                return int(id_str[1:])
            return None
        
        extracted_dept_id = extract_id(departmentId)
        if extracted_dept_id:
            # 假设User模型有department_id字段，如果没有可以去掉这个过滤
            # query = query.filter(User.department_id == extracted_dept_id)
            pass
    
    if limit:
        query = query.limit(limit)
    
    users = query.all()
    
    user_workloads = []
    for user in users:
        # 统计用户的任务数量
        total_tasks = db.query(Task).filter(Task.assignee_id == user.id).count()
        completed_tasks = db.query(Task).filter(
            and_(Task.assignee_id == user.id, Task.status == TaskStatus.DONE)
        ).count()
        in_progress_tasks = db.query(Task).filter(
            and_(Task.assignee_id == user.id, Task.status == TaskStatus.IN_PROGRESS)
        ).count()
        
        # 统计逾期任务
        overdue_tasks = db.query(Task).filter(
            and_(
                Task.assignee_id == user.id,
                Task.due_date < datetime.now(),
                Task.status != TaskStatus.DONE
            )
        ).count()
        
        # 计算工作负载百分比（基于完成率）
        workload_percentage = 0.0
        if total_tasks > 0:
            workload_percentage = (completed_tasks / total_tasks) * 100
        
        user_workload = UserWorkload(
            userId=str(user.id),
            userName=user.name,
            totalTasks=total_tasks,
            completedTasks=completed_tasks,
            inProgressTasks=in_progress_tasks,
            overdueTasks=overdue_tasks,
            workloadPercentage=round(workload_percentage, 1)
        )
        user_workloads.append(user_workload)
    
    return BaseResponse(
        message="获取用户工作负载数据成功",
        data=user_workloads
    )

@router.get("/project-trends", response_model=BaseResponse)
async def get_project_trends(
    period: str = Query("month", description="时间周期 (week|month|quarter|year)"),
    departmentId: Optional[str] = Query(None, description="部门ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取项目统计趋势数据"""
    
    # 根据周期计算时间范围
    now = datetime.now()
    if period == "week":
        periods = 12  # 12周
        delta = timedelta(weeks=1)
    elif period == "month":
        periods = 12  # 12个月
        delta = timedelta(days=30)
    elif period == "quarter":
        periods = 8   # 8个季度
        delta = timedelta(days=90)
    elif period == "year":
        periods = 5   # 5年
        delta = timedelta(days=365)
    else:
        periods = 12
        delta = timedelta(days=30)
    
    trends = []
    for i in range(periods):
        # 计算时间范围
        end_date = now - (delta * i)
        start_date = end_date - delta
        
        # 构建项目查询
        query = db.query(Project)
        
        # 部门过滤（如果Project模型有department_id字段）
        if departmentId:
            # ID格式处理函数
            def extract_id(id_str):
                """提取ID的数字部分，兼容多种格式"""
                if not id_str:
                    return None
                # 如果是纯数字，直接返回
                if id_str.isdigit():
                    return int(id_str)
                # 如果是以O开头的新格式，提取数字部分
                if id_str.startswith('O') and id_str[1:].isdigit():
                    return int(id_str[1:])
                return None
            
            extracted_dept_id = extract_id(departmentId)
            if extracted_dept_id:
                # query = query.filter(Project.department_id == extracted_dept_id)
                pass
        
        # 统计该时间段内的项目
        total_projects = query.filter(
            Project.created_at.between(start_date, end_date)
        ).count()
        
        completed_projects = query.filter(
            and_(
                Project.created_at.between(start_date, end_date),
                Project.status == ProjectStatus.COMPLETED
            )
        ).count()
        
        active_projects = query.filter(
            and_(
                Project.created_at.between(start_date, end_date),
                Project.status == ProjectStatus.ACTIVE
            )
        ).count()
        
        # 格式化日期
        if period == "week":
            date_str = start_date.strftime("%Y-W%U")
        elif period == "month":
            date_str = start_date.strftime("%Y-%m")
        elif period == "quarter":
            quarter = (start_date.month - 1) // 3 + 1
            date_str = f"{start_date.year}-Q{quarter}"
        else:  # year
            date_str = start_date.strftime("%Y")
        
        trend = ProjectTrend(
            period=period,
            totalProjects=total_projects,
            completedProjects=completed_projects,
            activeProjects=active_projects,
            date=date_str
        )
        trends.append(trend)
    
    # 按日期排序（最新的在前）
    trends.reverse()
    
    return BaseResponse(
        message="获取项目统计趋势数据成功",
        data=trends
    )