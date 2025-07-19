from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List
import json

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.project import Project, project_members
from app.models.task import Task
from app.models.organization import Organization
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetailResponse,
    ProjectProgressUpdate, ProjectMemberAdd, ProjectMemberRemove,
    ProjectStatistics, ProjectSearchParams, BatchProjectStatusUpdate,
    BatchProjectMemberAssign, ProjectStatus, ProjectPriority
)
from app.schemas.base import BaseResponse, PaginationParams, PaginationResponse, BatchOperationResponse

router = APIRouter()

@router.get("/", response_model=BaseResponse[PaginationResponse[ProjectResponse]])
async def get_projects(
    pagination: PaginationParams = Depends(),
    search: ProjectSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:view"))
):
    """获取项目列表"""
    query = select(Project)
    
    # 搜索条件
    if search.keyword:
        query = query.where(
            or_(
                Project.name.contains(search.keyword),
                Project.description.contains(search.keyword)
            )
        )
    
    if search.status:
        query = query.where(Project.status == search.status)
    
    if search.priority:
        query = query.where(Project.priority == search.priority)
    
    if search.manager_id:
        query = query.where(Project.manager_id == search.manager_id)
    
    if search.organization_id:
        query = query.where(Project.organization_id == search.organization_id)
    
    if search.start_date_from:
        query = query.where(Project.start_date >= search.start_date_from)
    
    if search.start_date_to:
        query = query.where(Project.start_date <= search.start_date_to)
    
    if search.tags:
        # 标签搜索（JSON字段）
        for tag in search.tags:
            query = query.where(Project.tags.contains(tag))
    
    # 权限过滤：非管理员只能看到自己管理或参与的项目
    if current_user.role not in ["admin", "manager"]:
        query = query.where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
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
                if hasattr(Project, field):
                    if direction.lower() == 'desc':
                        query = query.order_by(getattr(Project, field).desc())
                    else:
                        query = query.order_by(getattr(Project, field).asc())
    else:
        query = query.order_by(Project.created_at.desc())
    
    # 执行查询
    result = await db.execute(query)
    projects = result.scalars().all()
    
    # 计算分页信息
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_prev = pagination.page > 1
    
    return BaseResponse(
        data=PaginationResponse(
            items=[ProjectResponse.from_orm(project) for project in projects],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        ),
        message="获取成功"
    )

@router.post("/", response_model=BaseResponse[ProjectResponse])
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:create"))
):
    """创建项目"""
    # 验证项目经理是否存在
    manager_result = await db.execute(select(User).where(User.id == project_data.manager_id))
    manager = manager_result.scalar_one_or_none()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目经理不存在"
        )
    
    # 验证组织是否存在
    if project_data.organization_id:
        org_result = await db.execute(select(Organization).where(Organization.id == project_data.organization_id))
        organization = org_result.scalar_one_or_none()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="组织不存在"
            )
    
    # 创建项目
    new_project = Project(
        name=project_data.name,
        description=project_data.description,
        status=project_data.status,
        priority=project_data.priority,
        start_date=project_data.start_date,
        end_date=project_data.end_date,
        budget=project_data.budget,
        estimated_hours=project_data.estimated_hours,
        tags=json.dumps(project_data.tags) if project_data.tags else None,
        manager_id=project_data.manager_id,
        organization_id=project_data.organization_id
    )
    
    db.add(new_project)
    await db.flush()  # 获取项目ID
    
    # 添加项目成员
    if project_data.member_ids:
        for member_id in project_data.member_ids:
            # 验证成员是否存在
            member_result = await db.execute(select(User).where(User.id == member_id))
            member = member_result.scalar_one_or_none()
            if member:
                # 添加到项目成员关联表
                await db.execute(
                    project_members.insert().values(
                        project_id=new_project.id,
                        user_id=member_id,
                        role="member"
                    )
                )
    
    await db.commit()
    await db.refresh(new_project)
    
    return BaseResponse(
        data=ProjectResponse.from_orm(new_project),
        message="项目创建成功"
    )

