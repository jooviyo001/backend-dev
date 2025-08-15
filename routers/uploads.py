from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, status
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from datetime import datetime
import mimetypes
from pathlib import Path

from models.database import get_db
from models.user import User
from schemas.base import BaseResponse
from utils.auth import require_permission
from utils.response_utils import standard_response

router = APIRouter()

# 配置上传目录
UPLOAD_DIR = "uploads/images"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif", 
    "image/bmp", "image/webp"
}

def ensure_upload_dir():
    """确保上传目录存在"""
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

def validate_image_file(file: UploadFile) -> None:
    """验证图片文件"""
    # 检查文件大小
    if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制，最大允许 {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # 检查文件扩展名
    if file.filename:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
            )
    
    # 检查MIME类型
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型，仅支持图片文件"
        )

def generate_filename(original_filename: str) -> str:
    """生成唯一的文件名"""
    file_ext = Path(original_filename).suffix.lower()
    unique_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{unique_id}{file_ext}"

@router.post("/image", response_model=BaseResponse)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload:write"))
):
    """上传单个图片文件"""
    try:
        # 验证文件
        validate_image_file(file)
        
        # 确保上传目录存在
        ensure_upload_dir()
        
        # 生成唯一文件名
        filename = generate_filename(file.filename or "image")
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # 保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 构建响应数据
        file_info = {
            "id": str(uuid.uuid4()),
            "filename": filename,
            "original_filename": file.filename,
            "file_path": file_path,
            "file_size": len(content),
            "content_type": file.content_type,
            "uploaded_by": current_user.id,
            "uploaded_at": datetime.now(),
            "url": f"/api/v1/uploads/files/{filename}"
        }
        
        return standard_response(
            data=file_info,
            message="图片上传成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )

@router.post("/images", response_model=BaseResponse)
async def upload_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload:write"))
):
    """批量上传图片文件"""
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="一次最多只能上传10个文件"
        )
    
    try:
        # 确保上传目录存在
        ensure_upload_dir()
        
        uploaded_files = []
        
        for file in files:
            # 验证文件
            validate_image_file(file)
            
            # 生成唯一文件名
            filename = generate_filename(file.filename or "image")
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            # 保存文件
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # 添加到结果列表
            file_info = {
                "id": str(uuid.uuid4()),
                "filename": filename,
                "original_filename": file.filename,
                "file_path": file_path,
                "file_size": len(content),
                "content_type": file.content_type,
                "uploaded_by": current_user.id,
                "uploaded_at": datetime.now(),
                "url": f"/api/v1/uploads/files/{filename}"
            }
            uploaded_files.append(file_info)
        
        return standard_response(
            data={
                "files": uploaded_files,
                "count": len(uploaded_files)
            },
            message=f"成功上传 {len(uploaded_files)} 个图片文件"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量上传失败: {str(e)}"
        )

@router.get("/files/{filename}")
async def get_file(filename: str):
    """获取上传的文件"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 获取文件的MIME类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=filename
    )

@router.delete("/files/{filename}", response_model=BaseResponse)
async def delete_file(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload:delete"))
):
    """删除上传的文件"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    try:
        os.remove(file_path)
        return standard_response(
            message="文件删除成功"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件删除失败: {str(e)}"
        )

@router.get("/info", response_model=BaseResponse)
async def get_upload_info():
    """获取上传配置信息"""
    return standard_response(
        data={
            "max_file_size": MAX_FILE_SIZE,
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "allowed_extensions": list(ALLOWED_EXTENSIONS),
            "allowed_mime_types": list(ALLOWED_MIME_TYPES),
            "max_batch_count": 10
        },
        message="获取上传配置成功"
    )