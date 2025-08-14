"""文档管理服务模块

提供文档和文件夹的增删改查等业务逻辑
"""
import io
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from models.document import Document
from schemas.document import (
    DocumentResponse, DocumentListResponse, FolderCreate, DocumentUploadResponse
)
from models.enums import DocumentType
from utils.snowflake import generate_document_id
from utils.minio_client import get_minio_client, generate_object_key, get_file_type_from_filename


class DocumentService:
    """文档管理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.minio_client = get_minio_client()
    
    def get_documents(
        self,
        parent_id: str = "0",
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None
    ) -> DocumentListResponse:
        """获取文档列表
        
        Args:
            parent_id: 父级文件夹ID
            page: 页码
            page_size: 每页数量
            user_id: 用户ID（用于权限控制）
            
        Returns:
            文档列表响应
        """
        # 构建查询条件
        query = self.db.query(Document).filter(
            Document.parent_id == parent_id,
            Document.is_deleted == False
        )
        
        # 如果指定了用户ID，只返回该用户的文档
        if user_id:
            query = query.filter(Document.created_by == user_id)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        documents = query.order_by(Document.type, Document.name).offset(offset).limit(page_size).all()
        
        # 转换为响应格式
        items = [self._document_to_response(doc) for doc in documents]
        
        return DocumentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    
    def create_folder(
        self,
        folder_data: FolderCreate,
        user_id: str
    ) -> DocumentResponse:
        """创建文件夹
        
        Args:
            folder_data: 文件夹创建数据
            user_id: 创建者ID
            
        Returns:
            文档响应
        """
        # 检查父级文件夹是否存在
        if folder_data.parent_id != "0":
            parent_folder = self.get_document_by_id(folder_data.parent_id, user_id)
            if not parent_folder or parent_folder.type != DocumentType.FOLDER:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="父级文件夹不存在"
                )
        
        # 检查同名文件夹是否存在
        existing = self.db.query(Document).filter(
            Document.parent_id == folder_data.parent_id,
            Document.name == folder_data.name,
            Document.type == DocumentType.FOLDER,
            Document.is_deleted == False,
            Document.created_by == user_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="文件夹名称已存在"
            )
        
        # 创建文件夹
        folder = Document(
            id=generate_document_id(),
            name=folder_data.name,
            type=DocumentType.FOLDER,
            parent_id=folder_data.parent_id,
            created_by=user_id,
            updated_by=user_id
        )
        
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        
        return self._document_to_response(folder)
    
    def upload_document(
        self,
        file: UploadFile,
        name: str,
        parent_id: str,
        user_id: str
    ) -> DocumentUploadResponse:
        """上传文档
        
        Args:
            file: 上传的文件
            name: 文档名称
            parent_id: 父级文件夹ID
            user_id: 上传者ID
            
        Returns:
            文档上传响应
        """
        # 检查父级文件夹是否存在
        if parent_id != "0":
            parent_folder = self.get_document_by_id(parent_id, user_id)
            if not parent_folder or parent_folder.type != DocumentType.FOLDER:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="父级文件夹不存在"
                )
        
        # 检查文件大小（50MB限制）
        max_size = 50 * 1024 * 1024  # 50MB
        if file.size and file.size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="文件大小超过50MB限制"
            )
        
        # 检查文件类型
        allowed_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.md', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar'
        }
        
        file_ext, content_type = get_file_type_from_filename(file.filename or "")
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"不支持的文件类型: {file_ext}"
            )
        
        # 检查同名文档是否存在
        existing = self.db.query(Document).filter(
            Document.parent_id == parent_id,
            Document.name == name,
            Document.type == DocumentType.DOCUMENT,
            Document.is_deleted == False,
            Document.created_by == user_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="文档名称已存在"
            )
        
        try:
            # 读取文件内容
            file_content = file.file.read()
            file_size = len(file_content)
            
            # 生成MinIO对象键
            object_key = generate_object_key(file.filename or name, user_id)
            
            # 上传到MinIO
            bucket_name, stored_object_key = self.minio_client.upload_file(
                file_data=io.BytesIO(file_content),
                object_key=object_key,
                file_size=file_size,
                content_type=content_type
            )
            
            # 创建文档记录
            document = Document(
                id=generate_document_id(),
                name=name,
                type=DocumentType.DOCUMENT,
                parent_id=parent_id,
                file_type=file_ext.lstrip('.'),
                file_size=file_size,
                minio_bucket=bucket_name,
                minio_object_key=stored_object_key,
                original_filename=file.filename,
                content_type=content_type,
                created_by=user_id,
                updated_by=user_id
            )
            
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            
            return DocumentUploadResponse(
                id=document.id,
                name=document.name,
                type=document.type.value,
                parent_id=document.parent_id,
                file_type=document.file_type,
                size=document.file_size,
                created_at=document.created_at,
                updated_at=document.updated_at
            )
            
        except Exception as e:
            # 如果数据库操作失败，尝试删除已上传的文件
            if 'stored_object_key' in locals():
                self.minio_client.delete_file(stored_object_key, bucket_name)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文档上传失败: {str(e)}"
            )
    
    def delete_document(
        self,
        document_id: str,
        user_id: str
    ) -> bool:
        """删除文档或文件夹
        
        Args:
            document_id: 文档ID
            user_id: 用户ID
            
        Returns:
            是否删除成功
        """
        document = self.get_document_by_id(document_id, user_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        try:
            if document.type == DocumentType.FOLDER:
                # 递归删除文件夹及其内容
                self._delete_folder_recursive(document, user_id)
            else:
                # 删除文档文件
                if document.minio_object_key:
                    self.minio_client.delete_file(
                        document.minio_object_key,
                        document.minio_bucket
                    )
                
                # 标记为已删除
                document.is_deleted = True
                document.deleted_at = datetime.utcnow()
                document.updated_by = user_id
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除失败: {str(e)}"
            )
    
    def rename_document(
        self,
        document_id: str,
        new_name: str,
        user_id: str
    ) -> DocumentResponse:
        """重命名文档或文件夹
        
        Args:
            document_id: 文档ID
            new_name: 新名称
            user_id: 用户ID
            
        Returns:
            文档响应
        """
        document = self.get_document_by_id(document_id, user_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查同名文档是否存在
        existing = self.db.query(Document).filter(
            Document.parent_id == document.parent_id,
            Document.name == new_name,
            Document.type == document.type,
            Document.is_deleted == False,
            Document.created_by == user_id,
            Document.id != document_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="名称已存在"
            )
        
        # 更新名称
        document.name = new_name
        document.updated_by = user_id
        document.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(document)
        
        return self._document_to_response(document)
    
    def download_document(
        self,
        document_id: str,
        user_id: str
    ) -> Tuple[io.BytesIO, str, str]:
        """下载文档
        
        Args:
            document_id: 文档ID
            user_id: 用户ID
            
        Returns:
            Tuple[文件流, 文件名, 内容类型]
        """
        document = self.get_document_by_id(document_id, user_id)
        if not document or document.type != DocumentType.DOCUMENT:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        if not document.minio_object_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档文件不存在"
            )
        
        try:
            # 从MinIO下载文件
            file_data = self.minio_client.download_file(
                document.minio_object_key,
                document.minio_bucket
            )
            
            # 读取文件内容到内存
            content = file_data.read()
            file_stream = io.BytesIO(content)
            
            return file_stream, document.original_filename or document.name, document.content_type or "application/octet-stream"
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文档下载失败: {str(e)}"
            )
    
    def get_document_by_id(
        self,
        document_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Document]:
        """根据ID获取文档
        
        Args:
            document_id: 文档ID
            user_id: 用户ID（用于权限控制）
            
        Returns:
            文档对象
        """
        query = self.db.query(Document).filter(
            Document.id == document_id,
            Document.is_deleted == False
        )
        
        if user_id:
            query = query.filter(Document.created_by == user_id)
        
        return query.first()
    
    def _delete_folder_recursive(
        self,
        folder: Document,
        user_id: str
    ) -> None:
        """递归删除文件夹及其内容
        
        Args:
            folder: 文件夹对象
            user_id: 用户ID
        """
        # 获取文件夹下的所有子项
        children = self.db.query(Document).filter(
            Document.parent_id == folder.id,
            Document.is_deleted == False,
            Document.created_by == user_id
        ).all()
        
        for child in children:
            if child.type == DocumentType.FOLDER:
                # 递归删除子文件夹
                self._delete_folder_recursive(child, user_id)
            else:
                # 删除文档文件
                if child.minio_object_key:
                    self.minio_client.delete_file(
                        child.minio_object_key,
                        child.minio_bucket
                    )
                
                # 标记为已删除
                child.is_deleted = True
                child.deleted_at = datetime.utcnow()
                child.updated_by = user_id
        
        # 标记文件夹为已删除
        folder.is_deleted = True
        folder.deleted_at = datetime.utcnow()
        folder.updated_by = user_id
    
    def _document_to_response(self, document: Document) -> DocumentResponse:
        """将文档对象转换为响应格式
        
        Args:
            document: 文档对象
            
        Returns:
            文档响应
        """
        return DocumentResponse(
            id=document.id,
            name=document.name,
            type=document.type.value,
            parent_id=document.parent_id,
            file_type=document.file_type,
            size=document.file_size,
            created_at=document.created_at,
            updated_at=document.updated_at
        )


def get_document_service(db: Session) -> DocumentService:
    """获取文档服务实例"""
    return DocumentService(db)