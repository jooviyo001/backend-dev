"""
职位相关的Pydantic模式定义
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class PositionBase(BaseModel):
    """职位基础模式"""
    name: str = Field(..., max_length=100, description="职位名称")
    code: str = Field(..., max_length=100, description="职位编码")
    department: str = Field(..., description="组织名称")
    level: str = Field(..., max_length=100, description="职位级别")
    department_id: str = Field(..., description="组织ID")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = Field(None, description="职位描述")
    # 职位要求
    requirements: Optional[str] = Field(None, description="职位要求")
    # 职位职责
    responsibilities: Optional[str] = Field(None, description="职位职责")


class PositionCreate(PositionBase):
    """职位创建模式"""
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """验证职位名称"""
        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'职位名称不能包含字符: {char}')
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


class PositionResponse(BaseModel):
    """职位响应模式"""
    id: str = Field(..., description="职位ID")
    name: str = Field(..., max_length=100, description="职位名称")
    code: str = Field(..., max_length=100, description="职位编码")
    department_id: str = Field(..., description="组织ID")
    department: Optional[str] = Field(None, description="组织名称")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = Field(None, description="职位描述")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class PositionListResponse(BaseModel):
    """职位列表响应模式
    包含职位的基本信息、创建时间、更新时间、使用该职位的用户数量和项目数量
    字段说明：
    id：职位ID
    name：职位名称
    code：职位编码
    department_id：所属部门ID
    department_name：所属部门名称
    type：职位类型
    description：职位描述
    is_active：是否启用
    created_at：创建时间
    updated_at：更新时间
    user_count：使用该职位的用户数量
    project_count：使用该职位的项目数量
    """
    
    id: str = Field(..., description="职位ID")
    code: str = Field(..., description="职位编码")
    name: str = Field(..., description="职位名称")
    department_id: str = Field(..., description="所属部门ID")
    department_name: str = Field(..., description="所属部门名称")
    type: str = Field(..., description="职位类型")
    code: str = Field(..., description="职位编码")
    description: Optional[str] = Field(None, description="职位描述")
    is_active: bool = Field(True, description="是否启用")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    user_count: int = Field(0, description="使用该职位的用户数量")
    project_count: int = Field(0, description="使用该职位的项目数量")

    class Config:
        from_attributes = True
        