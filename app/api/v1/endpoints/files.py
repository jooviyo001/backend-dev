from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import os
import uuid
import aiofiles
from datetime import datetime
from typing import List, Optional
import mimetypes

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.config import settings
from app.models.user import User
from app.models.file import File as FileModel
from app.schemas.base import BaseResponse, PaginationParams, PaginationResponse

router = APIRouter()

# 文件相关的 Pydantic 模式
from pydantic import BaseModel, Field

class FileResponse(BaseModel):
    """文件响应模式"""
    id: str
    filename: str
    original_filename: str
    file_path: str
    file_url: str
    file_size: int
    file_type: str
    file_extension: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    uploader_id: str
    uploader_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class FileSearchParams(BaseModel):
    """文件搜索参数"""
    keyword: Optional[str] = Field(None, description="搜索关键词")
    file_type: Optional[str] = Field(None, description="文件类型")
    entity_type: Optional[str] = Field(None, description="关联实体类型")
    entity_id: Optional[str] = Field(None, description="关联实体ID")
    uploader_id: Optional[str] = Field(None, description="上传者ID")
    date_from: Optional[datetime] = Field(None, description="开始日期")
    date_to: Optional[datetime] = Field(None, description="结束日期")

class BatchFileDelete(BaseModel):
    """批量删除文件"""
    file_ids: List[str] = Field(..., description="文件ID列表")

# 允许的文件类型
ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
    'document': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'],
    'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
    'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv'],
    'audio': ['.mp3', '.wav', '.flac', '.aac']
}

# 最大文件大小（字节）
MAX_FILE_SIZE = settings.MAX_FILE_SIZE

def get_file_type(extension: str) -> str:
    """根据文件扩展名获取文件类型"""
    extension = extension.lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return file_type
    return 'other'

def is_allowed_file(filename: str) -> bool:
    """检查文件是否允许上传"""
    if '.' not in filename:
        return False
    
    extension = '.' + filename.rsplit('.', 1)[1].lower()
    all_extensions = []
    for extensions in ALLOWED_EXTENSIONS.values():
        all_extensions.extend(extensions)
    
    return extension in all_extensions

async def save_upload_file(upload_file: UploadFile, upload_dir: str) -> tuple:
    """保存上传的文件"""
    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    file_extension = '.' + upload_file.filename.rsplit('.', 1)[1].lower() if '.' in upload_file.filename else ''
    filename = f"{file_id}{file_extension}"
    
    # 确保上传目录存在
    os.makedirs(upload_dir, exist_ok=True)
    
    # 文件路径
    file_path = os.path.join(upload_dir, filename)
    
    # 保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        content = await upload_file.read()
        await f.write(content)
    
    # 获取文件大小
    file_size = len(content)
    
    # 获取文件类型
    file_type = get_file_type(file_extension)
    
    return filename, file_path, file_size, file_type, file_extension

@router.post("/upload", response_model=BaseResponse[FileResponse])
async def upload_file(
    file: UploadFile = File(...),
    entity_type: Optional[str] = Form(None),
    entity_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:upload"))
):
    """上传文件"""
    # 检查文件是否为空
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未选择文件"
        )
    
    # 检查文件类型
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型"
        )
    
    # 检查文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（{MAX_FILE_SIZE // 1024 // 1024}MB）"
        )
    
    # 重置文件指针
    await file.seek(0)
    
    try:
        # 保存文件
        filename, file_path, file_size, file_type, file_extension = await save_upload_file(
            file, settings.UPLOAD_DIR
        )
        
        # 生成文件URL
        file_url = f"/api/v1/files/download/{filename}"
        
        # 保存文件信息到数据库
        new_file = FileModel(
            filename=filename,
            original_filename=file.filename,
            file_path=file_path,
            file_url=file_url,
            file_size=file_size,
            file_type=file_type,
            file_extension=file_extension,
            entity_type=entity_type,
            entity_id=entity_id,
            uploader_id=current_user.id
        )
        
        db.add(new_file)
        await db.commit()
        await db.refresh(new_file)
        
        # 构建响应
        file_response = FileResponse(
            **new_file.__dict__,
            uploader_name=current_user.name
        )
        
        return BaseResponse(
            data=file_response,
            message="文件上传成功"
        )
        
    except Exception as e:
        # 如果数据库操作失败，删除已上传的文件
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败：{str(e)}"
        )

