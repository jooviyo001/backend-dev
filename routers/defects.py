from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc, or_
from typing import Optional, List
from datetime import date, datetime

from models.database import get_db
from models.models import Task, User, Project, TaskStatus, TaskPriority, TaskType
from schemas.schemas import BaseResponse, PaginationResponse, TaskResponse
from utils.auth import get_current_active_user, require_permission
from utils.response_utils import list_response, paginate_query, standard_response

router = APIRouter()

@router.get("/page", response_model=BaseResponse)
async def get_defects_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[TaskStatus] = Query(None, description="缺陷状态"),
    organization_id: Optional[str] = Query(None, description="组织ID"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    assignee_id: Optional[str] = Query(None, description="执行人ID"),
    reporter_id: Optional[str] = Query(None, description="报告人ID"),
    priority: Optional[TaskPriority] = Query(None, description="缺陷优先级"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取缺陷分页数据
    
    该接口专门用于查询类型为BUG的任务（缺陷），支持多种筛选条件：
    - 关键词搜索（标题和描述）
    - 状态筛选
    - 组织、项目、执行人、报告人筛选
    - 优先级筛选
    - 日期范围筛选
    """
    # 使用joinedload预加载用户数据和项目数据
    query = db.query(Task).options(
        joinedload(Task.assignee),  # 预加载负责人信息
        joinedload(Task.reporter),  # 预加载报告人信息
        joinedload(Task.project)    # 预加载项目信息
    ).filter(Task.type == TaskType.BUG)  # 只查询缺陷类型的任务

    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Task.title.contains(keyword),
                Task.description.contains(keyword)
            )
        )
    
    # 状态筛选
    if status:
        query = query.filter(Task.status == status)
    
    # 组织筛选
    if organization_id:
        query = query.join(Project).filter(Project.organization_id == organization_id)
    
    # 项目筛选
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    # 执行人筛选
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    
    # 报告人筛选
    if reporter_id:
        query = query.filter(Task.reporter_id == reporter_id)
    
    # 优先级筛选
    if priority:
        query = query.filter(Task.priority == priority)
    
    # 日期范围筛选
    if start_date:
        query = query.filter(Task.created_at >= start_date)
    if end_date:
        query = query.filter(Task.created_at <= end_date)

    # 按创建时间倒序排列
    query = query.order_by(desc(Task.created_at))

    # 分页查询
    total, defects = paginate_query(query, page, size)

    return list_response(
        records=[TaskResponse.model_validate(defect, from_attributes=True) for defect in defects],
        total=total,
        page=page,
        size=size,
        message="获取缺陷列表成功"
    )