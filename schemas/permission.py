"""权限相关的数据模式"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from schemas.base import BaseResponse


# 基础权限模型
class Permission(BaseModel):
    """权限基础模型"""
    id: str
    name: str
    code: str
    description: Optional[str] = None
    module: str
    resource_type: str
    action_type: str
    status: str = "active"  # active, inactive
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 权限表单数据
class PermissionFormData(BaseModel):
    """权限表单数据"""
    name: str = Field(..., description="权限名称")
    code: str = Field(..., description="权限代码")
    description: Optional[str] = Field(None, description="权限描述")
    module: str = Field(..., description="所属模块")
    resource_type: str = Field(..., description="资源类型")
    action_type: str = Field(..., description="操作类型")
    status: Optional[str] = Field("active", description="权限状态")


# 权限搜索参数
class PermissionSearchParams(BaseModel):
    """权限搜索参数"""
    page: Optional[int] = Field(1, ge=1, description="页码")
    limit: Optional[int] = Field(20, ge=1, le=100, description="每页数量")
    name: Optional[str] = Field(None, description="权限名称")
    code: Optional[str] = Field(None, description="权限代码")
    module: Optional[str] = Field(None, description="所属模块")
    resource_type: Optional[str] = Field(None, description="资源类型")
    action_type: Optional[str] = Field(None, description="操作类型")
    status: Optional[str] = Field(None, description="权限状态")
    keyword: Optional[str] = Field(None, description="搜索关键词")
    sort_field: Optional[str] = Field(None, description="排序字段")
    sort_order: Optional[str] = Field(None, description="排序顺序")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

# 权限列表响应
class PermissionListResponse(BaseModel):
    """权限列表响应"""
    items: List[Permission]
    total: int
    page: int
    limit: int
    totalPages: int


# 批量操作参数
class PermissionBatchOperationParams(BaseModel):
    """权限批量操作参数"""
    permission_ids: List[str] = Field(..., description="权限ID列表")
    operation: str = Field(..., description="操作类型: activate, deactivate, delete")
    data: Optional[Dict[str, Any]] = Field(None, description="操作数据")


class PermissionModule(BaseModel):
    """权限模块"""
    name: str  # 模块名称
    code: str  # 模块代码
    description: str  # 模块描述
    permissions: List[str]  # 模块包含的权限列表


class PermissionModuleResponse(BaseModel):
    """权限模块响应"""
    name: str
    code: str
    description: str
    permissions: List[str]


class PermissionModuleListResponse(BaseResponse):
    """权限模块列表响应"""
    data: List[PermissionModuleResponse]


class UserPermissionResponse(BaseModel):
    """用户权限响应"""
    user_id: str
    username: str
    role: str
    permissions: List[str]
    modules: List[PermissionModuleResponse]


class RolePermissionResponse(BaseModel):
    """角色权限响应"""
    role: str
    role_name: str
    permissions: List[str]
    modules: List[PermissionModuleResponse]


class PermissionCheckRequest(BaseModel):
    """权限检查请求"""
    permission: str  # 权限字符串，格式为 "resource:action"


class PermissionCheckResponse(BaseModel):
    """权限检查响应"""
    has_permission: bool
    permission: str
    message: str