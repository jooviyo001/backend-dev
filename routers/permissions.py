"""权限模块相关的API路由
提供权限管理和查询功能，使用新的权限服务层和缓存机制
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from models.database import get_db
from models.user import User
from schemas.permission import (
    PermissionCreate, PermissionUpdate, PermissionResponse,
    PermissionListResponse, UserPermissionResponse, RolePermissionResponse,
    PermissionCheckRequest, PermissionCheckResponse, PermissionStatsResponse
)
from schemas.base import BaseResponse
from services.permission_service import get_permission_service
from utils.auth import get_current_active_user
from utils.permission_middleware import require_permission, require_admin
from utils.permission_cache import get_permission_cache
from utils.response_utils import success_response
from utils.exceptions import BusinessException

router = APIRouter()

# 依赖注入
def get_permission_service_dep(db: Session = Depends(get_db)):
    """获取权限服务实例"""
    return get_permission_service(db)

def get_permission_cache_dep():
    """获取权限缓存实例"""
    return get_permission_cache()


# 权限管理API
@router.post("/create", response_model=BaseResponse)
async def create_permission(
    permission_data: PermissionCreate,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """创建新权限"""
    try:
        permission = await permission_service.create_permission(
            name=permission_data.name,
            code=permission_data.code,
            description=permission_data.description,
            module=permission_data.module,
            resource_type=permission_data.resource_type,
            action=permission_data.action
        )
        return success_response(data=permission, message="权限创建成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=BaseResponse)
async def get_permissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    module: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system:read"))
):
    """获取权限列表"""
    permissions = await permission_service.get_permissions(
        skip=skip,
        limit=limit,
        module=module,
        resource_type=resource_type,
        is_active=is_active
    )
    return success_response(data=permissions, message="获取权限列表成功")


@router.get("/{permission_id}", response_model=BaseResponse)
async def get_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system:read"))
):
    """获取指定权限详情"""
    permission = await permission_service.get_permission_by_id(permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    return success_response(data=permission, message="获取权限详情成功")

@router.put("/{permission_id}", response_model=BaseResponse)
async def update_permission(
    permission_id: int,
    permission_data: PermissionUpdate,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """更新权限信息"""
    try:
        permission = await permission_service.update_permission(
            permission_id=permission_id,
            **permission_data.dict(exclude_unset=True)
        )
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="权限不存在"
            )
        return success_response(data=permission, message="权限更新成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{permission_id}", response_model=BaseResponse)
async def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """删除权限"""
    success = await permission_service.delete_permission(permission_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    return success_response(message="权限删除成功")


# 用户权限API
@router.get("/user/{user_id}/permissions", response_model=BaseResponse)
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_permission("user:read"))
):
    """获取指定用户的权限信息"""
    try:
        # 使用缓存获取用户权限
        user_permissions = await permission_cache.get_user_permissions(user_id)
        if not user_permissions:
            # 缓存未命中，从服务层获取
            user_permissions = await permission_service.get_user_permissions(user_id)
            if user_permissions:
                # 更新缓存
                await permission_cache.set_user_permissions(user_id, user_permissions)
        
        if not user_permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在或无权限信息"
            )
        
        return success_response(data=user_permissions, message="获取用户权限信息成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user/me/permissions", response_model=BaseResponse)
async def get_current_user_permissions(
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的权限信息"""
    try:
        # 使用缓存获取用户权限
        user_permissions = await permission_cache.get_user_permissions(current_user.id)
        if not user_permissions:
            # 缓存未命中，从服务层获取
            user_permissions = await permission_service.get_user_permissions(current_user.id)
            if user_permissions:
                # 更新缓存
                await permission_cache.set_user_permissions(current_user.id, user_permissions)
        
        return success_response(data=user_permissions, message="获取当前用户权限信息成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 角色权限API
@router.get("/role/{role_id}/permissions", response_model=BaseResponse)
async def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取指定角色的权限信息"""
    try:
        # 使用缓存获取角色权限
        role_permissions = await permission_cache.get_role_permissions(role_id)
        if not role_permissions:
            # 缓存未命中，从服务层获取
            role_permissions = await permission_service.get_role_permissions(role_id)
            if role_permissions:
                # 更新缓存
                await permission_cache.set_role_permissions(role_id, role_permissions)
        
        if not role_permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在或无权限信息"
            )
        
        return success_response(data=role_permissions, message="获取角色权限信息成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/role/{role_id}/permissions", response_model=BaseResponse)
async def assign_role_permissions(
    role_id: int,
    permission_ids: List[int],
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """为角色分配权限"""
    try:
        success = await permission_service.assign_role_permissions(role_id, permission_ids)
        if success:
            # 清除相关缓存
            await permission_cache.invalidate_role_permissions(role_id)
            await permission_cache.invalidate_users_by_role(role_id)
        
        return success_response(message="角色权限分配成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/role/{role_id}/permissions/{permission_id}", response_model=BaseResponse)
async def revoke_role_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """撤销角色权限"""
    try:
        success = await permission_service.revoke_role_permission(role_id, permission_id)
        if success:
            # 清除相关缓存
            await permission_cache.invalidate_role_permissions(role_id)
            await permission_cache.invalidate_users_by_role(role_id)
        
        return success_response(message="角色权限撤销成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 权限检查API
@router.post("/check", response_model=BaseResponse)
async def check_user_permission(
    permission_request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(get_current_active_user)
):
    """检查当前用户是否拥有指定权限"""
    try:
        # 使用缓存进行权限检查
        has_permission = await permission_cache.check_user_permission(
            current_user.id, 
            permission_request.permission
        )
        
        if has_permission is None:
            # 缓存未命中，使用服务层检查
            has_permission = await permission_service.check_user_permission(
                current_user.id, 
                permission_request.permission
            )
        
        response_data = PermissionCheckResponse(
            has_permission=has_permission,
            permission=permission_request.permission,
            user_id=current_user.id,
            message="有权限" if has_permission else "无权限"
        )
        
        return success_response(
            data=response_data, 
            message=f"权限检查完成: {permission_request.permission}"
        )
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/check/batch", response_model=BaseResponse)
async def check_user_permissions_batch(
    permissions: List[str],
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(get_current_active_user)
):
    """批量检查用户权限"""
    try:
        target_user_id = user_id if user_id else current_user.id
        
        # 如果检查其他用户权限，需要管理员权限
        if user_id and user_id != current_user.id:
            admin_permission = await permission_service.check_user_permission(
                current_user.id, "user:read"
            )
            if not admin_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限检查其他用户权限"
                )
        
        # 使用缓存进行批量权限检查
        permission_results = await permission_cache.check_user_permissions_batch(
            target_user_id, permissions
        )
        
        return success_response(
            data=permission_results, 
            message="批量权限检查完成"
        )
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 权限统计API
@router.get("/stats", response_model=BaseResponse)
async def get_permission_stats(
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system:read"))
):
    """获取权限统计信息"""
    try:
        stats = await permission_service.get_permission_stats()
        return success_response(data=stats, message="获取权限统计信息成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

# 缓存管理API
@router.post("/cache/refresh", response_model=BaseResponse)
async def refresh_permission_cache(
    user_id: Optional[int] = None,
    role_id: Optional[int] = None,
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """刷新权限缓存"""
    try:
        if user_id:
            # 刷新指定用户的权限缓存
            await permission_cache.invalidate_user_permissions(user_id)
            user_permissions = await permission_service.get_user_permissions(user_id)
            if user_permissions:
                await permission_cache.set_user_permissions(user_id, user_permissions)
            message = f"用户 {user_id} 权限缓存刷新成功"
        elif role_id:
            # 刷新指定角色的权限缓存
            await permission_cache.invalidate_role_permissions(role_id)
            await permission_cache.invalidate_users_by_role(role_id)
            role_permissions = await permission_service.get_role_permissions(role_id)
            if role_permissions:
                await permission_cache.set_role_permissions(role_id, role_permissions)
            message = f"角色 {role_id} 权限缓存刷新成功"
        else:
            # 刷新所有权限缓存
            await permission_cache.clear_all_cache()
            message = "所有权限缓存刷新成功"
        
        return success_response(message=message)
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/cache/stats", response_model=BaseResponse)
async def get_cache_stats(
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_permission("system:read"))
):
    """获取权限缓存统计信息"""
    try:
        cache_stats = await permission_cache.get_cache_stats()
        return success_response(data=cache_stats, message="获取缓存统计信息成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")

# 权限模块API（兼容性保持）
@router.get("/modules", response_model=BaseResponse)
async def get_permission_modules(
    db: Session = Depends(get_db),
    permission_service = Depends(get_permission_service_dep),
    current_user: User = Depends(get_current_active_user)
):
    """获取权限模块列表（按模块分组的权限）"""
    try:
        modules = await permission_service.get_permission_modules()
        return success_response(data=modules, message="获取权限模块列表成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))