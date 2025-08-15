"""角色相关的Pydantic模式定义"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RoleBase(BaseModel):
    """角色基础模式"""
    code: str = Field(..., max_length=100, description="角色编码")
    name: str = Field(..., max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_active: bool = Field(True, description="是否启用")


class RoleCreate(RoleBase):
    """角色创建模式"""
    pass


class RoleUpdate(BaseModel):
    """角色更新模式"""
    code: Optional[str] = Field(None, max_length=100, description="角色编码")
    name: Optional[str] = Field(None, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class RoleResponse(RoleBase):
    """角色响应模式"""
    id: str = Field(..., description="角色ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """角色列表响应模式"""
    id: str = Field(..., description="角色ID")
    code: str = Field(..., description="角色编码")
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_active: bool = Field(True, description="是否启用")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    user_count: int = Field(0, description="使用该角色的用户数量")
    
    class Config:
        from_attributes = True