@router.get("/{project_id}", response_model=BaseResponse[ProjectDetailResponse])
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:view"))
):
    """获取项目详情"""
    # 先从缓存获取
    cached_project = await redis_client.get(f"project:{project_id}")
    if cached_project:
        return BaseResponse(
            data=ProjectDetailResponse(**cached_project),
            message="获取成功"
        )
    
    # 从数据库获取
    query = select(Project).options(
        selectinload(Project.manager),
        selectinload(Project.members),
        selectinload(Project.organization)
    ).where(Project.id == project_id)
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 权限检查：非管理员只能查看自己管理或参与的项目
    if current_user.role not in ["admin", "manager"]:
        is_manager = project.manager_id == current_user.id
        is_member = any(member.id == current_user.id for member in project.members)
        if not (is_manager or is_member):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问此项目"
            )
    
    # 获取任务统计
    task_count_result = await db.execute(
        select(func.count(Task.id)).where(Task.project_id == project_id)
    )
    task_count = task_count_result.scalar()
    
    completed_task_count_result = await db.execute(
        select(func.count(Task.id)).where(
            and_(Task.project_id == project_id, Task.status == "done")
        )
    )
    completed_task_count = completed_task_count_result.scalar()
    
    # 构建响应数据
    project_detail = ProjectDetailResponse(
        **ProjectResponse.from_orm(project).dict(),
        manager={
            "id": project.manager.id,
            "username": project.manager.username,
            "name": project.manager.name,
            "avatar": project.manager.avatar
        } if project.manager else None,
        members=[
            {
                "id": member.id,
                "username": member.username,
                "name": member.name,
                "avatar": member.avatar,
                "role": member.role
            } for member in project.members
        ],
        organization={
            "id": project.organization.id,
            "name": project.organization.name,
            "type": project.organization.type
        } if project.organization else None,
        task_count=task_count,
        completed_task_count=completed_task_count
    )
    
    # 缓存项目详情
    await redis_client.set(f"project:{project_id}", project_detail.dict(), expire=1800)
    
    return BaseResponse(
        data=project_detail,
        message="获取成功"
    )

@router.put("/{project_id}", response_model=BaseResponse[ProjectResponse])
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:edit"))
):
    """更新项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 权限检查：非管理员只能编辑自己管理的项目
    if current_user.role not in ["admin", "manager"] and project.manager_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限编辑此项目"
        )
    
    # 验证新的项目经理
    if project_data.manager_id and project_data.manager_id != project.manager_id:
        manager_result = await db.execute(select(User).where(User.id == project_data.manager_id))
        manager = manager_result.scalar_one_or_none()
        if not manager:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目经理不存在"
            )
    
    # 验证组织
    if project_data.organization_id and project_data.organization_id != project.organization_id:
        org_result = await db.execute(select(Organization).where(Organization.id == project_data.organization_id))
        organization = org_result.scalar_one_or_none()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="组织不存在"
            )
    
    # 更新项目信息
    update_data = project_data.dict(exclude_unset=True)
    if 'tags' in update_data and update_data['tags'] is not None:
        update_data['tags'] = json.dumps(update_data['tags'])
    
    for field, value in update_data.items():
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    
    # 清除缓存
    await redis_client.delete(f"project:{project_id}")
    
    return BaseResponse(
        data=ProjectResponse.from_orm(project),
        message="项目更新成功"
    )

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:delete"))
):
    """删除项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and project.manager_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限删除此项目"
        )
    
    await db.delete(project)
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"project:{project_id}")
    
    return BaseResponse(message="项目删除成功")

