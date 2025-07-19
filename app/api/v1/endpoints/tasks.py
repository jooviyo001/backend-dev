from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
import json

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse,
    TaskStatusUpdate, TaskAssign, TaskStatistics, TaskSearchParams,
    BatchTaskStatusUpdate, BatchTaskAssign, BatchTaskPriorityUpdate,
    TaskStatus, TaskPriority, TaskType
)
from app.schemas.base import BaseResponse, PaginationParams, PaginationResponse, BatchOperationResponse

router = APIRouter()

@router.get("/", response_model=BaseResponse[PaginationResponse[TaskResponse]])
async def get_tasks(
    pagination: PaginationParams = Depends(),
    search: TaskSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:view"))
):
    """获取任务列表"""
    query = select(Task)
    
    # 搜索条件
    if search.keyword:
        query = query.where(
            or_(
                Task.title.contains(search.keyword),
                Task.description.contains(search.keyword)
            )
        )
    
    if search.status:
        query = query.where(Task.status == search.status)
    
    if search.priority:
        query = query.where(Task.priority == search.priority)
    
    if search.type:
        query = query.where(Task.type == search.type)
    
    if search.project_id:
        query = query.where(Task.project_id == search.project_id)
    
    if search.assignee_id:
        query = query.where(Task.assignee_id == search.assignee_id)
    
    if search.reporter_id:
        query = query.where(Task.reporter_id == search.reporter_id)
    
    if search.due_date_from:
        query = query.where(Task.due_date >= search.due_date_from)
    
    if search.due_date_to:
        query = query.where(Task.due_date <= search.due_date_to)
    
    if search.parent_task_id:
        query = query.where(Task.parent_task_id == search.parent_task_id)
    
    if search.tags:
        for tag in search.tags:
            query = query.where(Task.tags.contains(tag))
    
    # 权限过滤：非管理员只能看到相关的任务
    if current_user.role not in ["admin", "manager"]:
        # 获取用户参与的项目
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        
        query = query.where(
            or_(
                Task.assignee_id == current_user.id,
                Task.reporter_id == current_user.id,
                Task.project_id.in_(user_projects)
            )
        )
    
    # 总数查询
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页和排序
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    # 排序
    if pagination.sort:
        for sort_item in pagination.sort.split(','):
            if ':' in sort_item:
                field, direction = sort_item.split(':')
                if hasattr(Task, field):
                    if direction.lower() == 'desc':
                        query = query.order_by(getattr(Task, field).desc())
                    else:
                        query = query.order_by(getattr(Task, field).asc())
    else:
        query = query.order_by(Task.created_at.desc())
    
    # 执行查询
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # 计算分页信息
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_prev = pagination.page > 1
    
    return BaseResponse(
        data=PaginationResponse(
            items=[TaskResponse.from_orm(task) for task in tasks],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        ),
        message="获取成功"
    )

@router.post("/", response_model=BaseResponse[TaskResponse])
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:create"))
):
    """创建任务"""
    # 验证项目是否存在
    project_result = await db.execute(select(Project).where(Project.id == task_data.project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目不存在"
        )
    
    # 验证指派人是否存在
    if task_data.assignee_id:
        assignee_result = await db.execute(select(User).where(User.id == task_data.assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指派人不存在"
            )
    
    # 验证报告人是否存在
    reporter_result = await db.execute(select(User).where(User.id == task_data.reporter_id))
    reporter = reporter_result.scalar_one_or_none()
    if not reporter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="报告人不存在"
        )
    
    # 验证父任务是否存在
    if task_data.parent_task_id:
        parent_result = await db.execute(select(Task).where(Task.id == task_data.parent_task_id))
        parent_task = parent_result.scalar_one_or_none()
        if not parent_task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父任务不存在"
            )
        if parent_task.project_id != task_data.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父任务必须在同一项目中"
            )
    
    # 创建任务
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        type=task_data.type,
        due_date=task_data.due_date,
        start_date=task_data.start_date,
        estimated_hours=task_data.estimated_hours,
        tags=json.dumps(task_data.tags) if task_data.tags else None,
        project_id=task_data.project_id,
        assignee_id=task_data.assignee_id,
        reporter_id=task_data.reporter_id,
        parent_task_id=task_data.parent_task_id
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    return BaseResponse(
        data=TaskResponse.from_orm(new_task),
        message="任务创建成功"
    )

