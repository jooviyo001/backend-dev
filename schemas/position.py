"""
职位相关的Pydantic模式定义
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class PositionBase(BaseModel):
    """职位基础模式"""
    name: str = Field(..., max_length=100, description="职位名称")
    description: Optional[str] = Field(None, description="职位描述")
    is_active: bool = Field(True, description="是否启用")


class PositionCreate(PositionBase):
    """职位创建模式"""
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """验证职位名称"""
        if not v or not v.strip():
            raise ValueError('职位名称不能为空')
        if len(v.strip()) > 100:
            raise ValueError('职位名称长度不能超过100个字符')
        return v.strip()


class PositionUpdate(BaseModel):
    """职位更新模式"""
    name: Optional[str] = Field(None, max_length=100, description="职位名称")
    description: Optional[str] = Field(None, description="职位描述")
    is_active: Optional[bool] = Field(None, description="是否启用")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """验证职位名称"""
        if v is not None:
            if not v.strip():
                raise ValueError('职位名称不能为空')
            if len(v.strip()) > 100:
                raise ValueError('职位名称长度不能超过100个字符')
            return v.strip()
        return v


class PositionResponse(PositionBase):
    """职位响应模式"""
    id: str = Field(..., description="职位ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class PositionListResponse(BaseModel):
    """职位列表响应模式"""
    id: str = Field(..., description="职位ID")
    name: str = Field(..., description="职位名称")
    is_active: bool = Field(..., description="是否启用")
    user_count: int = Field(0, description="使用该职位的用户数量")
    
    class Config:
        from_attributes = True