@router.put("/{project_id}/progress", response_model=BaseResponse[ProjectResponse])
async def update_project_progress(
    project_id: str,
    progress_data: ProjectProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:edit"))
):
    """更新项目进度"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and project.manager_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限更新此项目进度"
        )
    
    project.progress = progress_data.progress
    await db.commit()
    await db.refresh(project)
    
    # 清除缓存
    await redis_client.delete(f"project:{project_id}")
    
    return BaseResponse(
        data=ProjectResponse.from_orm(project),
        message="项目进度更新成功"
    )

@router.post("/{project_id}/members")
async def add_project_members(
    project_id: str,
    member_data: ProjectMemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:edit"))
):
    """添加项目成员"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and project.manager_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限管理此项目成员"
        )
    
    success_count = 0
    failed_items = []
    
    for user_id in member_data.user_ids:
        try:
            # 验证用户是否存在
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                failed_items.append({"user_id": user_id, "error": "用户不存在"})
                continue
            
            # 检查是否已经是项目成员
            existing_result = await db.execute(
                select(project_members).where(
                    and_(
                        project_members.c.project_id == project_id,
                        project_members.c.user_id == user_id
                    )
                )
            )
            if existing_result.first():
                failed_items.append({"user_id": user_id, "error": "已经是项目成员"})
                continue
            
            # 添加成员
            await db.execute(
                project_members.insert().values(
                    project_id=project_id,
                    user_id=user_id,
                    role=member_data.role
                )
            )
            success_count += 1
            
        except Exception as e:
            failed_items.append({"user_id": user_id, "error": str(e)})
    
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"project:{project_id}")
    
    return BaseResponse(
        data={
            "success_count": success_count,
            "failed_count": len(failed_items),
            "failed_items": failed_items
        },
        message=f"成员添加完成，成功{success_count}个，失败{len(failed_items)}个"
    )

@router.delete("/{project_id}/members")
async def remove_project_members(
    project_id: str,
    member_data: ProjectMemberRemove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:edit"))
):
    """移除项目成员"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and project.manager_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限管理此项目成员"
        )
    
    # 移除成员
    await db.execute(
        project_members.delete().where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id.in_(member_data.user_ids)
            )
        )
    )
    
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"project:{project_id}")
    
    return BaseResponse(message="项目成员移除成功")

@router.get("/statistics", response_model=BaseResponse[ProjectStatistics])
async def get_project_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("project:view"))
):
    """获取项目统计信息"""
    # 检查缓存
    cached_stats = await redis_client.get("project_statistics")
    if cached_stats:
        return BaseResponse(
            data=ProjectStatistics(**cached_stats),
            message="获取成功"
        )
    
    # 总项目数
    total_result = await db.execute(select(func.count(Project.id)))
    total = total_result.scalar()
    
    # 按状态统计
    status_counts = {}
    for status in ProjectStatus:
        count_result = await db.execute(
            select(func.count(Project.id)).where(Project.status == status.value)
        )
        status_counts[status.value] = count_result.scalar()
    
    # 按优先级统计
    priority_counts = {}
    for priority in ProjectPriority:
        count_result = await db.execute(
            select(func.count(Project.id)).where(Project.priority == priority.value)
        )
        priority_counts[priority.value] = count_result.scalar()
    
    # 预算统计
    budget_result = await db.execute(
        select(func.sum(Project.budget)).where(Project.budget.isnot(None))
    )
    total_budget = budget_result.scalar() or 0.0
    
    cost_result = await db.execute(
        select(func.sum(Project.actual_cost)).where(Project.actual_cost.isnot(None))
    )
    total_actual_cost = cost_result.scalar() or 0.0
    
    # 平均进度
    progress_result = await db.execute(
        select(func.avg(Project.progress)).where(Project.progress.isnot(None))
    )
    average_progress = progress_result.scalar() or 0.0
    
    # 逾期项目数
    from datetime import datetime
    overdue_result = await db.execute(
        select(func.count(Project.id)).where(
            and_(
                Project.end_date < datetime.now(),
                Project.status.notin_(["completed", "cancelled"])
            )
        )
    )
    overdue_projects = overdue_result.scalar()
    
    stats = ProjectStatistics(
        total=total,
        planning=status_counts.get("planning", 0),
        active=status_counts.get("active", 0),
        completed=status_counts.get("completed", 0),
        cancelled=status_counts.get("cancelled", 0),
        inactive=status_counts.get("inactive", 0),
        by_priority=priority_counts,
        total_budget=total_budget,
        total_actual_cost=total_actual_cost,
        average_progress=round(average_progress, 2),
        overdue_projects=overdue_projects
    )
    
    # 缓存统计数据
    await redis_client.set("project_statistics", stats.dict(), expire=3600)
    
    return BaseResponse(
        data=stats,
        message="获取成功"
    )