@router.get("/{task_id}", response_model=BaseResponse[TaskDetailResponse])
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:view"))
):
    """获取任务详情"""
    # 从数据库获取
    query = select(Task).options(
        selectinload(Task.project),
        selectinload(Task.assignee),
        selectinload(Task.reporter),
        selectinload(Task.parent_task),
        selectinload(Task.subtasks)
    ).where(Task.id == task_id)
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        # 检查是否有权限访问此任务
        has_permission = (
            task.assignee_id == current_user.id or
            task.reporter_id == current_user.id or
            task.project.manager_id == current_user.id or
            any(member.id == current_user.id for member in task.project.members)
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问此任务"
            )
    
    # 构建响应数据
    task_detail = TaskDetailResponse(
        **TaskResponse.from_orm(task).dict(),
        project={
            "id": task.project.id,
            "name": task.project.name,
            "status": task.project.status
        } if task.project else None,
        assignee={
            "id": task.assignee.id,
            "username": task.assignee.username,
            "name": task.assignee.name,
            "avatar": task.assignee.avatar
        } if task.assignee else None,
        reporter={
            "id": task.reporter.id,
            "username": task.reporter.username,
            "name": task.reporter.name,
            "avatar": task.reporter.avatar
        } if task.reporter else None,
        parent_task={
            "id": task.parent_task.id,
            "title": task.parent_task.title,
            "status": task.parent_task.status
        } if task.parent_task else None,
        subtasks=[
            {
                "id": subtask.id,
                "title": subtask.title,
                "status": subtask.status,
                "priority": subtask.priority
            } for subtask in task.subtasks
        ]
    )
    
    return BaseResponse(
        data=task_detail,
        message="获取成功"
    )

@router.put("/{task_id}", response_model=BaseResponse[TaskResponse])
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:edit"))
):
    """更新任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        # 获取项目信息
        project_result = await db.execute(select(Project).where(Project.id == task.project_id))
        project = project_result.scalar_one()
        
        has_permission = (
            task.assignee_id == current_user.id or
            task.reporter_id == current_user.id or
            project.manager_id == current_user.id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限编辑此任务"
            )
    
    # 验证新的指派人
    if task_data.assignee_id and task_data.assignee_id != task.assignee_id:
        assignee_result = await db.execute(select(User).where(User.id == task_data.assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指派人不存在"
            )
    
    # 验证父任务
    if task_data.parent_task_id and task_data.parent_task_id != task.parent_task_id:
        if task_data.parent_task_id == task_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务不能设置自己为父任务"
            )
        
        parent_result = await db.execute(select(Task).where(Task.id == task_data.parent_task_id))
        parent_task = parent_result.scalar_one_or_none()
        if not parent_task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父任务不存在"
            )
        if parent_task.project_id != task.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父任务必须在同一项目中"
            )
    
    # 更新任务信息
    update_data = task_data.dict(exclude_unset=True)
    if 'tags' in update_data and update_data['tags'] is not None:
        update_data['tags'] = json.dumps(update_data['tags'])
    
    # 如果状态更新为完成，设置完成时间
    if 'status' in update_data and update_data['status'] == 'done' and task.status != 'done':
        from datetime import datetime
        task.completed_date = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    
    return BaseResponse(
        data=TaskResponse.from_orm(task),
        message="任务更新成功"
    )

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:delete"))
):
    """删除任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        project_result = await db.execute(select(Project).where(Project.id == task.project_id))
        project = project_result.scalar_one()
        
        has_permission = (
            task.reporter_id == current_user.id or
            project.manager_id == current_user.id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限删除此任务"
            )
    
    await db.delete(task)
    await db.commit()
    
    return BaseResponse(message="任务删除成功")

