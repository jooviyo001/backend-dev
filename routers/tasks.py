from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from typing import Optional, List
from datetime import date, datetime

from models.database import get_db
from models.models import Task, User, Project, TaskStatus, TaskPriority, TaskType
from schemas.schemas import BaseResponse, PaginationResponse, TaskResponse, TaskListResponse, TaskUpdate
from utils.auth import get_current_active_user, require_permission
from utils.response_utils import list_response, paginate_query, standard_response

router = APIRouter()

@router.get("/list", response_model=BaseResponse)
async def get_tasks_list(
    limit: int = Query(5, ge=1, le=100, description="返回数量限制"),
    status: Optional[TaskStatus] = Query(None, description="任务状态筛选"),
    priority: Optional[TaskPriority] = Query(None, description="优先级筛选"),
    project_id: Optional[str] = Query(None, description="项目ID筛选"),
    assignee_id: Optional[str] = Query(None, description="负责人ID筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务列表（倒序查询最新任务）
    
    返回字段：
    - 任务ID
    - 任务标题
    - 所属项目
    - 负责人
    - 优先级
    - 状态
    - 截止日期
    - 创建日期
    - 更新时间
    """
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
    
    # 构建查询，使用joinedload预加载关联数据
    query = db.query(Task).options(
        joinedload(Task.project),
        joinedload(Task.assignee)
    )
    
    # 应用筛选条件
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if project_id:
        proj_id = extract_id(project_id)
        query = query.filter(Task.project_id == proj_id)
    if assignee_id:
        assignee_id_num = extract_id(assignee_id)
        query = query.filter(Task.assignee_id == assignee_id_num)
    
    # 按创建时间倒序排列，获取最新的任务
    tasks = query.order_by(desc(Task.created_at)).limit(limit).all()
    
    # 构建响应数据
    task_list = []
    for task in tasks:
        task_data = {
            "id": task.id,
            "title": task.title,
            "project_name": task.project.name if task.project else None,
            "assignee_name": task.assignee.username if task.assignee else None,
            "priority": task.priority,
            "status": task.status,
            "due_date": task.due_date,
            "created_at": task.created_at,
            "updated_at": task.updated_at
        }
        task_list.append(TaskListResponse(**task_data))
    
    return standard_response(
        data=task_list,
        message=f"获取任务列表成功，共 {len(task_list)} 条记录"
    )

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
        records=[TaskResponse.model_validate(task, from_attributes=True) for task in tasks],
        total=total,
        page=page,
        size=size,
        message="获取任务列表成功"
    )

@router.delete("/{task_id}", response_model=BaseResponse)
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:delete"))
):
    """删除任务
    
    Args:
        task_id: 任务ID（支持T前缀格式或纯数字）
    
    Returns:
        删除结果
    """
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以T开头（任务ID）
        if id_str.startswith('T') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    # 提取任务ID
    extracted_task_id = extract_id(task_id)
    if not extracted_task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式"
        )
    
    # 查找任务
    task = db.query(Task).filter(Task.id == extracted_task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限：只有任务创建者、负责人或管理员可以删除任务
    if (current_user.role != "admin" and 
        current_user.id != task.reporter_id and 
        current_user.id != task.assignee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除此任务"
        )
    
    # 删除任务
    try:
        db.delete(task)
        db.commit()
        
        return standard_response(
            data={"task_id": task_id},
            message="任务删除成功"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败: {str(e)}"
        )

@router.put("/{task_id}", response_model=BaseResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:update"))
):
    """更新任务信息
    
    Args:
        task_id: 任务ID（支持T前缀格式或纯数字）
        task_update: 任务更新数据
    
    Returns:
        更新后的任务信息
    """
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以T开头（任务ID）
        if id_str.startswith('T') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以U开头（用户ID）
        if id_str.startswith('U') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    # 提取任务ID
    extracted_task_id = extract_id(task_id)
    if not extracted_task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式"
        )
    
    # 查找任务
    task = db.query(Task).filter(Task.id == extracted_task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限：只有任务创建者、负责人或管理员可以更新任务
    if (current_user.role != "admin" and 
        current_user.id != task.reporter_id and 
        current_user.id != task.assignee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限更新此任务"
        )
    
    # 更新任务字段
    update_data = task_update.dict(exclude_unset=True)
    
    # 处理关联ID字段
    if 'project_id' in update_data and update_data['project_id']:
        project_id = extract_id(update_data['project_id'])
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指定的项目不存在"
            )
        update_data['project_id'] = project_id
    
    if 'assignee_id' in update_data and update_data['assignee_id']:
        assignee_id = extract_id(update_data['assignee_id'])
        # 验证用户是否存在
        assignee = db.query(User).filter(User.id == assignee_id).first()
        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指定的负责人不存在"
            )
        update_data['assignee_id'] = assignee_id
    
    # 更新任务
    try:
        for field, value in update_data.items():
            setattr(task, field, value)
        
        # 更新时间戳
        task.updated_at = datetime.now()
        
        db.commit()
        db.refresh(task)
        
        # 返回更新后的任务信息
        return standard_response(
            data=TaskResponse.from_orm(task),
            message="任务更新成功"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新任务失败: {str(e)}"
        )