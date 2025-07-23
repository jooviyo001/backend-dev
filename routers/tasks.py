from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import Optional, List
from math import ceil
from datetime import datetime
import json
import os
import uuid

from models.database import get_db
from models.models import Task, User, Project, TaskAttachment, TaskComment
from schemas.schemas import (
    TaskCreate, TaskUpdate, TaskResponse, BaseResponse, PaginationResponse,
    TaskStatistics, BatchDeleteRequest, BatchAssignRequest,
    AttachmentResponse, CommentCreate, CommentResponse
)
from utils.auth import (
    get_current_active_user, require_permission
)

router = APIRouter()

# 任务列表
@router.get("/list", response_model=BaseResponse)
async def get_tasks(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[str] = Query(None, description="任务状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    type: Optional[str] = Query(None, description="任务类型"),
    project_id: Optional[int] = Query(None, description="项目ID"),
    assignee_id: Optional[int] = Query(None, description="分配人ID"),
    reporter_id: Optional[int] = Query(None, description="报告人ID"),
    tags: Optional[str] = Query(None, description="标签"),
    due_date_from: Optional[datetime] = Query(None, description="截止日期范围开始"),
    due_date_to: Optional[datetime] = Query(None, description="截止日期范围结束"),
    created_at_from: Optional[datetime] = Query(None, description="创建时间范围开始"),
    created_at_to: Optional[datetime] = Query(None, description="创建时间范围结束"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务列表"""
    from utils.response_utils import list_response, paginate_query
    
    query = db.query(Task)
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Task.title.contains(keyword),
                Task.description.contains(keyword)
            )
        )
    
    # 状态过滤
    if status:
        query = query.filter(Task.status == status)
    
    # 优先级过滤
    if priority:
        query = query.filter(Task.priority == priority)
    
    # 类型过滤
    if type:
        query = query.filter(Task.type == type)
    
    # 项目过滤
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    # 分配人过滤
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    
    # 报告人过滤
    if reporter_id:
        query = query.filter(Task.reporter_id == reporter_id)
    
    # 标签过滤
    if tags:
        query = query.filter(Task.tags.contains(tags))
    
    # 截止日期范围过滤
    if due_date_from:
        query = query.filter(Task.due_date >= due_date_from)
    if due_date_to:
        query = query.filter(Task.due_date <= due_date_to)
    
    # 创建时间范围过滤
    if created_at_from:
        query = query.filter(Task.created_at >= created_at_from)
    if created_at_to:
        query = query.filter(Task.created_at <= created_at_to)
    
    # 分页
    total, tasks = paginate_query(query, page, size)
    
    return list_response(
        items=[TaskResponse.from_orm(task) for task in tasks],
        total=total,
        page=page,
        size=size,
        message="获取任务列表成功"
    )

# 任务分列表
@router.get("/page", response_model=BaseResponse)
async def get_tasks_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[str] = Query(None, description="任务状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    project_id: Optional[int] = Query(None, description="项目ID"),
    assignee_id: Optional[int] = Query(None, description="分配人ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务分页数据"""
    return await get_tasks(
        keyword, status, priority, None, project_id, assignee_id, None, None,
        None, None, None, None, page, size, db, current_user
    )


@router.get("/my", response_model=BaseResponse)
async def get_my_tasks(
    status: Optional[str] = Query(None, description="任务状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    project_id: Optional[int] = Query(None, description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的任务"""
    from utils.response_utils import list_response
    
    query = db.query(Task).filter(Task.assignee_id == current_user.id)
    
    # 状态过滤
    if status:
        query = query.filter(Task.status == status)
    
    # 优先级过滤
    if priority:
        query = query.filter(Task.priority == priority)
    
    # 项目过滤
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    tasks = query.all()
    
    return list_response(
        items=[TaskResponse.from_orm(task) for task in tasks],
        message="获取我的任务成功"
    )

@router.get("/statistics", response_model=BaseResponse)
async def get_task_statistics(
    project_id: Optional[int] = Query(None, description="项目ID"),
    assignee_id: Optional[int] = Query(None, description="分配人ID"),
    date_from: Optional[datetime] = Query(None, description="日期范围开始"),
    date_to: Optional[datetime] = Query(None, description="日期范围结束"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务统计信息"""
    query = db.query(Task)
    
    # 项目过滤
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    # 分配人过滤
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    
    # 日期范围过滤
    if date_from:
        query = query.filter(Task.created_at >= date_from)
    if date_to:
        query = query.filter(Task.created_at <= date_to)
    
    # 统计各状态任务数量
    total = query.count()
    todo = query.filter(Task.status == "todo").count()
    in_progress = query.filter(Task.status == "in_progress").count()
    review = query.filter(Task.status == "review").count()
    done = query.filter(Task.status == "done").count()
    cancelled = query.filter(Task.status == "cancelled").count()
    
    # 统计逾期任务
    overdue = query.filter(
        and_(
            Task.due_date < datetime.now(),
            Task.status.notin_(["done", "cancelled"])
        )
    ).count()
    
    statistics = TaskStatistics(
        total=total,
        todo=todo,
        in_progress=in_progress,
        review=review,
        done=done,
        cancelled=cancelled,
        overdue=overdue
    )
    
    return BaseResponse(
        message="获取任务统计成功",
        data=statistics
    )

@router.get("/{task_id}", response_model=BaseResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务详情"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    return BaseResponse(
        message="获取任务详情成功",
        data=TaskResponse.from_orm(task)
    )

@router.post("/create", response_model=BaseResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """创建任务"""
    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == task_data.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查分配人是否存在
    if task_data.assignee_id:
        assignee = db.query(User).filter(User.id == task_data.assignee_id).first()
        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分配人不存在"
            )
    
    # 创建新任务
    tags_json = json.dumps(task_data.tags) if task_data.tags else None
    db_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        type=task_data.type,
        project_id=task_data.project_id,
        assignee_id=task_data.assignee_id,
        reporter_id=current_user.id,
        due_date=task_data.due_date,
        estimated_hours=task_data.estimated_hours,
        tags=tags_json
    )
    
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return BaseResponse(
        message="创建任务成功",
        data=TaskResponse.from_orm(db_task)
    )

@router.put("/{task_id}", response_model=BaseResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """更新任务信息"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 更新任务信息
    update_data = task_data.dict(exclude_unset=True)
    
    # 处理标签
    if 'tags' in update_data and update_data['tags'] is not None:
        update_data['tags'] = json.dumps(update_data['tags'])
    
    for field, value in update_data.items():
        setattr(task, field, value)
    
    db.commit()
    db.refresh(task)
    
    return BaseResponse(
        message="更新任务信息成功",
        data=TaskResponse.from_orm(task)
    )

@router.delete("/{task_id}", response_model=BaseResponse)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """删除任务"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    db.delete(task)
    db.commit()
    
    return BaseResponse(message="删除任务成功")

@router.post("/batch-delete", response_model=BaseResponse)
async def batch_delete_tasks(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """批量删除任务"""
    tasks = db.query(Task).filter(Task.id.in_(request.ids)).all()
    
    for task in tasks:
        db.delete(task)
    
    db.commit()
    
    return BaseResponse(message=f"成功删除 {len(tasks)} 个任务")

@router.post("/batch-assign", response_model=BaseResponse)
async def batch_assign_tasks(
    request: BatchAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """批量分配任务"""
    # 检查分配人是否存在
    assignee = db.query(User).filter(User.id == request.assignee_id).first()
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分配人不存在"
        )
    
    tasks = db.query(Task).filter(Task.id.in_(request.task_ids)).all()
    
    for task in tasks:
        task.assignee_id = request.assignee_id
    
    db.commit()
    
    return BaseResponse(message=f"成功分配 {len(tasks)} 个任务")

# 任务附件相关接口
@router.get("/{task_id}/attachments", response_model=BaseResponse)
async def get_task_attachments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务附件列表"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    attachments = db.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).all()
    
    return BaseResponse(
        message="获取任务附件成功",
        data=[AttachmentResponse.from_orm(attachment) for attachment in attachments]
    )

@router.post("/{task_id}/attachments", response_model=BaseResponse)
async def upload_task_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """上传任务附件"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 创建上传目录
    upload_dir = "uploads/attachments"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # 创建附件记录
    attachment = TaskAttachment(
        task_id=task_id,
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        content_type=file.content_type,
        uploaded_by=current_user.id
    )
    
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return BaseResponse(
        message="上传附件成功",
        data=AttachmentResponse.from_orm(attachment)
    )

# 任务评论相关接口
@router.get("/{task_id}/comments", response_model=BaseResponse)
async def get_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务评论列表"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    comments = db.query(TaskComment).filter(TaskComment.task_id == task_id).all()
    
    return BaseResponse(
        message="获取任务评论成功",
        data=[CommentResponse.from_orm(comment) for comment in comments]
    )

@router.post("/{task_id}/comments", response_model=BaseResponse)
async def create_task_comment(
    task_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """创建任务评论"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    comment = TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        content=comment_data.content
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return BaseResponse(
        message="创建评论成功",
        data=CommentResponse.from_orm(comment)
    )