@router.put("/{task_id}/status", response_model=BaseResponse[TaskResponse])
async def update_task_status(
    task_id: str,
    status_data: TaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:edit"))
):
    """更新任务状态"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        project_result = await db.execute(select(Project).where(Project.id == task.project_id))
        project = project_result.scalar_one()
        
        has_permission = (
            task.assignee_id == current_user.id or
            task.reporter_id == current_user.id or
            project.manager_id == current_user.id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限更新此任务状态"
            )
    
    # 如果状态更新为完成，设置完成时间
    if status_data.status == TaskStatus.DONE and task.status != TaskStatus.DONE:
        from datetime import datetime
        task.completed_date = datetime.utcnow()
    
    task.status = status_data.status
    await db.commit()
    await db.refresh(task)
    
    return BaseResponse(
        data=TaskResponse.from_orm(task),
        message="任务状态更新成功"
    )

@router.put("/{task_id}/assign", response_model=BaseResponse[TaskResponse])
async def assign_task(
    task_id: str,
    assign_data: TaskAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:edit"))
):
    """分配任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 验证指派人是否存在
    assignee_result = await db.execute(select(User).where(User.id == assign_data.assignee_id))
    assignee = assignee_result.scalar_one_or_none()
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指派人不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        project_result = await db.execute(select(Project).where(Project.id == task.project_id))
        project = project_result.scalar_one()
        
        has_permission = (
            task.reporter_id == current_user.id or
            project.manager_id == current_user.id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限分配此任务"
            )
    
    task.assignee_id = assign_data.assignee_id
    await db.commit()
    await db.refresh(task)
    
    return BaseResponse(
        data=TaskResponse.from_orm(task),
        message="任务分配成功"
    )

@router.get("/statistics", response_model=BaseResponse[TaskStatistics])
async def get_task_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:view"))
):
    """获取任务统计信息"""
    # 检查缓存
    cache_key = f"task_statistics:{current_user.id}"
    cached_stats = await redis_client.get(cache_key)
    if cached_stats:
        return BaseResponse(
            data=TaskStatistics(**cached_stats),
            message="获取成功"
        )
    
    # 构建基础查询（根据用户权限）
    base_query = select(Task)
    if current_user.role not in ["admin", "manager"]:
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        base_query = base_query.where(
            or_(
                Task.assignee_id == current_user.id,
                Task.reporter_id == current_user.id,
                Task.project_id.in_(user_projects)
            )
        )
    
    # 总任务数
    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar()
    
    # 按状态统计
    by_status = {}
    for status in TaskStatus:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(Task.status == status.value).subquery()
            )
        )
        by_status[status.value] = count_result.scalar()
    
    # 按优先级统计
    by_priority = {}
    for priority in TaskPriority:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(Task.priority == priority.value).subquery()
            )
        )
        by_priority[priority.value] = count_result.scalar()
    
    # 按类型统计
    by_type = {}
    for task_type in TaskType:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(Task.type == task_type.value).subquery()
            )
        )
        by_type[task_type.value] = count_result.scalar()
    
    # 逾期任务数
    from datetime import datetime
    overdue_result = await db.execute(
        select(func.count()).select_from(
            base_query.where(
                and_(
                    Task.due_date < datetime.now(),
                    Task.status.notin_(["done", "cancelled"])
                )
            ).subquery()
        )
    )
    overdue_tasks = overdue_result.scalar()
    
    # 本周完成的任务数
    from datetime import timedelta
    week_start = datetime.now() - timedelta(days=7)
    completed_this_week_result = await db.execute(
        select(func.count()).select_from(
            base_query.where(
                and_(
                    Task.status == "done",
                    Task.completed_date >= week_start
                )
            ).subquery()
        )
    )
    completed_this_week = completed_this_week_result.scalar()
    
    # 分配给我的任务数
    assigned_to_me_result = await db.execute(
        select(func.count(Task.id)).where(Task.assignee_id == current_user.id)
    )
    assigned_to_me = assigned_to_me_result.scalar()
    
    # 我报告的任务数
    reported_by_me_result = await db.execute(
        select(func.count(Task.id)).where(Task.reporter_id == current_user.id)
    )
    reported_by_me = reported_by_me_result.scalar()
    
    stats = TaskStatistics(
        total=total,
        by_status=by_status,
        by_priority=by_priority,
        by_type=by_type,
        overdue_tasks=overdue_tasks,
        completed_this_week=completed_this_week,
        assigned_to_me=assigned_to_me,
        reported_by_me=reported_by_me
    )
    
    # 缓存统计数据
    await redis_client.set(cache_key, stats.dict(), expire=1800)
    
    return BaseResponse(
        data=stats,
        message="获取成功"
    )

