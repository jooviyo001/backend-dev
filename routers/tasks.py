from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date

from models.database import get_db
from models import User, UserRole, Task
from schemas.base import BaseResponse
from schemas.task import TaskResponse, TaskListResponse, TaskUpdate, \
    TaskCreate, TaskBatchStatusUpdate, TaskBatchAssigneeUpdate, TaskBatchDelete, \
    TaskStatusUpdate

from utils.auth import require_permission
from utils.response_utils import list_response, standard_response
from services.task_service import TaskService

router = APIRouter()

@router.get("/list", response_model=BaseResponse)
async def get_tasks_list(
    limit: int = Query(5, ge=1, le=100, description="返回数量限制"),
    status: Optional[str] = Query(None, description="任务状态筛选"),
    priority: Optional[str] = Query(None, description="优先级筛选"),
    project_id: Optional[str] = Query(None, description="项目ID筛选"),
    assignee_id: Optional[str] = Query(None, description="负责人ID筛选"),
    params: Optional[str] = Query(None, description="JSON格式的参数（用于前端兼容）"),
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
    task_service = TaskService(db)
    
    # 构建过滤参数
    filters = {
        "status": status,
        "priority": priority,
        "project_id": project_id,
        "assignee_id": assignee_id,
        "params": params
    }
    
    task_list = task_service.get_tasks_list(
        limit=limit,
        status=status,
        priority=priority,
        project_id=project_id,
        assignee_id=assignee_id,
        current_user=current_user
    )
    
    return standard_response(
        data=task_list,
        message=f"获取任务列表成功，共 {len(task_list)} 条记录"
    )

@router.get("/page", response_model=BaseResponse)
async def get_tasks_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[str] = Query(None, description="任务状态"),
    department_id: Optional[str] = Query(None, description="组织ID"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    assignee_id: Optional[str] = Query(None, description="执行人ID"),
    reporter_id: Optional[str] = Query(None, description="报告人ID"),
    priority: Optional[str] = Query(None, description="任务优先级"),
    type: Optional[str] = Query(None, description="任务类型"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务分页数据"""
    task_service = TaskService(db)
    
    # 构建过滤参数
    filters = {
        "keyword": keyword,
        "status": status,
        "department_id": department_id,
        "project_id": project_id,
        "assignee_id": assignee_id,
        "reporter_id": reporter_id,
        "priority": priority,
        "type": type,
        "start_date": start_date,
        "end_date": end_date
    }
    
    total, tasks = task_service.get_tasks_page(
        current_user=current_user,
        page=page,
        size=size,
        keyword=filters["keyword"],
        status=filters["status"],
        department_id=filters["department_id"],
        project_id=filters["project_id"],
        assignee_id=filters["assignee_id"],
        reporter_id=filters["reporter_id"],
        priority=filters["priority"],
        type=filters["type"],
        start_date=filters["start_date"],
        end_date=filters["end_date"]
    )

    return list_response(
        records=[TaskResponse.model_validate(task, from_attributes=True) for task in tasks],
        total=total,
        page=page,
        size=size,
        message="获取任务列表成功"
    )

@router.post("/create", response_model=BaseResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """创建新任务"""
    task_service = TaskService(db)
    
    try:
        task = task_service.create_task(task_data, current_user)
        
        # 转换为响应模型
        task_response = TaskResponse.model_validate(task)
        
        return standard_response(
            data=task_response,
            message="任务创建成功"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
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
    
    # 查找任务（使用原始task_id，因为数据库中存储的是带前缀的ID）
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限：只有任务创建者、负责人或管理员可以删除任务
    user_is_admin: bool = current_user.role == UserRole.ADMIN  # type: ignore
    user_is_reporter: bool = current_user.id == task.reporter_id  # type: ignore
    user_is_assignee: bool = current_user.id == task.assignee_id  # type: ignore
    if not (user_is_admin or user_is_reporter or user_is_assignee):
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
    # ID格式处理函数,使用原来的ID

    if not task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式"
        )
    
    # 查找任务（使用原始带前缀的task_id）
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限：非管理员只能更新自己相关的任务
    if current_user.role != UserRole.ADMIN:  # type: ignore
        user_is_assignee = current_user.id == task.assignee_id
        user_is_reporter = current_user.id == task.reporter_id
        user_is_project_member = task.project and any(
            member.id == current_user.id for member in task.project.members
        )
        
        if not (user_is_assignee or user_is_reporter or user_is_project_member):  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限更新此任务"
            )
    
    # 更新任务字段
    update_data = task_update.model_dump(exclude_unset=True)
    
    # 处理tags字段，转换为JSON字符串
    if 'tags' in update_data and update_data['tags'] is not None:
        import json
        update_data['tags'] = json.dumps(update_data['tags'], ensure_ascii=False)

    # 处理关联ID字段（保持带前缀的ID格式）
    if 'project_id' in update_data and update_data['project_id']:
        project_id = update_data['project_id']  # 保持原始ID格式
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指定的项目不存在"
            )
        update_data['project_id'] = project_id
    
    if 'assignee_id' in update_data and update_data['assignee_id']:
        assignee_id = update_data['assignee_id']  # 保持原始ID格式
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
        task.updated_at = datetime.now()  # type: ignore
        
        db.commit()
        db.refresh(task)
        
        # 返回更新后的任务信息
        return standard_response(
            data=TaskResponse.model_validate(task),
            message="任务更新成功"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新任务失败: {str(e)}"
        )

@router.get("/{task_id}", response_model=BaseResponse)
async def get_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
):
    """获取任务详情
    
    Args:
        task_id: 任务ID（支持T前缀格式或纯数字）
    
    Returns:
        任务详细信息
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
        # 如果以O开头（组织ID）
        if id_str.startswith('O') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    # 提取任务ID
    extracted_task_id = extract_id(task_id)
    if not extracted_task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式"
        )
    
    # 查找任务，预加载用户关联数据（不包含项目信息）
    task = db.query(Task).options(
        joinedload(Task.assignee),
        joinedload(Task.reporter),
        joinedload(Task.project)
    ).filter(Task.id == task_id).first()  # 修复：使用原始task_id而不是extracted_task_id
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限：非管理员只能查看自己相关的任务
    if current_user.role != UserRole.ADMIN:  # type: ignore
        user_is_assignee = current_user.id == task.assignee_id
        user_is_reporter = current_user.id == task.reporter_id
        user_is_project_member = task.project and any(
            member.id == current_user.id for member in task.project.members
        )
        
        if not (user_is_assignee or user_is_reporter or user_is_project_member):  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限查看此任务"
            )
    
    # 返回任务详情
    task_data = TaskResponse.model_validate(task)
    
    return standard_response(
        data=task_data,
        message="获取任务详情成功"
    )

# 更新任务状态
@router.put("/{task_id}/status", response_model=BaseResponse)
async def update_task_status(
    task_id: str,
    status_update: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """更新任务状态
    
    Args:
        task_id: 任务ID（支持T前缀格式或纯数字）
        status_update: 包含新状态的请求体
    
    Returns:
        更新后的任务信息
    """
    
    # 查找任务
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限：只有任务创建者、负责人或管理员可以更新任务
    user_is_admin = current_user.role == UserRole.ADMIN  # type: ignore
    unauthorized_tasks = []
    
    if not user_is_admin:  # type: ignore
        for task in tasks:  # type: ignore
            user_is_reporter = current_user.id == task.reporter_id
            user_is_assignee = current_user.id == task.assignee_id
            if not (user_is_reporter or user_is_assignee):  # type: ignore
                unauthorized_tasks.append(task.id)
    
    if unauthorized_tasks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限更新以下任务: " + ", ".join(unauthorized_tasks)
        )
    
    # 检查状态是否合法
    if status_update.status not in TaskStatus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务状态"
        )
    
    # 检查状态是否改变
    if status_update.status == task.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务状态未改变"
        )
    
    # 更新任务状态
    task.status = status_update.status  # type: ignore
    task.updated_at = datetime.now()  # type: ignore
    db.commit()
    db.refresh(task)
    
    # 返回更新后的任务信息
    return standard_response(
        data=TaskResponse.model_validate(task),
        message="任务状态更新成功"
    ) 

