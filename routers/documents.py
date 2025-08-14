"""文档管理路由模块

提供文档和文件夹管理的API接口
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from models.database import get_db
from models.user import User
from schemas.document import (
    DocumentResponse, FolderCreate, DocumentRename
)
from services.document_service import get_document_service
from utils.auth import get_current_user
from utils.response_utils import success_response, error_response

router = APIRouter()


@router.get("/documents", response_model=dict)
async def get_documents(
    parent_id: str = "0",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文档列表
    
    Args:
        parent_id: 父级文件夹ID，默认为'0'（根目录）
        page: 页码，默认为1
        page_size: 每页数量，默认为20
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        文档列表响应
    """
    try:
        # 验证分页参数
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        document_service = get_document_service(db)
        result = document_service.get_documents(
            parent_id=parent_id,
            page=page,
            page_size=page_size,
            user_id=current_user.id
        )
        
        return success_response(
            data=result.dict(),
            message="获取文档列表成功"
        )
        
    except Exception as e:
        return error_response(
            code=500,
            message=f"获取文档列表失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.post("/documents/folder", response_model=dict)
async def create_folder(
    folder_data: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建文件夹
    
    Args:
        folder_data: 文件夹创建数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建的文件夹信息
    """
    try:
        document_service = get_document_service(db)
        result = document_service.create_folder(
            folder_data=folder_data,
            user_id=current_user.id
        )
        
        return success_response(
            data=result.dict(),
            message="文件夹创建成功"
        )
        
    except HTTPException as e:
        return error_response(
            message=e.detail,
            status_code=e.status_code
        )
    except Exception as e:
        return error_response(
            message=f"文件夹创建失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.post("/documents/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    name: str = Form(...),
    parent_id: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传文档
    
    Args:
        file: 上传的文件
        name: 文档名称
        parent_id: 父级文件夹ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        上传的文档信息
    """
    try:
        document_service = get_document_service(db)
        result = document_service.upload_document(
            file=file,
            name=name,
            parent_id=parent_id,
            user_id=current_user.id
        )
        
        return success_response(
            data=result.dict(),
            message="文档上传成功"
        )
        
    except HTTPException as e:
        return error_response(
            message=e.detail,
            status_code=e.status_code
        )
    except Exception as e:
        return error_response(
            message=f"文档上传失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/documents/{document_id}", response_model=dict)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除文档或文件夹
    
    Args:
        document_id: 文档或文件夹ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        删除结果
    """
    try:
        document_service = get_document_service(db)
        success = document_service.delete_document(
            document_id=document_id,
            user_id=current_user.id
        )
        
        if success:
            return success_response(message="删除成功")
        else:
            return error_response(
                message="删除失败",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except HTTPException as e:
        return error_response(
            message=e.detail,
            status_code=e.status_code
        )
    except Exception as e:
        return error_response(
            message=f"删除失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.put("/documents/{document_id}/rename", response_model=dict)
async def rename_document(
    document_id: str,
    rename_data: DocumentRename,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """重命名文档或文件夹
    
    Args:
        document_id: 文档或文件夹ID
        rename_data: 重命名数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        重命名后的文档信息
    """
    try:
        document_service = get_document_service(db)
        result = document_service.rename_document(
            document_id=document_id,
            new_name=rename_data.name,
            user_id=current_user.id
        )
        
        return success_response(
            data=result.dict(),
            message="重命名成功"
        )
        
    except HTTPException as e:
        return error_response(
            message=e.detail,
            status_code=e.status_code
        )
    except Exception as e:
        return error_response(
            message=f"重命名失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载文档
    
    Args:
        document_id: 文档ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        文件流响应
    """
    try:
        document_service = get_document_service(db)
        file_stream, filename, content_type = document_service.download_document(
            document_id=document_id,
            user_id=current_user.id
        )
        
        # 设置响应头
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Content-Type": content_type
        }
        
        return StreamingResponse(
            iter([file_stream.getvalue()]),
            headers=headers,
            media_type=content_type
        )
        
    except HTTPException as e:
        return error_response(
            message=e.detail,
            status_code=e.status_code
        )
    except Exception as e:
        return error_response(
            message=f"文档下载失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/documents/{document_id}", response_model=dict)
async def get_document_detail(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文档详情
    
    Args:
        document_id: 文档ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        文档详情
    """
    try:
        document_service = get_document_service(db)
        document = document_service.get_document_by_id(
            document_id=document_id,
            user_id=current_user.id
        )
        
        if not document:
            return error_response(
                message="文档不存在",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        result = document_service._document_to_response(document)
        
        return success_response(
            data=result.dict(),
            message="获取文档详情成功"
        )
        
    except Exception as e:
        return error_response(
            message=f"获取文档详情失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/documents/statistics", response_model=dict)
async def get_document_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文档统计信息
    
    Args:
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        文档统计信息
    """
    try:
        from models.document import Document
        from enums import DocumentType
        from sqlalchemy import func
        
        # 统计文件夹数量
        folder_count = db.query(Document).filter(
            Document.created_by == current_user.id,
            Document.type == DocumentType.FOLDER,
            Document.is_deleted == False
        ).count()
        
        # 统计文档数量
        document_count = db.query(Document).filter(
            Document.created_by == current_user.id,
            Document.type == DocumentType.DOCUMENT,
            Document.is_deleted == False
        ).count()
        
        # 统计总文件大小
        total_size_result = db.query(func.sum(Document.file_size)).filter(
            Document.created_by == current_user.id,
            Document.type == DocumentType.DOCUMENT,
            Document.is_deleted == False
        ).scalar()
        
        total_size = total_size_result or 0
        
        statistics = {
            "folder_count": folder_count,
            "document_count": document_count,
            "total_size": total_size,
            "total_items": folder_count + document_count
        }
        
        return success_response(
            data=statistics,
            message="获取统计信息成功"
        )
        
    except Exception as e:
        return error_response(
            message=f"获取统计信息失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )