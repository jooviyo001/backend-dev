from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

def default_timestamp() -> str:
    """返回格式化的当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 基础响应模式
class BaseResponse(BaseModel):
    """基础响应模式"""
    code: str = "200"
    message: str = "操作成功"
    data: Optional[Any] = None
    # 使用字符串类型的格式化时间戳
    timestamp: str = Field(default_factory=default_timestamp)
    
    class Config:
        from_attributes = True

# 分页响应模式
class PaginationResponse(BaseModel):
    """分页响应模式"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页数量")
    totalPages: int = Field(..., description="总页数")
    items: List[Any] = Field(..., description="数据列表")

    class Config:
        from_attributes = True