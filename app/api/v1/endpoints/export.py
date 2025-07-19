from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import csv
import io
import json
import uuid
import os
from pathlib import Path

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.organization import Organization
from app.models.file import File
from app.schemas.base import BaseResponse

router = APIRouter()

# 导出相关的 Pydantic 模式
from pydantic import BaseModel, Field
from enum import Enum

class ExportFormat(str, Enum):
    """导出格式"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"

class ExportType(str, Enum):
    """导出类型"""
    PROJECTS = "projects"
    TASKS = "tasks"
    USERS = "users"
    ORGANIZATIONS = "organizations"
    FILES = "files"

class ExportRequest(BaseModel):
    """导出请求"""
    export_type: ExportType
    format: ExportFormat = ExportFormat.CSV
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="过滤条件")
    fields: Optional[List[str]] = Field(None, description="导出字段，为空则导出所有字段")
    date_from: Optional[datetime] = Field(None, description="开始日期")
    date_to: Optional[datetime] = Field(None, description="结束日期")

class ExportTask(BaseModel):
    """导出任务"""
    id: str
    export_type: ExportType
    format: ExportFormat
    status: str = Field(..., description="状态：pending, processing, completed, failed")
    progress: int = Field(0, ge=0, le=100, description="进度百分比")
    file_url: Optional[str] = Field(None, description="下载链接")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime
    expires_at: datetime

class ExportTaskResponse(BaseModel):
    """导出任务响应"""
    task_id: str
    message: str
    estimated_time: int = Field(..., description="预估完成时间（秒）")

# 导出文件存储目录
EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

@router.post("/", response_model=BaseResponse[ExportTaskResponse])
async def create_export_task(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("export:create"))
):
    """创建导出任务"""
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 预估完成时间（基于数据量）
    estimated_time = await estimate_export_time(export_request, db, current_user)
    
    # 创建导出任务记录
    export_task = ExportTask(
        id=task_id,
        export_type=export_request.export_type,
        format=export_request.format,
        status="pending",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24)  # 24小时后过期
    )
    
    # 存储到 Redis
    await redis_client.set(
        f"export_task:{task_id}", 
        export_task.dict(), 
        expire=86400  # 24小时
    )
    
    # 添加后台任务
    background_tasks.add_task(
        process_export_task, 
        task_id, 
        export_request, 
        current_user.id
    )
    
    return BaseResponse(
        data=ExportTaskResponse(
            task_id=task_id,
            message="导出任务已创建，正在处理中",
            estimated_time=estimated_time
        ),
        message="导出任务创建成功"
    )

@router.get("/tasks/{task_id}", response_model=BaseResponse[ExportTask])
async def get_export_task(
    task_id: str,
    current_user: User = Depends(check_permission("export:view"))
):
    """获取导出任务状态"""
    task_data = await redis_client.get(f"export_task:{task_id}")
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="导出任务不存在或已过期"
        )
    
    export_task = ExportTask(**task_data)
    
    return BaseResponse(
        data=export_task,
        message="获取成功"
    )

@router.get("/tasks", response_model=BaseResponse[List[ExportTask]])
async def get_export_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: User = Depends(check_permission("export:list"))
):
    """获取导出任务列表"""
    # 从 Redis 获取用户的导出任务
    pattern = f"export_task:*"
    keys = await redis_client.keys(pattern)
    
    tasks = []
    for key in keys:
        task_data = await redis_client.get(key)
        if task_data:
            tasks.append(ExportTask(**task_data))
    
    # 按创建时间排序
    tasks.sort(key=lambda x: x.created_at, reverse=True)
    
    # 分页
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_tasks = tasks[start_idx:end_idx]
    
    return BaseResponse(
        data=paginated_tasks,
        message="获取成功"
    )

@router.get("/download/{task_id}")
async def download_export_file(
    task_id: str,
    current_user: User = Depends(check_permission("export:download"))
):
    """下载导出文件"""
    task_data = await redis_client.get(f"export_task:{task_id}")
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="导出任务不存在或已过期"
        )
    
    export_task = ExportTask(**task_data)
    
    if export_task.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="导出任务尚未完成"
        )
    
    if not export_task.file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="导出文件不存在"
        )
    
    file_path = EXPORT_DIR / export_task.file_url
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="导出文件不存在"
        )
    
    # 确定文件类型和媒体类型
    media_type = {
        ExportFormat.CSV: "text/csv",
        ExportFormat.JSON: "application/json",
        ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }.get(export_task.format, "application/octet-stream")
    
    filename = f"{export_task.export_type}_{export_task.id}.{export_task.format}"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@router.delete("/tasks/{task_id}", response_model=BaseResponse[None])
async def delete_export_task(
    task_id: str,
    current_user: User = Depends(check_permission("export:delete"))
):
    """删除导出任务"""
    task_data = await redis_client.get(f"export_task:{task_id}")
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="导出任务不存在"
        )
    
    export_task = ExportTask(**task_data)
    
    # 删除文件
    if export_task.file_url:
        file_path = EXPORT_DIR / export_task.file_url
        if file_path.exists():
            file_path.unlink()
    
    # 删除 Redis 记录
    await redis_client.delete(f"export_task:{task_id}")
    
    return BaseResponse(
        data=None,
        message="导出任务删除成功"
    )

@router.get("/quick/{export_type}")
async def quick_export(
    export_type: ExportType,
    format: ExportFormat = Query(ExportFormat.CSV, description="导出格式"),
    limit: int = Query(1000, ge=1, le=10000, description="导出数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("export:quick"))
):
    """快速导出（小数据量，直接返回文件流）"""
    # 获取数据
    data = await get_export_data(
        ExportRequest(
            export_type=export_type,
            format=format,
            filters={"limit": limit}
        ),
        db,
        current_user
    )
    
    if format == ExportFormat.CSV:
        return await export_to_csv_stream(data, export_type)
    elif format == ExportFormat.JSON:
        return await export_to_json_stream(data)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="快速导出不支持 Excel 格式"
        )

# 辅助函数
async def estimate_export_time(export_request: ExportRequest, db: AsyncSession, current_user: User) -> int:
    """预估导出时间"""
    # 获取数据量
    count = await get_data_count(export_request, db, current_user)
    
    # 基于数据量预估时间（秒）
    if count <= 1000:
        return 10
    elif count <= 10000:
        return 30
    elif count <= 100000:
        return 120
    else:
        return 300

async def get_data_count(export_request: ExportRequest, db: AsyncSession, current_user: User) -> int:
    """获取数据数量"""
    if export_request.export_type == ExportType.PROJECTS:
        query = select(func.count(Project.id))
        if current_user.role not in ["admin", "manager"]:
            query = query.where(
                or_(
                    Project.manager_id == current_user.id,
                    Project.members.any(User.id == current_user.id)
                )
            )
    elif export_request.export_type == ExportType.TASKS:
        query = select(func.count(Task.id))
        if current_user.role not in ["admin", "manager"]:
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
    elif export_request.export_type == ExportType.USERS:
        if current_user.role not in ["admin", "manager"]:
            return 0
        query = select(func.count(User.id))
    elif export_request.export_type == ExportType.ORGANIZATIONS:
        query = select(func.count(Organization.id))
        if current_user.role not in ["admin", "manager"]:
            query = query.where(Organization.members.any(User.id == current_user.id))
    elif export_request.export_type == ExportType.FILES:
        query = select(func.count(File.id))
        if current_user.role not in ["admin", "manager"]:
            query = query.where(File.uploader_id == current_user.id)
    else:
        return 0
    
    result = await db.execute(query)
    return result.scalar() or 0

async def process_export_task(task_id: str, export_request: ExportRequest, user_id: str):
    """处理导出任务（后台任务）"""
    try:
        # 更新任务状态
        await update_export_task_status(task_id, "processing", progress=0)
        
        # 获取数据库连接
        from app.core.database import async_session
        async with async_session() as db:
            # 获取用户信息
            user_result = await db.execute(select(User).where(User.id == user_id))
            current_user = user_result.scalar_one_or_none()
            if not current_user:
                raise Exception("用户不存在")
            
            # 获取数据
            await update_export_task_status(task_id, "processing", progress=20)
            data = await get_export_data(export_request, db, current_user)
            
            # 生成文件
            await update_export_task_status(task_id, "processing", progress=60)
            filename = await generate_export_file(task_id, export_request, data)
            
            # 完成任务
            await update_export_task_status(
                task_id, 
                "completed", 
                progress=100, 
                file_url=filename
            )
            
    except Exception as e:
        await update_export_task_status(
            task_id, 
            "failed", 
            error_message=str(e)
        )

async def update_export_task_status(
    task_id: str, 
    status: str, 
    progress: int = None, 
    file_url: str = None, 
    error_message: str = None
):
    """更新导出任务状态"""
    task_data = await redis_client.get(f"export_task:{task_id}")
    if task_data:
        export_task = ExportTask(**task_data)
        export_task.status = status
        if progress is not None:
            export_task.progress = progress
        if file_url:
            export_task.file_url = file_url
        if error_message:
            export_task.error_message = error_message
        
        await redis_client.set(
            f"export_task:{task_id}", 
            export_task.dict(), 
            expire=86400
        )

async def get_export_data(export_request: ExportRequest, db: AsyncSession, current_user: User) -> List[Dict]:
    """获取导出数据"""
    if export_request.export_type == ExportType.PROJECTS:
        return await get_projects_data(export_request, db, current_user)
    elif export_request.export_type == ExportType.TASKS:
        return await get_tasks_data(export_request, db, current_user)
    elif export_request.export_type == ExportType.USERS:
        return await get_users_data(export_request, db, current_user)
    elif export_request.export_type == ExportType.ORGANIZATIONS:
        return await get_organizations_data(export_request, db, current_user)
    elif export_request.export_type == ExportType.FILES:
        return await get_files_data(export_request, db, current_user)
    else:
        return []

async def get_projects_data(export_request: ExportRequest, db: AsyncSession, current_user: User) -> List[Dict]:
    """获取项目数据"""
    query = select(Project)
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        query = query.where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
    
    # 应用过滤条件
    query = apply_filters(query, export_request.filters, Project)
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    data = []
    for project in projects:
        data.append({
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "priority": project.priority,
            "progress": project.progress,
            "budget": float(project.budget) if project.budget else None,
            "actual_cost": float(project.actual_cost) if project.actual_cost else None,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "manager_id": project.manager_id,
            "organization_id": project.organization_id,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat()
        })
    
    return data

async def get_tasks_data(export_request: ExportRequest, db: AsyncSession, current_user: User) -> List[Dict]:
    """获取任务数据"""
    query = select(Task)
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
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
    
    # 应用过滤条件
    query = apply_filters(query, export_request.filters, Task)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    data = []
    for task in tasks:
        data.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "type": task.type,
            "estimated_hours": float(task.estimated_hours) if task.estimated_hours else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "start_date": task.start_date.isoformat() if task.start_date else None,
            "completed_date": task.completed_date.isoformat() if task.completed_date else None,
            "project_id": task.project_id,
            "assignee_id": task.assignee_id,
            "reporter_id": task.reporter_id,
            "parent_task_id": task.parent_task_id,
            "tags": task.tags,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        })
    
    return data

async def get_users_data(export_request: ExportRequest, db: AsyncSession, current_user: User) -> List[Dict]:
    """获取用户数据"""
    if current_user.role not in ["admin", "manager"]:
        return []
    
    query = select(User)
    
    # 应用过滤条件
    query = apply_filters(query, export_request.filters, User)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    data = []
    for user in users:
        data.append({
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "department": user.department,
            "phone": user.phone,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat()
        })
    
    return data

async def get_organizations_data(export_request: ExportRequest, db: AsyncSession, current_user: User) -> List[Dict]:
    """获取组织数据"""
    query = select(Organization)
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Organization.members.any(User.id == current_user.id))
    
    # 应用过滤条件
    query = apply_filters(query, export_request.filters, Organization)
    
    result = await db.execute(query)
    organizations = result.scalars().all()
    
    data = []
    for org in organizations:
        data.append({
            "id": org.id,
            "name": org.name,
            "description": org.description,
            "type": org.type,
            "parent_id": org.parent_id,
            "email": org.email,
            "phone": org.phone,
            "address": org.address,
            "created_at": org.created_at.isoformat(),
            "updated_at": org.updated_at.isoformat()
        })
    
    return data

async def get_files_data(export_request: ExportRequest, db: AsyncSession, current_user: User) -> List[Dict]:
    """获取文件数据"""
    query = select(File)
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        query = query.where(File.uploader_id == current_user.id)
    
    # 应用过滤条件
    query = apply_filters(query, export_request.filters, File)
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    data = []
    for file in files:
        data.append({
            "id": file.id,
            "filename": file.filename,
            "original_filename": file.original_filename,
            "file_path": file.file_path,
            "file_url": file.file_url,
            "file_size": file.file_size,
            "file_type": file.file_type,
            "file_extension": file.file_extension,
            "entity_type": file.entity_type,
            "entity_id": file.entity_id,
            "uploader_id": file.uploader_id,
            "created_at": file.created_at.isoformat(),
            "updated_at": file.updated_at.isoformat()
        })
    
    return data

def apply_filters(query, filters: Dict, model):
    """应用过滤条件"""
    if not filters:
        return query
    
    for key, value in filters.items():
        if key == "limit" and isinstance(value, int):
            query = query.limit(value)
        elif hasattr(model, key) and value is not None:
            if isinstance(value, list):
                query = query.where(getattr(model, key).in_(value))
            else:
                query = query.where(getattr(model, key) == value)
    
    return query

async def generate_export_file(task_id: str, export_request: ExportRequest, data: List[Dict]) -> str:
    """生成导出文件"""
    filename = f"{task_id}.{export_request.format}"
    file_path = EXPORT_DIR / filename
    
    if export_request.format == ExportFormat.CSV:
        await generate_csv_file(file_path, data)
    elif export_request.format == ExportFormat.JSON:
        await generate_json_file(file_path, data)
    elif export_request.format == ExportFormat.EXCEL:
        await generate_excel_file(file_path, data)
    
    return filename

async def generate_csv_file(file_path: Path, data: List[Dict]):
    """生成 CSV 文件"""
    if not data:
        return
    
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)

async def generate_json_file(file_path: Path, data: List[Dict]):
    """生成 JSON 文件"""
    with open(file_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)

async def generate_excel_file(file_path: Path, data: List[Dict]):
    """生成 Excel 文件"""
    try:
        import pandas as pd
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False, engine='openpyxl')
    except ImportError:
        raise Exception("需要安装 pandas 和 openpyxl 库才能导出 Excel 文件")

async def export_to_csv_stream(data: List[Dict], export_type: ExportType) -> StreamingResponse:
    """导出为 CSV 流"""
    if not data:
        data = []
    
    output = io.StringIO()
    if data:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    
    output.seek(0)
    
    def iter_csv():
        yield output.getvalue().encode('utf-8')
    
    filename = f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

async def export_to_json_stream(data: List[Dict]) -> StreamingResponse:
    """导出为 JSON 流"""
    def iter_json():
        yield json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return StreamingResponse(
        iter_json(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )