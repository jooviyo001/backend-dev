"""权限模块相关的API路由
提供权限模块管理和查询功能
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.database import get_db
from models.user import User
from schemas.permission import (
    PermissionModuleResponse, PermissionModuleListResponse,
    UserPermissionResponse, RolePermissionResponse,
    PermissionCheckRequest, PermissionCheckResponse
)
from schemas.base import BaseResponse
from utils.auth import get_current_active_user, require_permission, check_permission
from utils.response_utils import success_response

router = APIRouter()

# 权限模块定义
PERMISSION_MODULES = {
    "user": {
        "name": "用户管理",
        "code": "user",
        "description": "用户信息管理、用户状态管理等功能",
        "permissions": ["user:read", "user:write"]
    },
    "project": {
        "name": "项目管理",
        "code": "project",
        "description": "项目创建、编辑、删除、成员管理等功能",
        "permissions": ["project:read", "project:write"]
    },
    "task": {
        "name": "任务管理",
        "code": "task",
        "description": "任务创建、分配、状态更新、优先级设置等功能",
        "permissions": ["task:read", "task:write"]
    },
    "organization": {
        "name": "组织管理",
        "code": "organization",
        "description": "组织架构管理、部门管理、成员分配等功能",
        "permissions": ["organization:read", "organization:write"]
    },
    "defect": {
        "name": "缺陷管理",
        "code": "defect",
        "description": "缺陷报告、跟踪、修复状态管理等功能",
        "permissions": ["defect:read", "defect:write"]
    },
    "upload": {
        "name": "文件管理",
        "code": "upload",
        "description": "文件上传、下载、删除等功能",
        "permissions": ["upload:read", "upload:write", "upload:delete"]
    },
    "comment": {
        "name": "评论管理",
        "code": "comment",
        "description": "评论创建、编辑、删除等功能",
        "permissions": ["comment:create", "comment:read", "comment:update", "comment:delete"]
    }
}

# 角色权限映射（从 utils/auth.py 复制）
ROLE_PERMISSIONS = {
    "admin": ["user:read", "user:write", "project:read", "project:write", 
             "task:read", "task:write", "organization:read", "organization:write",
             "defect:read", "defect:write", "upload:read", "upload:write", "upload:delete"],
    "manager": ["user:read", "project:read", "project:write", 
               "task:read", "task:write", "organization:read",
               "defect:read", "defect:write", "upload:read", "upload:write", "upload:delete"],
    "member": ["user:read", "project:read", "task:read", "task:write",
              "defect:read", "defect:write", "upload:read", "upload:write"],
    "user": ["user:read", "project:read", "task:read", "defect:read", "upload:read"]
}

ROLE_NAMES = {
    "admin": "管理员",
    "manager": "项目经理",
    "member": "项目成员",
    "user": "普通用户"
}


@router.get("/modules", response_model=PermissionModuleListResponse)
async def get_permission_modules(
    current_user: User = Depends(get_current_active_user)
):
    """获取所有权限模块列表"""
    modules = []
    for module_code, module_info in PERMISSION_MODULES.items():
        modules.append(PermissionModuleResponse(
            name=module_info["name"],
            code=module_info["code"],
            description=module_info["description"],
            permissions=module_info["permissions"]
        ))
    
    return success_response(data=modules, message="获取权限模块列表成功")


@router.get("/modules/{module_code}", response_model=BaseResponse)
async def get_permission_module(
    module_code: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取指定权限模块详情"""
    if module_code not in PERMISSION_MODULES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限模块不存在"
        )
    
    module_info = PERMISSION_MODULES[module_code]
    module_data = PermissionModuleResponse(
        name=module_info["name"],
        code=module_info["code"],
        description=module_info["description"],
        permissions=module_info["permissions"]
    )
    
    return success_response(data=module_data, message="获取权限模块详情成功")


@router.get("/user/permissions", response_model=BaseResponse)
async def get_user_permissions(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的权限信息"""
    user_permissions = ROLE_PERMISSIONS.get(current_user.role.value, [])
    
    # 获取用户拥有的模块
    user_modules = []
    for module_code, module_info in PERMISSION_MODULES.items():
        # 检查用户是否拥有该模块的任何权限
        has_module_permission = any(
            perm in user_permissions for perm in module_info["permissions"]
        )
        if has_module_permission:
            # 过滤出用户实际拥有的权限
            available_permissions = [
                perm for perm in module_info["permissions"]
                if perm in user_permissions
            ]
            user_modules.append(PermissionModuleResponse(
                name=module_info["name"],
                code=module_info["code"],
                description=module_info["description"],
                permissions=available_permissions
            ))
    
    user_permission_data = UserPermissionResponse(
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        permissions=user_permissions,
        modules=user_modules
    )
    
    return success_response(data=user_permission_data, message="获取用户权限信息成功")


@router.get("/roles/{role}/permissions", response_model=BaseResponse)
async def get_role_permissions(
    role: str,
    current_user: User = Depends(require_permission("user:read"))
):
    """获取指定角色的权限信息"""
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    role_permissions = ROLE_PERMISSIONS[role]
    
    # 获取角色拥有的模块
    role_modules = []
    for module_code, module_info in PERMISSION_MODULES.items():
        # 检查角色是否拥有该模块的任何权限
        has_module_permission = any(
            perm in role_permissions for perm in module_info["permissions"]
        )
        if has_module_permission:
            # 过滤出角色实际拥有的权限
            available_permissions = [
                perm for perm in module_info["permissions"]
                if perm in role_permissions
            ]
            role_modules.append(PermissionModuleResponse(
                name=module_info["name"],
                code=module_info["code"],
                description=module_info["description"],
                permissions=available_permissions
            ))
    
    role_permission_data = RolePermissionResponse(
        role=role,
        role_name=ROLE_NAMES.get(role, role),
        permissions=role_permissions,
        modules=role_modules
    )
    
    return success_response(data=role_permission_data, message="获取角色权限信息成功")


@router.post("/check", response_model=BaseResponse)
async def check_user_permission(
    permission_request: PermissionCheckRequest,
    current_user: User = Depends(get_current_active_user)
):
    """检查当前用户是否拥有指定权限"""
    has_permission = check_permission(current_user, permission_request.permission)
    
    response_data = PermissionCheckResponse(
        has_permission=has_permission,
        permission=permission_request.permission,
        message="有权限" if has_permission else "无权限"
    )
    
    return success_response(
        data=response_data, 
        message=f"权限检查完成: {permission_request.permission}"
    )


@router.get("/roles", response_model=BaseResponse)
async def get_all_roles(
    current_user: User = Depends(require_permission("user:read"))
):
    """获取所有角色及其权限信息"""
    roles_data = []
    for role, permissions in ROLE_PERMISSIONS.items():
        # 获取角色拥有的模块
        role_modules = []
        for module_code, module_info in PERMISSION_MODULES.items():
            # 检查角色是否拥有该模块的任何权限
            has_module_permission = any(
                perm in permissions for perm in module_info["permissions"]
            )
            if has_module_permission:
                # 过滤出角色实际拥有的权限
                available_permissions = [
                    perm for perm in module_info["permissions"]
                    if perm in permissions
                ]
                role_modules.append(PermissionModuleResponse(
                    name=module_info["name"],
                    code=module_info["code"],
                    description=module_info["description"],
                    permissions=available_permissions
                ))
        
        roles_data.append(RolePermissionResponse(
            role=role,
            role_name=ROLE_NAMES.get(role, role),
            permissions=permissions,
            modules=role_modules
        ))
    
    return success_response(data=roles_data, message="获取所有角色权限信息成功")