@router.post("/upload/multiple", response_model=BaseResponse[List[FileResponse]])
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    entity_type: Optional[str] = Form(None),
    entity_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:upload"))
):
    """批量上传文件"""
    if len(files) > 10:  # 限制批量上传数量
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="批量上传文件数量不能超过10个"
        )
    
    uploaded_files = []
    failed_files = []
    
    for file in files:
        try:
            # 检查文件
            if not file.filename:
                failed_files.append({"filename": "未知", "error": "未选择文件"})
                continue
            
            if not is_allowed_file(file.filename):
                failed_files.append({"filename": file.filename, "error": "不支持的文件类型"})
                continue
            
            # 检查文件大小
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                failed_files.append({"filename": file.filename, "error": "文件大小超过限制"})
                continue
            
            # 重置文件指针
            await file.seek(0)
            
            # 保存文件
            filename, file_path, file_size, file_type, file_extension = await save_upload_file(
                file, settings.UPLOAD_DIR
            )
            
            # 生成文件URL
            file_url = f"/api/v1/files/download/{filename}"
            
            # 保存文件信息到数据库
            new_file = FileModel(
                filename=filename,
                original_filename=file.filename,
                file_path=file_path,
                file_url=file_url,
                file_size=file_size,
                file_type=file_type,
                file_extension=file_extension,
                entity_type=entity_type,
                entity_id=entity_id,
                uploader_id=current_user.id
            )
            
            db.add(new_file)
            await db.flush()  # 获取ID但不提交
            
            file_response = FileResponse(
                **new_file.__dict__,
                uploader_name=current_user.name
            )
            uploaded_files.append(file_response)
            
        except Exception as e:
            failed_files.append({"filename": file.filename, "error": str(e)})
            # 如果文件已保存但数据库操作失败，删除文件
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
    
    # 提交所有成功的文件
    if uploaded_files:
        await db.commit()
    
    message = f"批量上传完成，成功{len(uploaded_files)}个，失败{len(failed_files)}个"
    if failed_files:
        message += f"。失败文件：{', '.join([f['filename'] for f in failed_files])}"
    
    return BaseResponse(
        data=uploaded_files,
        message=message
    )

@router.get("/", response_model=BaseResponse[PaginationResponse[FileResponse]])
async def get_files(
    pagination: PaginationParams = Depends(),
    search: FileSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:view"))
):
    """获取文件列表"""
    query = select(FileModel)
    
    # 搜索条件
    if search.keyword:
        query = query.where(
            or_(
                FileModel.filename.contains(search.keyword),
                FileModel.original_filename.contains(search.keyword)
            )
        )
    
    if search.file_type:
        query = query.where(FileModel.file_type == search.file_type)
    
    if search.entity_type:
        query = query.where(FileModel.entity_type == search.entity_type)
    
    if search.entity_id:
        query = query.where(FileModel.entity_id == search.entity_id)
    
    if search.uploader_id:
        query = query.where(FileModel.uploader_id == search.uploader_id)
    
    if search.date_from:
        query = query.where(FileModel.created_at >= search.date_from)
    
    if search.date_to:
        query = query.where(FileModel.created_at <= search.date_to)
    
    # 权限过滤：非管理员只能看到自己上传的文件
    if current_user.role not in ["admin", "manager"]:
        query = query.where(FileModel.uploader_id == current_user.id)
    
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
                if hasattr(FileModel, field):
                    if direction.lower() == 'desc':
                        query = query.order_by(getattr(FileModel, field).desc())
                    else:
                        query = query.order_by(getattr(FileModel, field).asc())
    else:
        query = query.order_by(FileModel.created_at.desc())
    
    # 执行查询
    result = await db.execute(query)
    files = result.scalars().all()
    
    # 获取上传者信息
    file_responses = []
    for file in files:
        uploader_result = await db.execute(
            select(User).where(User.id == file.uploader_id)
        )
        uploader = uploader_result.scalar_one_or_none()
        
        file_response = FileResponse(
            **file.__dict__,
            uploader_name=uploader.name if uploader else "未知用户"
        )
        file_responses.append(file_response)
    
    # 计算分页信息
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_prev = pagination.page > 1
    
    return BaseResponse(
        data=PaginationResponse(
            items=file_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        ),
        message="获取成功"
    )

