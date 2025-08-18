"""角色管理服务模块

提供角色相关的业务逻辑处理，包括角色CRUD操作、权限管理等功能
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime

from models.role import Role
from models.user import User
from schemas.role import RoleCreate, RoleUpdate, RoleResponse, RoleListResponse
from utils.exceptions import BusinessException, ResourceNotFoundException, ValidationException
from utils.status_codes import NOT_FOUND, VALIDATION_ERROR, CONFLICT
from utils.cache_manager import cache_manager, cache, invalidate_cache


class RoleService:
    """角色管理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @invalidate_cache("role_list")
    @invalidate_cache("active_roles")
    @invalidate_cache("role_stats")
    def create_role(self, role_data: RoleCreate) -> Role:
        """创建新角色
        
        Args:
            role_data: 角色创建数据
            
        Returns:
            Role: 创建的角色对象
            
        Raises:
            ValidationException: 当角色编码或名称已存在时
        """
        # 检查角色编码是否已存在
        if self._is_code_exists(role_data.code):
            raise ValidationException("角色编码已存在", CONFLICT)
        
        # 检查角色名称是否已存在
        if self._is_name_exists(role_data.name):
            raise ValidationException("角色名称已存在", CONFLICT)
        
        # 创建新角色
        new_role = Role(
            code=role_data.code,
            name=role_data.name,
            description=role_data.description,
            is_active=role_data.is_active
        )
        
        self.db.add(new_role)
        self.db.commit()
        self.db.refresh(new_role)
        
        return new_role
    
    @cache(expire=600, key_prefix="role_detail")
    def get_role_by_id(self, role_id: str) -> Role:
        """根据ID获取角色
        
        Args:
            role_id: 角色ID
            
        Returns:
            Role: 角色对象
            
        Raises:
            ResourceNotFoundException: 当角色不存在时
        """
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ResourceNotFoundException("角色不存在", NOT_FOUND)
        return role
    
    @cache(expire=300, key_prefix="role_list")
    def get_all_roles(self) -> List[Dict[str, Any]]:
        """获取所有角色列表，包含用户数量统计
        
        Returns:
            List[Dict]: 角色列表，包含用户数量
        """
        # 使用子查询优化用户数量统计，避免N+1查询问题
        user_count_subquery = (
            self.db.query(
                User.role_id,
                func.count(User.id).label('user_count')
            )
            .group_by(User.role_id)
            .subquery()
        )
        
        # 左连接获取角色和用户数量
        roles_with_count = (
            self.db.query(
                Role,
                func.coalesce(user_count_subquery.c.user_count, 0).label('user_count')
            )
            .outerjoin(user_count_subquery, Role.id == user_count_subquery.c.role_id)
            .all()
        )
        
        # 构建响应数据
        role_list = []
        for role, user_count in roles_with_count:
            role_data = RoleListResponse.model_validate(role).model_dump()
            role_data["user_count"] = user_count
            role_list.append(role_data)
        
        return role_list
    
    @cache(expire=180, key_prefix="role_stats")
    def get_role_stats(self) -> Dict[str, int]:
        """获取角色统计信息
        
        Returns:
            Dict[str, int]: 角色统计数据
        """
        # 系统角色编码列表
        system_role_codes = ['ADMIN', 'USER', 'MANAGER', 'VIEWER', 'EDITOR']
        
        # 使用单次查询获取所有统计数据，避免多次数据库访问
        stats_query = self.db.query(
            func.count(Role.id).label('total_roles'),
            func.sum(func.case([(Role.is_active == True, 1)], else_=0)).label('active_roles'),
            func.sum(func.case([(Role.code.in_(system_role_codes), 1)], else_=0)).label('system_roles')
        ).first()
        
        total_roles = stats_query.total_roles or 0
        active_roles = stats_query.active_roles or 0
        system_roles = stats_query.system_roles or 0
        
        # 自定义角色数
        custom_roles = total_roles - system_roles
        
        return {
            "total_roles": total_roles,
            "active_roles": active_roles,
            "system_roles": system_roles,
            "custom_roles": custom_roles
        }
    
    @invalidate_cache("role_list")
    @invalidate_cache("role_detail")
    @invalidate_cache("active_roles")
    @invalidate_cache("role_stats")
    @invalidate_cache("roles_by_codes")
    def update_role(self, role_id: str, role_data: RoleUpdate) -> Role:
        """更新角色信息
        
        Args:
            role_id: 角色ID
            role_data: 角色更新数据
            
        Returns:
            Role: 更新后的角色对象
            
        Raises:
            ResourceNotFoundException: 当角色不存在时
            ValidationException: 当角色编码或名称冲突时
        """
        role = self.get_role_by_id(role_id)
        
        # 检查角色编码是否已被其他角色使用
        if role_data.code and role_data.code != role.code:
            if self._is_code_exists(role_data.code, exclude_id=role_id):
                raise ValidationException("角色编码已存在", CONFLICT)
        
        # 检查角色名称是否已被其他角色使用
        if role_data.name and role_data.name != role.name:
            if self._is_name_exists(role_data.name, exclude_id=role_id):
                raise ValidationException("角色名称已存在", CONFLICT)
        
        # 更新角色信息
        update_data = role_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(role, field):
                setattr(role, field, value)
        
        self.db.commit()
        self.db.refresh(role)
        
        return role
    
    @invalidate_cache("role_list")
    @invalidate_cache("role_detail")
    @invalidate_cache("active_roles")
    @invalidate_cache("role_stats")
    @invalidate_cache("roles_by_codes")
    def delete_role(self, role_id: str) -> None:
        """删除角色
        
        Args:
            role_id: 角色ID
            
        Raises:
            ResourceNotFoundException: 当角色不存在时
            ValidationException: 当角色仍被用户使用时
        """
        role = self.get_role_by_id(role_id)
        
        # 检查是否有用户正在使用该角色
        user_count = self.db.query(User).filter(User.role_id == role_id).count()
        if user_count > 0:
            raise ValidationException(
                f"无法删除角色，还有 {user_count} 个用户正在使用该角色",
                CONFLICT
            )
        
        self.db.delete(role)
        self.db.commit()
    
    @cache(expire=600, key_prefix="roles_by_codes")
    def get_roles_by_codes(self, codes: List[str]) -> List[Role]:
        """根据角色编码列表获取角色
        
        Args:
            codes: 角色编码列表
            
        Returns:
            List[Role]: 角色列表
        """
        if not codes:
            return []
        
        # 使用索引优化的批量查询
        return self.db.query(Role).filter(Role.code.in_(codes)).all()
    
    def get_roles_by_ids(self, role_ids: List[str]) -> List[Role]:
        """根据角色ID列表批量获取角色
        
        Args:
            role_ids: 角色ID列表
            
        Returns:
            List[Role]: 角色列表
        """
        if not role_ids:
            return []
        
        return self.db.query(Role).filter(Role.id.in_(role_ids)).all()
    
    def get_roles_with_user_counts(self, role_ids: List[str] = None) -> List[Dict]:
        """获取角色及其用户数量（优化版本）
        
        Args:
            role_ids: 可选的角色ID列表，如果提供则只查询指定角色
            
        Returns:
            List[Dict]: 包含角色信息和用户数量的字典列表
        """
        # 构建基础查询
        query = self.db.query(
            Role,
            func.count(User.id).label('user_count')
        ).outerjoin(User, Role.id == User.role_id)
        
        # 如果指定了角色ID，则添加过滤条件
        if role_ids:
            query = query.filter(Role.id.in_(role_ids))
        
        # 按角色分组
        results = query.group_by(Role.id).all()
        
        # 构建返回数据
        role_list = []
        for role, user_count in results:
            role_data = RoleListResponse.model_validate(role).model_dump()
            role_data["user_count"] = user_count or 0
            role_list.append(role_data)
        
        return role_list
    
    @cache(expire=600, key_prefix="active_roles")
    def get_active_roles(self) -> List[Role]:
        """获取所有激活状态的角色
        
        Returns:
            List[Role]: 激活的角色列表
        """
        return self.db.query(Role).filter(Role.is_active == True).all()
    
    @invalidate_cache("role_list")
    @invalidate_cache("role_detail")
    @invalidate_cache("active_roles")
    @invalidate_cache("role_stats")
    def toggle_role_status(self, role_id: str) -> Role:
        """切换角色激活状态
        
        Args:
            role_id: 角色ID
            
        Returns:
            Role: 更新后的角色对象
        """
        role = self.get_role_by_id(role_id)
        role.is_active = not role.is_active
        
        self.db.commit()
        self.db.refresh(role)
        
        return role
    
    def _is_code_exists(self, code: str, exclude_id: Optional[str] = None) -> bool:
        """检查角色编码是否已存在
        
        Args:
            code: 角色编码
            exclude_id: 排除的角色ID（用于更新时检查）
            
        Returns:
            bool: 是否存在
        """
        query = self.db.query(Role).filter(Role.code == code)
        if exclude_id:
            query = query.filter(Role.id != exclude_id)
        return query.first() is not None
    
    def _is_name_exists(self, name: str, exclude_id: Optional[str] = None) -> bool:
        """检查角色名称是否已存在
        
        Args:
            name: 角色名称
            exclude_id: 排除的角色ID（用于更新时检查）
            
        Returns:
            bool: 是否存在
        """
        query = self.db.query(Role).filter(Role.name == name)
        if exclude_id:
            query = query.filter(Role.id != exclude_id)
        return query.first() is not None


def get_role_service(db: Session) -> RoleService:
    """获取角色服务实例
    
    Args:
        db: 数据库会话
        
    Returns:
        RoleService: 角色服务实例
    """
    return RoleService(db)