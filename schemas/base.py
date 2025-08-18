from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

def default_timestamp() -> str:
    """返回格式化的当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 基础响应模式
class BaseResponse(BaseModel):
    code: str = "200"
    message: str = "操作成功"
    data: Optional[Any] = None
    # 使用字符串类型的格式化时间戳
    timestamp: str = Field(default_factory=default_timestamp)
    
    class Config:
        from_attributes = True

# 分页响应模式
class PaginationResponse(BaseModel):
    total: int
    page: int
    size: int
    totalPages: int
    items: List[Any]