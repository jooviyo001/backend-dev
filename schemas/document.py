"""文档管理相关的Pydantic模式
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from models.enums import DocumentType
from .base import BaseResponse, PaginationResponse


class DocumentBase(BaseModel):
    """文档基础模式"""
    name: str = Field(..., min_length=1, max_length=255, description="文档/文件夹名称")
    type: DocumentType = Field(..., description="类型：文件夹或文档")
    parent_id: Optional[str] = Field(None, description="父级文件夹ID，根目录为null")
    description: Optional[str] = Field(None, max_length=1000, description="文档描述")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('名称不能为空')
        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'名称不能包含字符: {char}')
        return v.strip()


class DocumentCreate(DocumentBase):
    """创建文档模式"""
    pass


class DocumentUpdate(BaseModel):
    """更新文档模式"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="文档/文件夹名称")
    description: Optional[str] = Field(None, max_length=1000, description="文档描述")
    parent_id: Optional[str] = Field(None, description="父级文件夹ID")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError('名称不能为空')
            # 检查非法字符
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            for char in invalid_chars:
                if char in v:
                    raise ValueError(f'名称不能包含字符: {char}')
            return v.strip()
        return v


class DocumentRename(BaseModel):
    """重命名文档模式"""
    name: str = Field(..., min_length=1, max_length=255, description="新名称")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('名称不能为空')
        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'名称不能包含字符: {char}')
        return v.strip()


class DocumentResponse(BaseModel):
    """文档响应模式"""
    id: str = Field(..., description="文档/文件夹ID")
    name: str = Field(..., description="名称")
    type: DocumentType = Field(..., description="类型：文件夹或文档")
    parent_id: Optional[str] = Field(None, description="父级文件夹ID")
    file_type: Optional[str] = Field(None, description="文件类型（仅文档类型）")
    file_size: Optional[int] = Field(None, description="文件大小（字节，仅文档类型）")
    mime_type: Optional[str] = Field(None, description="MIME类型")
    description: Optional[str] = Field(None, description="文档描述")
    created_by: str = Field(..., description="创建人ID")
    updated_by: Optional[str] = Field(None, description="更新人ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """文档列表响应模式"""
    items: List[DocumentResponse] = Field(..., description="文档列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页数量")
    
    class Config:
        from_attributes = True


class FolderCreate(BaseModel):
    """创建文件夹模式"""
    name: str = Field(..., min_length=1, max_length=255, description="文件夹名称")
    parent_id: Optional[str] = Field(None, description="父级文件夹ID，根目录为null")
    description: Optional[str] = Field(None, max_length=1000, description="文件夹描述")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('文件夹名称不能为空')
        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'文件夹名称不能包含字符: {char}')
        return v.strip()


class DocumentUploadResponse(BaseModel):
    """文档上传响应模式"""
    id: str = Field(..., description="文档ID")
    name: str = Field(..., description="文档名称")
    type: DocumentType = Field(..., description="类型")
    parent_id: Optional[str] = Field(None, description="父级文件夹ID")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小（字节）")
    mime_type: str = Field(..., description="MIME类型")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class DocumentMoveRequest(BaseModel):
    """移动文档请求模式"""
    target_parent_id: Optional[str] = Field(None, description="目标父级文件夹ID，null表示移动到根目录")


class DocumentBatchDeleteRequest(BaseModel):
    """批量删除文档请求模式"""
    document_ids: List[str] = Field(..., min_items=1, max_items=100, description="要删除的文档ID列表")


class DocumentSearchRequest(BaseModel):
    """文档搜索请求模式"""
    keyword: str = Field(..., min_length=1, max_length=100, description="搜索关键词")
    parent_id: Optional[str] = Field(None, description="搜索范围的父级文件夹ID")
    file_type: Optional[str] = Field(None, description="文件类型过滤")
    document_type: Optional[DocumentType] = Field(None, description="文档类型过滤")
    page: int = Field(1, ge=1, description="页码")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


class DocumentStatistics(BaseModel):
    """文档统计信息"""
    total_documents: int = Field(..., description="文档总数")
    total_folders: int = Field(..., description="文件夹总数")
    total_size: int = Field(..., description="总文件大小（字节）")
    file_type_stats: dict = Field(..., description="文件类型统计")
    
    class Config:
        from_attributes = True