# 批量更新任务状态
@router.put("/batch/status", response_model=BaseResponse)
async def batch_update_task_status(
    batch_update: TaskBatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """批量更新任务状态
    
    只支持更新为以下状态：
    - todo: 待办
    - in_progress: 进行中  
    - done: 完成
    
    Args:
        batch_update: 批量更新请求，包含任务ID列表和目标状态
    
    Returns:
        更新结果统计
    """
    if not batch_update.task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务ID列表不能为空"
        )
    
    # 查询要更新的任务
    tasks = db.query(Task).filter(Task.id.in_(batch_update.task_ids)).all()
    
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何指定的任务"
        )
    
    # 检查找到的任务数量
    found_task_ids = [task.id for task in tasks]
    missing_task_ids = [task_id for task_id in batch_update.task_ids if task_id not in found_task_ids]
    
    # 检查权限：只有任务创建者、负责人或管理员可以更新任务
    user_is_admin = current_user.role == UserRole.ADMIN
    unauthorized_tasks = []
    
    if not user_is_admin:  # type: ignore
        for task in tasks:
            user_is_reporter = current_user.id == task.reporter_id
            user_is_assignee = current_user.id == task.assignee_id
            if not (user_is_reporter or user_is_assignee): # type: ignore
                unauthorized_tasks.append(task.id)
    
    if unauthorized_tasks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"没有权限更新以下任务: {', '.join(unauthorized_tasks)}"
        )
    
    # 执行批量更新
    try:
        updated_count = 0
        for task in tasks:
            task.status = batch_update.status  # type: ignore
            task.updated_at = datetime.now()  # type: ignore
            updated_count += 1
        
        db.commit()
        
        # 构建响应数据
        result = {
            "updated_count": updated_count,
            "total_requested": len(batch_update.task_ids),
            "updated_task_ids": found_task_ids,
            "target_status": batch_update.status.value,
            "missing_task_ids": missing_task_ids if missing_task_ids else '无'
        }
        
        message = f"成功更新 {updated_count} 个任务状态为 {batch_update.status.value}"
        if missing_task_ids:
            message += f"，{len(missing_task_ids)} 个任务未找到"
        
        return standard_response(
            data=result,
            message=message
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量更新任务状态失败: {str(e)}"
        )

