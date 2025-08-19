"""权限管理服务模块

提供权限相关的业务逻辑处理，包括权限CRUD操作、角色权限管理、权限检查等功能
"""
from typing import List, Optional, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, text
from datetime import datetime, timedelta
from enum import Enum

from models.permission import Permission, RolePermission, UserPermissionCache, role_permissions
from models.role import Role
from schemas.permission import (
    UserPermissionResponse, PermissionCheckRequest, PermissionCheckResponse,
    RolePermissionResponse, PermissionModule
)
from utils.exceptions import BusinessException, ResourceNotFoundException, ValidationException
from utils.status_codes import NOT_FOUND, VALIDATION_ERROR, CONFLICT, FORBIDDEN
from utils.cache_manager import cache_manager, cache, invalidate_cache
from utils.snowflake import generate_permission_id


class PermissionType(str, Enum):
    """权限类型枚举"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MANAGE = "manage"
    EXECUTE = "execute"
    APPROVE = "approve"


class ResourceType(str, Enum):
    """资源类型枚举"""
    USER = "user"
    ROLE = "role"
    PROJECT = "project"
    TASK = "task"
    DEFECT = "defect"
    DOCUMENT = "document"
    ORGANIZATION = "organization"
    SYSTEM = "system"


class PermissionService:
    """权限管理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.cache_expire_time = 300  # 缓存过期时间（秒）
    
    # ==================== 权限基础管理 ====================
    
    @invalidate_cache("permission_list")
    @invalidate_cache("active_permissions")
    def create_permission(self, permission_data: dict) -> Permission:
        """创建新权限
        
        Args:
            permission_data: 权限创建数据
            
        Returns:
            Permission: 创建的权限对象
            
        Raises:
            ValidationException: 当权限编码已存在时
        """
        # 检查权限编码是否已存在
        if self._is_permission_code_exists(permission_data.code):
            raise ValidationException("权限编码已存在", CONFLICT)
        
        # 创建新权限
        new_permission = Permission(
            code=permission_data.code,
            name=permission_data.name,
            description=permission_data.description,
            resource_type=permission_data.resource_type,
            action_type=permission_data.action_type,
            is_active=permission_data.is_active
        )
        
        self.db.add(new_permission)
        self.db.commit()
        self.db.refresh(new_permission)
        
        return new_permission
    
    @cache(expire=600, key_prefix="permission_detail")
    def get_permission_by_id(self, permission_id: str) -> Permission:
        """根据ID获取权限
        
        Args:
            permission_id: 权限ID
            
        Returns:
            Permission: 权限对象
            
        Raises:
            ResourceNotFoundException: 当权限不存在时
        """
        permission = self.db.query(Permission).filter(Permission.id == permission_id).first()
        if not permission:
            raise ResourceNotFoundException("权限不存在", NOT_FOUND)
        return permission
    
    @cache(expire=300, key_prefix="permission_list")
    def get_all_permissions(self, resource_type: Optional[str] = None, 
                          action_type: Optional[str] = None,
                          is_active: Optional[bool] = None) -> List[Permission]:
        """获取权限列表
        
        Args:
            resource_type: 资源类型过滤
            action_type: 操作类型过滤
            is_active: 激活状态过滤
            
        Returns:
            List[Permission]: 权限列表
        """
        query = self.db.query(Permission)
        
        if resource_type:
            query = query.filter(Permission.resource_type == resource_type)
        if action_type:
            query = query.filter(Permission.action_type == action_type)
        if is_active is not None:
            query = query.filter(Permission.is_active == is_active)
        
        return query.order_by(Permission.resource_type, Permission.action_type).all()
    
    @invalidate_cache("permission_list")
    @invalidate_cache("permission_detail")
    @invalidate_cache("active_permissions")
    def update_permission(self, permission_id: str, permission_data: dict) -> Permission:
        """更新权限信息
        
        Args:
            permission_id: 权限ID
            permission_data: 权限更新数据
            
        Returns:
            Permission: 更新后的权限对象
        """
        permission = self.get_permission_by_id(permission_id)
        
        # 检查权限编码是否已被其他权限使用
        if permission_data.code and permission_data.code != permission.code:
            if self._is_permission_code_exists(permission_data.code, exclude_id=permission_id):
                raise ValidationException("权限编码已存在", CONFLICT)
        
        # 更新权限信息
        update_data = permission_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(permission, field):
                setattr(permission, field, value)
        
        self.db.commit()
        self.db.refresh(permission)
        
        # 清除相关缓存
        self._clear_permission_cache(permission_id)
        
        return permission
    
    @invalidate_cache("permission_list")
    @invalidate_cache("permission_detail")
    @invalidate_cache("active_permissions")
    def delete_permission(self, permission_id: str) -> None:
        """删除权限
        
        Args:
            permission_id: 权限ID
            
        Raises:
            ValidationException: 当权限仍被角色使用时
        """
        permission = self.get_permission_by_id(permission_id)
        
        # 检查是否有角色正在使用该权限
        role_count = self.db.query(RolePermission).filter(
            RolePermission.permission_id == permission_id,
            RolePermission.is_granted == True
        ).count()
        
        if role_count > 0:
            raise ValidationException(
                f"无法删除权限，还有 {role_count} 个角色正在使用该权限",
                CONFLICT
            )
        
        self.db.delete(permission)
        self.db.commit()
        
        # 清除相关缓存
        self._clear_permission_cache(permission_id)
    
    # ==================== 角色权限管理 ====================
    
    @invalidate_cache("role_permissions")
    @invalidate_cache("user_permissions")
    def assign_permissions_to_role(self, role_id: str, permission_ids: List[str], 
                                 operator_id: str) -> List[RolePermission]:
        """为角色分配权限
        
        Args:
            role_id: 角色ID
            permission_ids: 权限ID列表
            operator_id: 操作人ID
            
        Returns:
            List[RolePermission]: 角色权限关联记录列表
        """
        # 验证角色存在
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ResourceNotFoundException("角色不存在", NOT_FOUND)
        
        # 验证权限存在
        permissions = self.db.query(Permission).filter(
            Permission.id.in_(permission_ids),
            Permission.is_active == True
        ).all()
        
        if len(permissions) != len(permission_ids):
            raise ValidationException("部分权限不存在或已禁用", VALIDATION_ERROR)
        
        role_permissions = []
        
        for permission_id in permission_ids:
            # 检查是否已存在权限分配记录
            existing = self.db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            ).first()
            
            if existing:
                # 如果已存在但被撤销，则重新授权
                if not existing.is_granted:
                    existing.is_granted = True
                    existing.granted_at = datetime.utcnow()
                    existing.granted_by = operator_id
                    existing.revoked_at = None
                    existing.revoked_by = None
                    role_permissions.append(existing)
            else:
                # 创建新的权限分配记录
                role_permission = RolePermission(
                    role_id=role_id,
                    permission_id=permission_id,
                    is_granted=True,
                    granted_at=datetime.utcnow(),
                    granted_by=operator_id
                )
                self.db.add(role_permission)
                role_permissions.append(role_permission)
        
        self.db.commit()
        
        # 清除相关用户权限缓存
        self._clear_role_users_permission_cache(role_id)
        
        return role_permissions
    
    @invalidate_cache("role_permissions")
    @invalidate_cache("user_permissions")
    def revoke_permissions_from_role(self, role_id: str, permission_ids: List[str], 
                                   operator_id: str) -> List[RolePermission]:
        """从角色撤销权限
        
        Args:
            role_id: 角色ID
            permission_ids: 权限ID列表
            operator_id: 操作人ID
            
        Returns:
            List[RolePermission]: 更新后的角色权限关联记录列表
        """
        # 查找现有的权限分配记录
        role_permissions = self.db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id.in_(permission_ids),
            RolePermission.is_granted == True
        ).all()
        
        if not role_permissions:
            raise ResourceNotFoundException("未找到要撤销的权限分配记录", NOT_FOUND)
        
        # 撤销权限
        for role_permission in role_permissions:
            role_permission.is_granted = False
            role_permission.revoked_at = datetime.utcnow()
            role_permission.revoked_by = operator_id
        
        self.db.commit()
        
        # 清除相关用户权限缓存
        self._clear_role_users_permission_cache(role_id)
        
        return role_permissions
    
    @cache(expire=300, key_prefix="role_permissions")
    def get_role_permissions(self, role_id: str, include_inactive: bool = False) -> List[Permission]:
        """获取角色的所有权限
        
        Args:
            role_id: 角色ID
            include_inactive: 是否包含非激活权限
            
        Returns:
            List[Permission]: 权限列表
        """
        query = self.db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).filter(
            RolePermission.role_id == role_id,
            RolePermission.is_granted == True
        )
        
        if not include_inactive:
            query = query.filter(Permission.is_active == True)
        
        return query.order_by(Permission.resource_type, Permission.action_type).all()
    
    def get_roles_by_permission(self, permission_id: str) -> List[Role]:
        """获取拥有指定权限的所有角色
        
        Args:
            permission_id: 权限ID
            
        Returns:
            List[Role]: 角色列表
        """
        return self.db.query(Role).join(
            RolePermission, Role.id == RolePermission.role_id
        ).filter(
            RolePermission.permission_id == permission_id,
            RolePermission.is_granted == True,
            Role.is_active == True
        ).all()
    
    # ==================== 用户权限查询 ====================
    
    @cache(expire=300, key_prefix="user_permissions")
    def get_user_permissions(self, user_id: str, resource_type: Optional[str] = None) -> List[Permission]:
        """获取用户的所有权限（通过角色继承）
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型过滤
            
        Returns:
            List[Permission]: 权限列表
        """
        # 先尝试从缓存获取
        cached_permissions = self._get_cached_user_permissions(user_id)
        if cached_permissions:
            permissions = cached_permissions
        else:
            # 从数据库查询并缓存
            permissions = self._query_user_permissions_from_db(user_id)
            self._cache_user_permissions(user_id, permissions)
        
        # 按资源类型过滤
        if resource_type:
            permissions = [p for p in permissions if p.resource_type == resource_type]
        
        return permissions
    
    def check_user_permission(self, user_id: str, resource_type: str, 
                            action_type: str, resource_id: Optional[str] = None) -> bool:
        """检查用户是否具有指定权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            action_type: 操作类型
            resource_id: 资源ID（可选，用于资源级权限控制）
            
        Returns:
            bool: 是否具有权限
        """
        # 获取用户权限
        user_permissions = self.get_user_permissions(user_id, resource_type)
        
        # 检查是否有匹配的权限
        for permission in user_permissions:
            if permission.matches(resource_type, action_type):
                # 如果需要资源级权限控制，在这里添加额外检查
                if resource_id:
                    # 可以扩展为更复杂的资源级权限检查逻辑
                    pass
                return True
        
        return False
    
    def get_user_accessible_resources(self, user_id: str, resource_type: str, 
                                    action_type: str) -> List[str]:
        """获取用户可访问的资源ID列表
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            action_type: 操作类型
            
        Returns:
            List[str]: 可访问的资源ID列表
        """
        # 检查用户是否有该类型资源的权限
        if not self.check_user_permission(user_id, resource_type, action_type):
            return []
        
        # 这里可以根据具体业务逻辑返回用户可访问的资源列表
        # 目前返回空列表，表示需要根据具体业务实现
        return []
    
    # ==================== 权限缓存管理 ====================
    
    def _get_cached_user_permissions(self, user_id: str) -> Optional[List[Permission]]:
        """从缓存获取用户权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[List[Permission]]: 缓存的权限列表，如果不存在或已过期则返回None
        """
        cache_record = self.db.query(UserPermissionCache).filter(
            UserPermissionCache.user_id == user_id
        ).first()
        
        if cache_record and not cache_record.is_expired():
            # 解析缓存的权限ID列表
            permission_ids = cache_record.permission_ids.split(',') if cache_record.permission_ids else []
            if permission_ids:
                return self.db.query(Permission).filter(
                    Permission.id.in_(permission_ids),
                    Permission.is_active == True
                ).all()
        
        return None
    
    def _cache_user_permissions(self, user_id: str, permissions: List[Permission]) -> None:
        """缓存用户权限
        
        Args:
            user_id: 用户ID
            permissions: 权限列表
        """
        permission_ids = ','.join([p.id for p in permissions])
        
        # 查找现有缓存记录
        cache_record = self.db.query(UserPermissionCache).filter(
            UserPermissionCache.user_id == user_id
        ).first()
        
        if cache_record:
            # 更新现有记录
            cache_record.permission_ids = permission_ids
            cache_record.cached_at = datetime.utcnow()
            cache_record.expires_at = datetime.utcnow() + timedelta(seconds=self.cache_expire_time)
        else:
            # 创建新记录
            cache_record = UserPermissionCache(
                user_id=user_id,
                permission_ids=permission_ids,
                cached_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=self.cache_expire_time)
            )
            self.db.add(cache_record)
        
        self.db.commit()
    
    def _query_user_permissions_from_db(self, user_id: str) -> List[Permission]:
        """从数据库查询用户权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Permission]: 权限列表
        """
        from models.user import User  # 避免循环导入
        return self.db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).join(
            Role, RolePermission.role_id == Role.id
        ).join(
            User, Role.id == User.role_id
        ).filter(
            User.id == user_id,
            RolePermission.is_granted == True,
            Permission.is_active == True,
            Role.is_active == True,
            User.is_active == True
        ).distinct().all()
    
    def _clear_permission_cache(self, permission_id: str) -> None:
        """清除权限相关缓存
        
        Args:
            permission_id: 权限ID
        """
        # 清除所有用户权限缓存（因为权限变更可能影响所有用户）
        self.db.query(UserPermissionCache).delete()
        self.db.commit()
    
    def _clear_role_users_permission_cache(self, role_id: str) -> None:
        """清除角色下所有用户的权限缓存
        
        Args:
            role_id: 角色ID
        """
        from models.user import User  # 避免循环导入
        # 获取该角色下的所有用户
        user_ids = self.db.query(User.id).filter(User.role_id == role_id).all()
        user_id_list = [user_id[0] for user_id in user_ids]
        
        if user_id_list:
            # 删除这些用户的权限缓存
            self.db.query(UserPermissionCache).filter(
                UserPermissionCache.user_id.in_(user_id_list)
            ).delete(synchronize_session=False)
            self.db.commit()
    
    def clear_expired_cache(self) -> int:
        """清除过期的权限缓存
        
        Returns:
            int: 清除的记录数量
        """
        expired_count = self.db.query(UserPermissionCache).filter(
            UserPermissionCache.expires_at < datetime.utcnow()
        ).count()
        
        self.db.query(UserPermissionCache).filter(
            UserPermissionCache.expires_at < datetime.utcnow()
        ).delete()
        
        self.db.commit()
        return expired_count
    
    # ==================== 权限统计和分析 ====================
    
    def get_permission_stats(self) -> Dict[str, Any]:
        """获取权限统计信息
        
        Returns:
            Dict[str, Any]: 权限统计数据
        """
        # 基础统计
        total_permissions = self.db.query(func.count(Permission.id)).scalar() or 0
        active_permissions = self.db.query(func.count(Permission.id)).filter(
            Permission.is_active == True
        ).scalar() or 0
        
        # 按资源类型统计
        resource_stats = self.db.query(
            Permission.resource_type,
            func.count(Permission.id).label('count')
        ).group_by(Permission.resource_type).all()
        
        # 按操作类型统计
        action_stats = self.db.query(
            Permission.action_type,
            func.count(Permission.id).label('count')
        ).group_by(Permission.action_type).all()
        
        # 角色权限分配统计
        role_permission_stats = self.db.query(
            func.count(func.distinct(RolePermission.role_id)).label('roles_with_permissions'),
            func.count(RolePermission.id).label('total_assignments')
        ).filter(RolePermission.is_granted == True).first()
        
        return {
            "total_permissions": total_permissions,
            "active_permissions": active_permissions,
            "inactive_permissions": total_permissions - active_permissions,
            "resource_type_distribution": {stat.resource_type: stat.count for stat in resource_stats},
            "action_type_distribution": {stat.action_type: stat.count for stat in action_stats},
            "roles_with_permissions": role_permission_stats.roles_with_permissions or 0,
            "total_role_permission_assignments": role_permission_stats.total_assignments or 0
        }
    
    def get_role_permission_matrix(self) -> Dict[str, List[str]]:
        """获取角色权限矩阵
        
        Returns:
            Dict[str, List[str]]: 角色ID到权限编码列表的映射
        """
        results = self.db.query(
            Role.id,
            Role.name,
            Permission.code
        ).join(
            RolePermission, Role.id == RolePermission.role_id
        ).join(
            Permission, RolePermission.permission_id == Permission.id
        ).filter(
            RolePermission.is_granted == True,
            Role.is_active == True,
            Permission.is_active == True
        ).all()
        
        matrix = {}
        for role_id, role_name, permission_code in results:
            if role_id not in matrix:
                matrix[role_id] = {
                    "role_name": role_name,
                    "permissions": []
                }
            matrix[role_id]["permissions"].append(permission_code)
        
        return matrix
    
    # ==================== 辅助方法 ====================
    
    def _is_permission_code_exists(self, code: str, exclude_id: Optional[str] = None) -> bool:
        """检查权限编码是否已存在
        
        Args:
            code: 权限编码
            exclude_id: 排除的权限ID（用于更新时检查）
            
        Returns:
            bool: 是否存在
        """
        query = self.db.query(Permission).filter(Permission.code == code)
        if exclude_id:
            query = query.filter(Permission.id != exclude_id)
        return query.first() is not None
    
    @cache(expire=600, key_prefix="active_permissions")
    def get_active_permissions(self) -> List[Permission]:
        """获取所有激活状态的权限
        
        Returns:
            List[Permission]: 激活的权限列表
        """
        return self.db.query(Permission).filter(Permission.is_active == True).all()
    
    def batch_check_permissions(self, user_id: str, 
                              permission_checks: List[Tuple[str, str]]) -> Dict[str, bool]:
        """批量检查用户权限
        
        Args:
            user_id: 用户ID
            permission_checks: 权限检查列表，每个元素为(resource_type, action_type)元组
            
        Returns:
            Dict[str, bool]: 权限检查结果，key为"resource_type:action_type"格式
        """
        user_permissions = self.get_user_permissions(user_id)
        results = {}
        
        for resource_type, action_type in permission_checks:
            key = f"{resource_type}:{action_type}"
            results[key] = any(
                p.matches(resource_type, action_type) for p in user_permissions
            )
        
        return results


    def get_permissions_paginated(
        self,
        page: int,
        limit: int,
        query: Optional[str] = None,
        resource_type: Optional[str] = None,
        action_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Tuple[List[Permission], int]:
        """分页获取权限列表

        Args:
            page: 页码
            limit: 每页大小
            query: 搜索关键字
            resource_type: 资源类型过滤
            action_type: 操作类型过滤
            is_active: 激活状态过滤
            start_time: 创建时间范围开始
            end_time: 创建时间范围结束

        Returns:
            Tuple[List[Permission], int]: 权限列表和总数
        """
        q = self.db.query(Permission)

        if query:
            q = q.filter(or_(
                Permission.name.ilike(f"%{query}%"),
                Permission.code.ilike(f"%{query}%"),
                Permission.description.ilike(f"%{query}%")
            ))
        if resource_type:
            q = q.filter(Permission.resource_type == resource_type)
        if action_type:
            q = q.filter(Permission.action_type == action_type)
        if is_active is not None:
            q = q.filter(Permission.is_active == is_active)
        if start_time:
            q = q.filter(Permission.created_at >= start_time)
        if end_time:
            q = q.filter(Permission.created_at <= end_time)

        total_count = q.count()
        permissions = q.order_by(Permission.created_at.desc())\
                       .offset((page - 1) * limit)\
                       .limit(limit)\
                       .all()

        return permissions, total_count

    @invalidate_cache("role_permissions")
    def get_role_permissions(self, role_id: str, include_inactive: bool = False) -> List[Permission]:
        """获取角色的所有权限
        
        Args:
            role_id: 角色ID
            include_inactive: 是否包含非激活权限
            
        Returns:
            List[Permission]: 权限列表
        """
        query = self.db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).filter(
            RolePermission.role_id == role_id,
            RolePermission.is_granted == True
        )
        
        if not include_inactive:
            query = query.filter(Permission.is_active == True)
        
        return query.order_by(Permission.resource_type, Permission.action_type).all()
    
    def get_roles_by_permission(self, permission_id: str) -> List[Role]:
        """获取拥有指定权限的所有角色
        
        Args:
            permission_id: 权限ID
            
        Returns:
            List[Role]: 角色列表
        """
        return self.db.query(Role).join(
            RolePermission, Role.id == RolePermission.role_id
        ).filter(
            RolePermission.permission_id == permission_id,
            RolePermission.is_granted == True,
            Role.is_active == True
        ).all()
    
    # ==================== 用户权限查询 ====================
    
    @cache(expire=300, key_prefix="user_permissions")
    def get_user_permissions(self, user_id: str, resource_type: Optional[str] = None) -> List[Permission]:
        """获取用户的所有权限（通过角色继承）
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型过滤
            
        Returns:
            List[Permission]: 权限列表
        """
        # 先尝试从缓存获取
        cached_permissions = self._get_cached_user_permissions(user_id)
        if cached_permissions:
            permissions = cached_permissions
        else:
            # 从数据库查询并缓存
            permissions = self._query_user_permissions_from_db(user_id)
            self._cache_user_permissions(user_id, permissions)
        
        # 按资源类型过滤
        if resource_type:
            permissions = [p for p in permissions if p.resource_type == resource_type]
        
        return permissions
    
    def check_user_permission(self, user_id: str, resource_type: str, 
                            action_type: str, resource_id: Optional[str] = None) -> bool:
        """检查用户是否具有指定权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            action_type: 操作类型
            resource_id: 资源ID（可选，用于资源级权限控制）
            
        Returns:
            bool: 是否具有权限
        """
        # 获取用户权限
        user_permissions = self.get_user_permissions(user_id, resource_type)
        
        # 检查是否有匹配的权限
        for permission in user_permissions:
            if permission.matches(resource_type, action_type):
                # 如果需要资源级权限控制，在这里添加额外检查
                if resource_id:
                    # 可以扩展为更复杂的资源级权限检查逻辑
                    pass
                return True
        
        return False
    
    def get_user_accessible_resources(self, user_id: str, resource_type: str, 
                                    action_type: str) -> List[str]:
        """获取用户可访问的资源ID列表
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            action_type: 操作类型
            
        Returns:
            List[str]: 可访问的资源ID列表
        """
        # 检查用户是否有该类型资源的权限
        if not self.check_user_permission(user_id, resource_type, action_type):
            return []
        
        # 这里可以根据具体业务逻辑返回用户可访问的资源列表
        # 目前返回空列表，表示需要根据具体业务实现
        return []
    
    # ==================== 权限缓存管理 ====================
    
    def _get_cached_user_permissions(self, user_id: str) -> Optional[List[Permission]]:
        """从缓存获取用户权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[List[Permission]]: 缓存的权限列表，如果不存在或已过期则返回None
        """
        cache_record = self.db.query(UserPermissionCache).filter(
            UserPermissionCache.user_id == user_id
        ).first()
        
        if cache_record and not cache_record.is_expired():
            # 解析缓存的权限ID列表
            permission_ids = cache_record.permission_ids.split(',') if cache_record.permission_ids else []
            if permission_ids:
                return self.db.query(Permission).filter(
                    Permission.id.in_(permission_ids),
                    Permission.is_active == True
                ).all()
        
        return None
    
    def _cache_user_permissions(self, user_id: str, permissions: List[Permission]) -> None:
        """缓存用户权限
        
        Args:
            user_id: 用户ID
            permissions: 权限列表
        """
        permission_ids = ','.join([p.id for p in permissions])
        
        # 查找现有缓存记录
        cache_record = self.db.query(UserPermissionCache).filter(
            UserPermissionCache.user_id == user_id
        ).first()
        
        if cache_record:
            # 更新现有记录
            cache_record.permission_ids = permission_ids
            cache_record.cached_at = datetime.utcnow()
            cache_record.expires_at = datetime.utcnow() + timedelta(seconds=self.cache_expire_time)
        else:
            # 创建新记录
            cache_record = UserPermissionCache(
                user_id=user_id,
                permission_ids=permission_ids,
                cached_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=self.cache_expire_time)
            )
            self.db.add(cache_record)
        
        self.db.commit()
    
    def _query_user_permissions_from_db(self, user_id: str) -> List[Permission]:
        """从数据库查询用户权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Permission]: 权限列表
        """
        from models.user import User  # 避免循环导入
        return self.db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).join(
            Role, RolePermission.role_id == Role.id
        ).join(
            User, Role.id == User.role_id
        ).filter(
            User.id == user_id,
            RolePermission.is_granted == True,
            Permission.is_active == True,
            Role.is_active == True,
            User.is_active == True
        ).distinct().all()
    
    def _clear_permission_cache(self, permission_id: str) -> None:
        """清除权限相关缓存
        
        Args:
            permission_id: 权限ID
        """
        # 清除所有用户权限缓存（因为权限变更可能影响所有用户）
        self.db.query(UserPermissionCache).delete()
        self.db.commit()
    
    def _clear_role_users_permission_cache(self, role_id: str) -> None:
        """清除角色下所有用户的权限缓存
        
        Args:
            role_id: 角色ID
        """
        from models.user import User  # 避免循环导入
        # 获取该角色下的所有用户
        user_ids = self.db.query(User.id).filter(User.role_id == role_id).all()
        user_id_list = [user_id[0] for user_id in user_ids]
        
        if user_id_list:
            # 删除这些用户的权限缓存
            self.db.query(UserPermissionCache).filter(
                UserPermissionCache.user_id.in_(user_id_list)
            ).delete(synchronize_session=False)
            self.db.commit()
    
    def clear_expired_cache(self) -> int:
        """清除过期的权限缓存
        
        Returns:
            int: 清除的记录数量
        """
        expired_count = self.db.query(UserPermissionCache).filter(
            UserPermissionCache.expires_at < datetime.utcnow()
        ).count()
        
        self.db.query(UserPermissionCache).filter(
            UserPermissionCache.expires_at < datetime.utcnow()
        ).delete()
        
        self.db.commit()
        return expired_count
    
    # ==================== 权限统计和分析 ====================
    
    def get_permission_stats(self) -> Dict[str, Any]:
        """获取权限统计信息
        
        Returns:
            Dict[str, Any]: 权限统计数据
        """
        # 基础统计
        total_permissions = self.db.query(func.count(Permission.id)).scalar() or 0
        active_permissions = self.db.query(func.count(Permission.id)).filter(
            Permission.is_active == True
        ).scalar() or 0
        
        # 按资源类型统计
        resource_stats = self.db.query(
            Permission.resource_type,
            func.count(Permission.id).label('count')
        ).group_by(Permission.resource_type).all()
        
        # 按操作类型统计
        action_stats = self.db.query(
            Permission.action_type,
            func.count(Permission.id).label('count')
        ).group_by(Permission.action_type).all()
        
        # 角色权限分配统计
        role_permission_stats = self.db.query(
            func.count(func.distinct(RolePermission.role_id)).label('roles_with_permissions'),
            func.count(RolePermission.id).label('total_assignments')
        ).filter(RolePermission.is_granted == True).first()
        
        return {
            "total_permissions": total_permissions,
            "active_permissions": active_permissions,
            "inactive_permissions": total_permissions - active_permissions,
            "resource_type_distribution": {stat.resource_type: stat.count for stat in resource_stats},
            "action_type_distribution": {stat.action_type: stat.count for stat in action_stats},
            "roles_with_permissions": role_permission_stats.roles_with_permissions or 0,
            "total_role_permission_assignments": role_permission_stats.total_assignments or 0
        }
    
    def get_role_permission_matrix(self) -> Dict[str, List[str]]:
        """获取角色权限矩阵
        
        Returns:
            Dict[str, List[str]]: 角色ID到权限编码列表的映射
        """
        results = self.db.query(
            Role.id,
            Role.name,
            Permission.code
        ).join(
            RolePermission, Role.id == RolePermission.role_id
        ).join(
            Permission, RolePermission.permission_id == Permission.id
        ).filter(
            RolePermission.is_granted == True,
            Role.is_active == True,
            Permission.is_active == True
        ).all()
        
        matrix = {}
        for role_id, role_name, permission_code in results:
            if role_id not in matrix:
                matrix[role_id] = {
                    "role_name": role_name,
                    "permissions": []
                }
            matrix[role_id]["permissions"].append(permission_code)
        
        return matrix
    
    # ==================== 辅助方法 ====================
    
    def _is_permission_code_exists(self, code: str, exclude_id: Optional[str] = None) -> bool:
        """检查权限编码是否已存在
        
        Args:
            code: 权限编码
            exclude_id: 排除的权限ID（用于更新时检查）
            
        Returns:
            bool: 是否存在
        """
        query = self.db.query(Permission).filter(Permission.code == code)
        if exclude_id:
            query = query.filter(Permission.id != exclude_id)
        return query.first() is not None
    
    @cache(expire=600, key_prefix="active_permissions")
    def get_active_permissions(self) -> List[Permission]:
        """获取所有激活状态的权限
        
        Returns:
            List[Permission]: 激活的权限列表
        """
        return self.db.query(Permission).filter(Permission.is_active == True).all()
    
    def batch_check_permissions(self, user_id: str, 
                              permission_checks: List[Tuple[str, str]]) -> Dict[str, bool]:
        """批量检查用户权限
        
        Args:
            user_id: 用户ID
            permission_checks: 权限检查列表，每个元素为(resource_type, action_type)元组
            
        Returns:
            Dict[str, bool]: 权限检查结果，key为"resource_type:action_type"格式
        """
        user_permissions = self.get_user_permissions(user_id)
        results = {}
        
        for resource_type, action_type in permission_checks:
            key = f"{resource_type}:{action_type}"
            results[key] = any(
                p.matches(resource_type, action_type) for p in user_permissions
            )
        
        return results


def get_permission_service(db: Session) -> PermissionService:
    """获取权限服务实例
    
    Args:
        db: 数据库会话
        
    Returns:
        PermissionService: 权限服务实例
    """
    return PermissionService(db)