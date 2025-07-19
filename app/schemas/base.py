from pydantic import BaseModel
from typing import Optional, Any, Generic, TypeVar
from datetime import datetime

DataT = TypeVar('DataT')

class BaseResponse(BaseModel, Generic[DataT]):
    """统一响应格式"""
    code: int = 200
    message: str = "操作成功"
    data: Optional[DataT] = None
    success: bool = True
    timestamp: datetime = datetime.utcnow()

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = 1
    page_size: int = 20
    sort: Optional[str] = None  # 格式: field1:asc,field2:desc

class PaginationResponse(BaseModel, Generic[DataT]):
    """分页响应"""
    items: list[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

class SearchParams(BaseModel):
    """搜索参数"""
    keyword: Optional[str] = None
    type: Optional[str] = None  # 搜索类型
    filters: Optional[dict] = None

class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    ids: list[str]
    operation: str
    data: Optional[dict] = None

class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    success_count: int
    failed_count: int
    success_ids: list[str]
    failed_items: list[dict]
    total: int