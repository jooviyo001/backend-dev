"""角色相关的Pydantic模式定义"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import re


class RoleBase(BaseModel):
    """角色基础模式"""
    code: str = Field(..., min_length=2, max_length=50, description="角色编码")
    name: str = Field(..., min_length=2, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, max_length=500, description="角色描述")
    is_active: bool = Field(True, description="是否启用")
    
    @validator('code')
    def validate_code(cls, v):
        """验证角色编码格式"""
        if not v:
            raise ValueError('角色编码不能为空')
        
        # 角色编码只能包含字母、数字和下划线，且必须以字母开头
        if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', v):
            raise ValueError('角色编码只能包含字母、数字和下划线，且必须以字母开头')
        
        # 转换为大写
        return v.upper()
    
    @validator('name')
    def validate_name(cls, v):
        """验证角色名称"""
        if not v or not v.strip():
            raise ValueError('角色名称不能为空')
        
        # 去除首尾空格
        v = v.strip()
        
        # 检查是否包含特殊字符（允许中文、英文、数字、空格、短横线、下划线）
        if not re.match(r'^[\u4e00-\u9fa5A-Za-z0-9\s\-_]+$', v):
            raise ValueError('角色名称只能包含中文、英文、数字、空格、短横线和下划线')
        
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """验证角色描述"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class RoleCreate(RoleBase):
    """角色创建模式"""
    pass


class RoleUpdate(BaseModel):
    """角色更新模式"""
    code: Optional[str] = Field(None, min_length=2, max_length=50, description="角色编码")
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, max_length=500, description="角色描述")
    is_active: Optional[bool] = Field(None, description="是否启用")
    
    @validator('code')
    def validate_code(cls, v):
        """验证角色编码格式"""
        if v is None:
            return v
            
        if not v:
            raise ValueError('角色编码不能为空')
        
        # 角色编码只能包含字母、数字和下划线，且必须以字母开头
        if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', v):
            raise ValueError('角色编码只能包含字母、数字和下划线，且必须以字母开头')
        
        # 转换为大写
        return v.upper()
    
    @validator('name')
    def validate_name(cls, v):
        """验证角色名称"""
        if v is None:
            return v
            
        if not v or not v.strip():
            raise ValueError('角色名称不能为空')
        
        # 去除首尾空格
        v = v.strip()
        
        # 检查是否包含特殊字符（允许中文、英文、数字、空格、短横线、下划线）
        if not re.match(r'^[\u4e00-\u9fa5A-Za-z0-9\s\-_]+$', v):
            raise ValueError('角色名称只能包含中文、英文、数字、空格、短横线和下划线')
        
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """验证角色描述"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


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