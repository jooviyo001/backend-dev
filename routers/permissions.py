"""权限模块相关的API路由
提供权限管理和查询功能，使用新的权限服务层和缓存机制
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File
from sqlalchemy.orm import Session

from models.database import get_db
from models.user import User
from schemas.permission import (
    Permission, PermissionFormData, PermissionSearchParams, PermissionListResponse,
    PermissionBatchOperationParams, UserPermissionResponse, RolePermissionResponse, 
    PermissionCheckRequest, PermissionCheckResponse, PermissionModule, PermissionModuleResponse
)
from schemas.base import BaseResponse
from services.permission_service import get_permission_service, PermissionService
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

# 异步权限管理API
@router.post("/", response_model=Permission)
def create_permission(
    permission_data: PermissionFormData,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """创建新权限"""
    try:
        permission = permission_service.create_permission(
            name=permission_data.name,
            code=permission_data.code,
            description=permission_data.description,
            module=permission_data.module,
            resource_type=permission_data.resource_type,
            action_type=permission_data.action_type,
            status=permission_data.status
        )
        return permission
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/pages", response_model=PermissionListResponse)
def get_permissions(
    params: PermissionSearchParams = Depends(),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限列表"""
    try:
        permissions, total_count = permission_service.get_permissions_paginated(
            page=params.page,
            limit=params.limit,
            query=params.keyword,
            resource_type=params.resource_type,
            action_type=params.action_type,
            is_active=params.is_active,
            start_time=params.created_at_start,
            end_time=params.created_at_end
        )
        
        # 计算总页数
        total_pages = (total_count + params.limit - 1) // params.limit
        
        return PermissionListResponse(
            success=True,
            message="获取权限列表成功",
            data=permissions,
            total=total_count,
            page=params.page,
            limit=params.limit,
            totalPages=total_pages
        )
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{permission_id}", response_model=Permission)
def get_permission(
    permission_id: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取指定权限详情"""
    try:
        permission = permission_service.get_permission_by_id(permission_id)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="权限不存在"
            )
        return permission
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{permission_id}", response_model=Permission)
def update_permission(
    permission_id: str,
    permission_data: PermissionFormData,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """更新权限信息"""
    try:
        permission = permission_service.update_permission(
            permission_id=permission_id,
            name=permission_data.name,
            code=permission_data.code,
            description=permission_data.description,
            module=permission_data.module,
            resource_type=permission_data.resource_type,
            action_type=permission_data.action_type,
            status=permission_data.status
        )
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="权限不存在"
            )
        return permission
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{permission_id}")
def delete_permission(
    permission_id: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """删除权限"""
    try:
        success = permission_service.delete_permission(permission_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="权限不存在"
            )
        return {"message": "权限删除成功"}
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/batch")
def batch_delete_permissions(
    request_data: dict,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """批量删除权限"""
    try:
        permission_ids = request_data.get("permission_ids", [])
        if not permission_ids:
            raise HTTPException(status_code=400, detail="权限ID列表不能为空")
        
        success_count = permission_service.batch_delete_permissions(permission_ids)
        return {
            "message": f"成功删除 {success_count} 个权限",
            "deleted_count": success_count
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-operation")
def batch_operate_permissions(
    params: PermissionBatchOperationParams,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """批量操作权限"""
    try:
        result = permission_service.batch_operate_permissions(
            permission_ids=params.permission_ids,
            operation=params.operation,
            data=params.data
        )
        return {
            "message": f"批量操作完成",
            "operation": params.operation,
            "affected_count": result.get("affected_count", 0)
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/copy", response_model=Permission)
def copy_permission(
    request_data: dict,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """复制权限"""
    try:
        permission_id = request_data.get("permission_id")
        name = request_data.get("name")
        code = request_data.get("code")
        
        if not all([permission_id, name, code]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        permission = permission_service.copy_permission(
            permission_id=permission_id,
            new_name=name,
            new_code=code
        )
        return permission
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/status", response_model=Permission)
def update_permission_status(
    request_data: dict,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """更新权限状态"""
    try:
        permission_id = request_data.get("permission_id")
        status = request_data.get("status")
        
        if not permission_id or not status:
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        if status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="无效的状态值")
        
        permission = permission_service.update_permission_status(
            permission_id=permission_id,
            status=status
        )
        return permission
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
def get_permission_stats(
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限统计"""
    try:
        stats = permission_service.get_permission_stats()
        return {
            "total": stats.get("total", 0),
            "active": stats.get("active", 0),
            "inactive": stats.get("inactive", 0),
            "by_module": stats.get("by_module", {}),
            "by_type": stats.get("by_type", {})
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/check-code")
def check_permission_code(
    code: str = Query(..., description="权限代码"),
    exclude_id: Optional[str] = Query(None, description="排除的权限ID"),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """检查权限代码是否可用"""
    try:
        available = permission_service.check_permission_code_available(
            code=code,
            exclude_id=exclude_id
        )
        return {"available": available}
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/modules", response_model=List[PermissionModule])
def get_permission_modules(
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(get_current_active_user)
):
    """获取权限模块列表"""
    try:
        modules = permission_service.get_permission_modules()
        return modules
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/by-module/{module}", response_model=List[Permission])
def get_permissions_by_module(
    module: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """按模块获取权限"""
    try:
        permissions = permission_service.get_permissions_by_module(module)
        return permissions
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/by-type/{type}", response_model=List[Permission])
def get_permissions_by_type(
    type: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """按类型获取权限"""
    try:
        permissions = permission_service.get_permissions_by_type(type)
        return permissions
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=List[Permission])
def search_permissions(
    q: str = Query(..., description="搜索关键词"),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """搜索权限"""
    try:
        permissions = permission_service.search_permissions(q)
        return permissions
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 用户权限API
@router.get("/users/{user_id}/permissions", response_model=List[Permission])
def get_user_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("user", "read"))
):
    """获取用户权限"""
    try:
        permissions = permission_service.get_user_permissions(user_id)
        return permissions
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}/permissions/check")
def check_user_permission(
    user_id: str,
    permission_code: str = Query(..., description="权限代码"),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("user", "read"))
):
    """检查用户是否有特定权限"""
    try:
        has_permission = permission_service.check_user_permission(
            user_id=user_id,
            permission_code=permission_code
        )
        return {"hasPermission": has_permission}
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 角色权限API
@router.get("/roles/{role_id}/permissions", response_model=List[Permission])
def get_role_permissions(
    role_id: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("role", "read"))
):
    """获取角色权限"""
    try:
        permissions = permission_service.get_role_permissions(role_id)
        return permissions
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: str,
    request_data: dict,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("role", "write"))
):
    """更新角色权限"""
    try:
        permission_ids = request_data.get("permission_ids", [])
        permission_service.update_role_permissions(
            role_id=role_id,
            permission_ids=permission_ids
        )
        return {"message": "角色权限更新成功"}
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 高级功能API
@router.get("/export")
def export_permissions(
    params: PermissionSearchParams = Depends(),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """导出权限数据"""
    try:
        file_content = permission_service.export_permissions(params)
        return Response(
            content=file_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=permissions.xlsx"}
        )
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import")
def import_permissions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """导入权限数据"""
    try:
        result = permission_service.import_permissions(file)
        return {
            "success": result.get("success", 0),
            "failed": result.get("failed", 0),
            "errors": result.get("errors", [])
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{id}/dependencies")
def get_permission_dependencies(
    id: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限依赖关系"""
    try:
        dependencies = permission_service.get_permission_dependencies(id)
        return {
            "dependencies": dependencies.get("dependencies", []),
            "dependents": dependencies.get("dependents", [])
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate")
def validate_permission_config(
    data: PermissionFormData,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """验证权限配置"""
    try:
        result = permission_service.validate_permission_config(data)
        return {
            "valid": result.get("valid", False),
            "errors": result.get("errors", [])
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{id}/usage")
def get_permission_usage(
    id: str,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限使用情况"""
    try:
        usage = permission_service.get_permission_usage(id)
        return {
            "roles": usage.get("roles", 0),
            "users": usage.get("users", 0),
            "last_used": usage.get("last_used")
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync-cache")
def sync_permission_cache(
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_admin)
):
    """同步权限缓存"""
    try:
        result = permission_service.sync_permission_cache()
        return {
            "success": result.get("success", False),
            "message": result.get("message", "缓存同步完成")
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{id}/history")
def get_permission_history(
    id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限变更历史"""
    try:
        history = permission_service.get_permission_history(
            permission_id=id,
            page=page,
            limit=limit
        )
        return {
            "items": history.get("items", []),
            "total": history.get("total", 0),
            "page": page,
            "limit": limit
        }
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 角色权限API
@router.get("/role/{role_id}/permissions", response_model=BaseResponse)
def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("role", "read"))
):
    """获取指定角色的权限信息"""
    try:
        # 直接从服务层获取角色权限
        role_permissions = permission_service.get_role_permissions(role_id)
        
        if not role_permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在或无权限信息"
            )
        
        return success_response(data=role_permissions, message="获取角色权限信息成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/role/{role_id}/permissions", response_model=BaseResponse)
def assign_role_permissions(
    role_id: int,
    permission_ids: List[int],
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """为角色分配权限"""
    try:
        success = permission_service.assign_role_permissions(role_id, permission_ids)
        if success:
            # 清除所有缓存（因为角色权限变更影响所有用户）
            permission_cache.clear_all_cache()
        
        return success_response(message="角色权限分配成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/role/{role_id}/permissions/{permission_id}", response_model=BaseResponse)
def revoke_role_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """撤销角色权限"""
    try:
        success = permission_service.revoke_role_permission(role_id, permission_id)
        if success:
            # 清除所有缓存（因为角色权限变更影响所有用户）
            permission_cache.clear_all_cache()
        
        return success_response(message="角色权限撤销成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 权限检查API
@router.post("/check", response_model=BaseResponse)
def check_user_permission(
    permission_request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(get_current_active_user)
):
    """检查当前用户是否拥有指定权限"""
    try:
        # 解析权限字符串 (格式: "resource_type:action_type")
        if ':' in permission_request.permission:
            resource_type, action_type = permission_request.permission.split(':', 1)
        else:
            # 兼容旧格式
            resource_type = permission_request.permission
            action_type = 'read'
        
        # 使用缓存进行权限检查
        has_permission = permission_cache.check_user_permission(
            str(current_user.id), 
            resource_type,
            action_type,
            db=db
        )
        
        response_data = PermissionCheckResponse(
            has_permission=has_permission,
            permission=permission_request.permission,
            message="有权限" if has_permission else "无权限"
        )
        
        return success_response(
            data=response_data, 
            message=f"权限检查完成: {permission_request.permission}"
        )
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/check/batch", response_model=BaseResponse)
def check_user_permissions_batch(
    permissions: List[str],
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(get_current_active_user)
):
    """批量检查用户权限"""
    try:
        target_user_id = user_id if user_id else current_user.id
        
        # 如果检查其他用户权限，需要管理员权限
        if user_id and user_id != current_user.id:
            admin_permission = permission_service.check_user_permission(
                current_user.id, "user:read"
            )
            if not admin_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限检查其他用户权限"
                )
        
        # 将权限字符串转换为(resource_type, action_type)元组列表
        permission_checks = []
        for perm in permissions:
            if ':' in perm:
                resource_type, action_type = perm.split(':', 1)
                permission_checks.append((resource_type, action_type))
            else:
                # 如果没有冒号，假设是resource_type，action_type为read
                permission_checks.append((perm, 'read'))
        
        # 使用缓存进行批量权限检查
        permission_results = permission_cache.batch_check_permissions(
            str(target_user_id), permission_checks, db
        )
        
        return success_response(
            data=permission_results, 
            message="批量权限检查完成"
        )
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# 权限统计API
@router.get("/stats", response_model=BaseResponse)
def get_permission_stats(
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限统计信息"""
    try:
        stats = permission_service.get_permission_stats()
        return success_response(data=stats, message="获取权限统计信息成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

# 缓存管理API
@router.post("/cache/refresh", response_model=BaseResponse)
def refresh_permission_cache(
    user_id: Optional[int] = None,
    role_id: Optional[int] = None,
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """刷新权限缓存"""
    try:
        if user_id:
            # 刷新指定用户的权限缓存
            permission_cache.invalidate_user_cache(str(user_id))
            user_permissions = permission_service.get_user_permissions(user_id)
            message = f"用户 {user_id} 权限缓存刷新成功"
        elif role_id:
            # 刷新指定角色的权限缓存
            permission_cache.clear_all_cache()
            role_permissions = permission_service.get_role_permissions(role_id)
            message = f"角色 {role_id} 权限缓存刷新成功"
        else:
            # 刷新所有权限缓存
            permission_cache.clear_all_cache()
            message = "所有权限缓存刷新成功"
        
        return success_response(message=message)
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/cache/stats", response_model=BaseResponse)
def get_cache_stats(
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取权限缓存统计信息"""
    try:
        cache_stats = permission_cache.get_cache_stats()
        return success_response(data=cache_stats, message="获取缓存统计信息成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")


@router.post("/cache/redis/toggle", response_model=BaseResponse)
async def toggle_redis_cache(
    enabled: bool = True,
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_admin)
):
    """动态切换Redis缓存开关"""
    try:
        import os
        from utils.cache_manager import cache_manager
        
        # 更新环境变量
        os.environ["REDIS_ENABLED"] = str(enabled).lower()
        
        # 重新初始化缓存管理器
        if enabled:
            cache_manager._init_redis()
            # 重新创建权限缓存的Redis客户端
            permission_cache.redis_client = permission_cache._create_redis_client()
            message = "Redis缓存已启用"
        else:
            # 禁用Redis缓存
            cache_manager.enabled = False
            cache_manager.redis_client = None
            cache_manager.async_redis_client = None
            permission_cache.redis_client = None
            message = "Redis缓存已禁用，将仅使用本地内存缓存"
        
        return success_response(
            data={
                "redis_enabled": enabled,
                "cache_manager_enabled": cache_manager.enabled,
                "permission_cache_redis_available": permission_cache.redis_client is not None
            },
            message=message
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"切换Redis缓存开关失败: {str(e)}"
        )


@router.get("/cache/redis/status", response_model=BaseResponse)
async def get_redis_cache_status(
    permission_cache = Depends(get_permission_cache_dep),
    current_user: User = Depends(require_permission("system", "read"))
):
    """获取Redis缓存状态"""
    try:
        import os
        from utils.cache_manager import cache_manager
        
        redis_enabled_env = os.getenv("REDIS_ENABLED", "true").lower() == "true"
        
        return success_response(
            data={
                "redis_enabled_env": redis_enabled_env,
                "cache_manager_enabled": cache_manager.enabled,
                "cache_manager_redis_available": cache_manager.redis_client is not None,
                "permission_cache_redis_available": permission_cache.redis_client is not None,
                "redis_connection_test": await _test_redis_connection()
            },
            message="Redis缓存状态获取成功"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取Redis缓存状态失败: {str(e)}"
        )


async def _test_redis_connection():
    """测试Redis连接"""
    try:
        from utils.cache_manager import cache_manager
        from utils.permission_cache import get_permission_cache
        
        permission_cache = get_permission_cache()
        
        result = {
            "cache_manager": False,
            "permission_cache": False
        }
        
        # 测试cache_manager的Redis连接
        if cache_manager.redis_client:
            try:
                cache_manager.redis_client.ping()
                result["cache_manager"] = True
            except:
                pass
        
        # 测试permission_cache的Redis连接
        if permission_cache.redis_client:
            try:
                permission_cache.redis_client.ping()
                result["permission_cache"] = True
            except:
                pass
        
        return result
    except Exception:
        return {"cache_manager": False, "permission_cache": False}

# 权限模块API（兼容性保持）
@router.get("/modules", response_model=BaseResponse)
def get_permission_modules(
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service_dep),
    current_user: User = Depends(get_current_active_user)
):
    """获取权限模块列表（按模块分组的权限）"""
    try:
        modules = permission_service.get_permission_modules()
        return success_response(data=modules, message="获取权限模块列表成功")
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))