# 批量分配任务
@router.put("/batch-assign", response_model=BaseResponse)
async def batch_update_task_assignee(
    batch_update: TaskBatchAssigneeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    
    """批量分配任务"""
    # 检查权限：只有任务创建者、负责人或管理员可以分配任务
    user_is_admin = current_user.role == UserRole.ADMIN  # type: ignore
    unauthorized_tasks = []
    if not user_is_admin:  # type: ignore
        for task_id in batch_update.task_ids:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                continue
            user_is_reporter = current_user.id == task.reporter_id
            user_is_assignee = current_user.id == task.assignee_id
            if not (user_is_reporter or user_is_assignee):  # type: ignore
                unauthorized_tasks.append(task_id)
    if unauthorized_tasks:  
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限分配以下任务: " + ", ".join(unauthorized_tasks)
        )
    if not batch_update.assignee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分配者ID不能为空"
        )
    # 检查分配者是否存在
    assignee = db.query(User).filter(User.id == batch_update.assignee_id).first()
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分配者不存在"
        )
    # 检查任务是否存在
    tasks = db.query(Task).filter(Task.id.in_(batch_update.task_ids)).all()
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何指定的任务"
        )
    # 检查任务是否已分配
    assigned_task_ids = [str(task.id) for task in tasks if task.assignee_id]  # type: ignore
    if assigned_task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下任务已分配，不能重复分配: {', '.join(assigned_task_ids)}"
        )
    # 检查任务是否已完成
    completed_task_ids = [str(task.id) for task in tasks if task.status == TaskStatus.DONE]  # type: ignore
    if completed_task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下任务已完成，不能分配: {', '.join(completed_task_ids)}"
        )
    # 检查任务是否已取消
    cancelled_task_ids = [str(task.id) for task in tasks if task.status == TaskStatus.CANCELLED]  # type: ignore
    if cancelled_task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下任务已取消，不能分配: {', '.join(cancelled_task_ids)}"
        )
    # 执行批量分配
    try:
        updated_count = 0
        for task in tasks:
            task.assignee_id = batch_update.assignee_id  # type: ignore
            task.updated_at = datetime.now()  # type: ignore
            updated_count += 1
        db.commit()
        return standard_response(
            data={
                "updated_count": updated_count,
                "total_requested": len(batch_update.task_ids),
                "updated_task_ids": [task.id for task in tasks],
                "assignee_id": batch_update.assignee_id
            },
            message="批量分配任务成功"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量分配任务失败: {str(e)}"
        )
    finally:
        db.close()

# 批量删除
@router.delete("/batch-delete", response_model=BaseResponse)
async def batch_delete_tasks(
    batch_delete: TaskBatchDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:write"))
):
    """批量删除任务"""
    # 检查权限：只有任务创建者、负责人或管理员可以删除任务
    user_is_admin = current_user.role == UserRole.ADMIN  # type: ignore
    unauthorized_tasks = []
    if not user_is_admin:  # type: ignore
        for task_id in batch_delete.task_ids:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                continue
            user_is_reporter = current_user.id == task.reporter_id
            user_is_assignee = current_user.id == task.assignee_id
            if not (user_is_reporter or user_is_assignee):  # type: ignore
                unauthorized_tasks.append(task_id)
    if unauthorized_tasks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除以下任务: " + ", ".join(unauthorized_tasks)
        )
    # 检查任务是否存在
    tasks = db.query(Task).filter(Task.id.in_(batch_delete.task_ids)).all()
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何指定的任务"
        )
    # 检查任务是否已完成
    completed_task_ids = [str(task.id) for task in tasks if task.status == TaskStatus.DONE]  # type: ignore
    if completed_task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下任务已完成，不能删除: {', '.join(completed_task_ids)}"
        )
    # 检查任务是否已取消
    cancelled_task_ids = [str(task.id) for task in tasks if task.status == TaskStatus.CANCELLED]  # type: ignore
    if cancelled_task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下任务已取消，不能删除: {', '.join(cancelled_task_ids)}"
        )
    # 执行批量删除
    try:
        deleted_task_ids = [task.id for task in tasks]
        for task in tasks:
            db.delete(task)
        db.commit()
        return standard_response(
            data={
                "deleted_count": len(tasks),
                "total_requested": len(batch_delete.task_ids),
                "deleted_task_ids": deleted_task_ids
            },
            message="批量删除任务成功"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除任务失败: {str(e)}"
        )
    finally:
        db.close()










































































