@router.put("/batch/status", response_model=BaseResponse[BatchOperationResponse])
async def batch_update_task_status(
    batch_data: BatchTaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:edit"))
):
    """批量更新任务状态"""
    success_count = 0
    failed_count = 0
    success_ids = []
    failed_items = []
    
    for task_id in batch_data.task_ids:
        try:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            
            if not task:
                failed_count += 1
                failed_items.append({"task_id": task_id, "error": "任务不存在"})
                continue
            
            # 权限检查
            if current_user.role not in ["admin", "manager"]:
                project_result = await db.execute(select(Project).where(Project.id == task.project_id))
                project = project_result.scalar_one()
                
                has_permission = (
                    task.assignee_id == current_user.id or
                    task.reporter_id == current_user.id or
                    project.manager_id == current_user.id
                )
                if not has_permission:
                    failed_count += 1
                    failed_items.append({"task_id": task_id, "error": "无权限更新此任务"})
                    continue
            
            # 如果状态更新为完成，设置完成时间
            if batch_data.status == TaskStatus.DONE and task.status != TaskStatus.DONE:
                from datetime import datetime
                task.completed_date = datetime.utcnow()
            
            task.status = batch_data.status
            success_count += 1
            success_ids.append(task_id)
            
        except Exception as e:
            failed_count += 1
            failed_items.append({"task_id": task_id, "error": str(e)})
    
    await db.commit()
    
    return BaseResponse(
        data=BatchOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            success_ids=success_ids,
            failed_items=failed_items,
            total=len(batch_data.task_ids)
        ),
        message=f"批量状态更新完成，成功{success_count}个，失败{failed_count}个"
    )

@router.put("/batch/assign", response_model=BaseResponse[BatchOperationResponse])
async def batch_assign_tasks(
    batch_data: BatchTaskAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("task:edit"))
):
    """批量分配任务"""
    # 验证指派人是否存在
    assignee_result = await db.execute(select(User).where(User.id == batch_data.assignee_id))
    assignee = assignee_result.scalar_one_or_none()
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指派人不存在"
        )
    
    success_count = 0
    failed_count = 0
    success_ids = []
    failed_items = []
    
    for task_id in batch_data.task_ids:
        try:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            
            if not task:
                failed_count += 1
                failed_items.append({"task_id": task_id, "error": "任务不存在"})
                continue
            
            # 权限检查
            if current_user.role not in ["admin", "manager"]:
                project_result = await db.execute(select(Project).where(Project.id == task.project_id))
                project = project_result.scalar_one()
                
                has_permission = (
                    task.reporter_id == current_user.id or
                    project.manager_id == current_user.id
                )
                if not has_permission:
                    failed_count += 1
                    failed_items.append({"task_id": task_id, "error": "无权限分配此任务"})
                    continue
            
            task.assignee_id = batch_data.assignee_id
            success_count += 1
            success_ids.append(task_id)
            
        except Exception as e:
            failed_count += 1
            failed_items.append({"task_id": task_id, "error": str(e)})
    
    await db.commit()
    
    return BaseResponse(
        data=BatchOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            success_ids=success_ids,
            failed_items=failed_items,
            total=len(batch_data.task_ids)
        ),
        message=f"批量任务分配完成，成功{success_count}个，失败{failed_count}个"
    )