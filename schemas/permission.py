"""权限相关的数据模式"""
from typing import List, Dict, Any
from pydantic import BaseModel
from schemas.base import BaseResponse


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