@router.get("/{file_id}", response_model=BaseResponse[FileResponse])
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:view"))
):
    """获取文件详情"""
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and file.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此文件"
        )
    
    # 获取上传者信息
    uploader_result = await db.execute(
        select(User).where(User.id == file.uploader_id)
    )
    uploader = uploader_result.scalar_one_or_none()
    
    file_response = FileResponse(
        **file.__dict__,
        uploader_name=uploader.name if uploader else "未知用户"
    )
    
    return BaseResponse(
        data=file_response,
        message="获取成功"
    )

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:delete"))
):
    """删除文件"""
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and file.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限删除此文件"
        )
    
    # 删除物理文件
    if os.path.exists(file.file_path):
        try:
            os.remove(file.file_path)
        except Exception as e:
            # 记录日志但不阻止删除数据库记录
            print(f"删除物理文件失败：{e}")
    
    # 删除数据库记录
    await db.delete(file)
    await db.commit()
    
    return BaseResponse(message="文件删除成功")

@router.delete("/batch", response_model=BaseResponse)
async def batch_delete_files(
    batch_data: BatchFileDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:delete"))
):
    """批量删除文件"""
    success_count = 0
    failed_count = 0
    
    for file_id in batch_data.file_ids:
        try:
            result = await db.execute(select(FileModel).where(FileModel.id == file_id))
            file = result.scalar_one_or_none()
            
            if not file:
                failed_count += 1
                continue
            
            # 权限检查
            if current_user.role not in ["admin", "manager"] and file.uploader_id != current_user.id:
                failed_count += 1
                continue
            
            # 删除物理文件
            if os.path.exists(file.file_path):
                try:
                    os.remove(file.file_path)
                except Exception:
                    pass  # 忽略物理文件删除失败
            
            # 删除数据库记录
            await db.delete(file)
            success_count += 1
            
        except Exception:
            failed_count += 1
    
    await db.commit()
    
    return BaseResponse(
        message=f"批量删除完成，成功{success_count}个，失败{failed_count}个"
    )

from fastapi.responses import FileResponse as FastAPIFileResponse

@router.get("/download/{filename}")
async def download_file(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """下载文件"""
    # 查找文件记录
    result = await db.execute(select(FileModel).where(FileModel.filename == filename))
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"] and file.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限下载此文件"
        )
    
    # 检查物理文件是否存在
    if not os.path.exists(file.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="物理文件不存在"
        )
    
    # 返回文件
    return FastAPIFileResponse(
        path=file.file_path,
        filename=file.original_filename,
        media_type=mimetypes.guess_type(file.original_filename)[0] or 'application/octet-stream'
    )

@router.get("/statistics", response_model=BaseResponse[dict])
async def get_file_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("file:view"))
):
    """获取文件统计信息"""
    # 构建查询
    if current_user.role in ["admin", "manager"]:
        base_query = select(FileModel)
    else:
        base_query = select(FileModel).where(FileModel.uploader_id == current_user.id)
    
    # 总文件数
    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total_files = total_result.scalar()
    
    # 总文件大小
    total_size_result = await db.execute(
        select(func.sum(FileModel.file_size)).select_from(base_query.subquery())
    )
    total_size = total_size_result.scalar() or 0
    
    # 按类型统计
    by_type = {}
    for file_type in ['image', 'document', 'archive', 'video', 'audio', 'other']:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(FileModel.file_type == file_type).subquery()
            )
        )
        by_type[file_type] = count_result.scalar()
    
    # 本月上传文件数
    from datetime import datetime
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_result = await db.execute(
        select(func.count()).select_from(
            base_query.where(FileModel.created_at >= month_start).subquery()
        )
    )
    this_month_files = this_month_result.scalar()
    
    statistics = {
        "total_files": total_files,
        "total_size": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "by_type": by_type,
        "this_month_files": this_month_files
    }
    
    return BaseResponse(
        data=statistics,
        message="获取成功"
    )