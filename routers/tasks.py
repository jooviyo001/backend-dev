from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from datetime import date

from models.database import get_db
from models.models import Task, User, Project, TaskStatus, TaskPriority, TaskType
from schemas.schemas import BaseResponse, PaginationResponse, TaskResponse
from utils.auth import get_current_active_user, require_permission
from utils.response_utils import list_response, paginate_query

router = APIRouter()

@router.get("/page", response_model=BaseResponse)
async def get_tasks_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[TaskStatus] = Query(None, description="任务状态"),
    organization_id: Optional[str] = Query(None, description="组织ID"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    assignee_id: Optional[str] = Query(None, description="执行人ID"),
    reporter_id: Optional[str] = Query(None, description="报告人ID"),
    priority: Optional[TaskPriority] = Query(None, description="任务优先级"),
    type: Optional[TaskType] = Query(None, description="任务类型"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务分页数据"""
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以O开头（组织ID）
        if id_str.startswith('O') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以U开头（用户ID）
        if id_str.startswith('U') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以T开头（任务ID）
        if id_str.startswith('T') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以USER_开头（旧格式）
        if id_str.startswith('USER_'):
            return id_str[5:]
        return id_str
    
    query = db.query(Task)

    if keyword:
        query = query.filter(
            or_(
                Task.title.contains(keyword),
                Task.description.contains(keyword)
            )
        )
    if status:
        query = query.filter(Task.status == status)
    if organization_id:
        org_id = extract_id(organization_id)
        query = query.join(Project).filter(Project.organization_id == org_id)
    if project_id:
        proj_id = extract_id(project_id)
        query = query.filter(Task.project_id == proj_id)
    if assignee_id:
        assignee_id_num = extract_id(assignee_id)
        query = query.filter(Task.assignee_id == assignee_id_num)
    if reporter_id:
        reporter_id_num = extract_id(reporter_id)
        query = query.filter(Task.reporter_id == reporter_id_num)
    if priority:
        query = query.filter(Task.priority == priority)
    if type:
        query = query.filter(Task.type == type)
    if start_date:
        query = query.filter(Task.created_at >= start_date)
    if end_date:
        query = query.filter(Task.created_at <= end_date)

    total, tasks = paginate_query(query, page, size)

    return list_response(
        items=[TaskResponse.from_orm(task) for task in tasks],
        total=total,
        page=page,
        size=size,
        message="获取任务列表成功"
    )