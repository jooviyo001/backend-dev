"""权限管理相关数据模型
包含权限、角色权限关联等数据模型定义
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from utils.snowflake import generate_permission_id
from models.base import BaseModelMixin


# 角色权限关联表（多对多关系）
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', String(25), ForeignKey('roles.id'), primary_key=True, comment='角色ID'),
    Column('permission_id', String(25), ForeignKey('permissions.id'), primary_key=True, comment='权限ID'),
    Column('created_at', DateTime, default=func.now(), comment='关联创建时间'),
    Column('created_by', String(25), comment='创建人ID')
)


class Permission(Base, BaseModelMixin):
    """权限表模型
    
    用于存储系统中的所有权限信息
    包括权限ID、权限编码、权限名称、权限描述、资源类型、操作类型等
    """
    __tablename__ = "permissions"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_permission_id, comment='权限ID，格式：P + 雪花算法ID')
    code = Column(String(100), nullable=False, unique=True, index=True, comment='权限编码，格式：resource:action')
    name = Column(String(100), nullable=False, comment='权限名称')
    description = Column(Text, comment='权限描述')
    resource = Column(String(50), nullable=False, index=True, comment='资源类型（如：user、project、task等）')
    action = Column(String(50), nullable=False, index=True, comment='操作类型（如：read、write、delete等）')
    module = Column(String(50), nullable=False, index=True, comment='所属模块')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关联关系
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions", lazy="dynamic")
    
    def __init__(self, code: str, name: str, resource: str, action: str, module: str, 
                 description: str = None, is_active: bool = True):
        self.code = code
        self.name = name
        self.resource = resource
        self.action = action
        self.module = module
        self.description = description
        self.is_active = is_active
    
    def __repr__(self):
        return f"<Permission(id={self.id}, code={self.code}, name={self.name}, resource={self.resource}, action={self.action})>"
    
    def __str__(self):
        return f"{self.name}({self.code})"
    
    def __eq__(self, other):
        if not isinstance(other, Permission):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)
    
    @property
    def full_code(self):
        """获取完整权限编码"""
        return f"{self.resource}:{self.action}"
    
    def is_match(self, resource: str, action: str) -> bool:
        """检查权限是否匹配指定的资源和操作"""
        return self.resource == resource and self.action == action


class RolePermission(Base, BaseModelMixin):
    """角色权限关联表模型
    
    用于记录角色权限分配的详细信息和历史
    """
    __tablename__ = "role_permission_logs"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_permission_id, comment='记录ID')
    role_id = Column(String(25), ForeignKey('roles.id'), nullable=False, index=True, comment='角色ID')
    permission_id = Column(String(25), ForeignKey('permissions.id'), nullable=False, index=True, comment='权限ID')
    action_type = Column(String(20), nullable=False, comment='操作类型：grant（授权）、revoke（撤销）')
    granted_by = Column(String(25), ForeignKey('users.id'), comment='授权人ID')
    granted_at = Column(DateTime, default=func.now(), comment='授权时间')
    revoked_by = Column(String(25), ForeignKey('users.id'), comment='撤销人ID')
    revoked_at = Column(DateTime, comment='撤销时间')
    reason = Column(Text, comment='操作原因')
    is_active = Column(Boolean, default=True, comment='是否有效')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关联关系
    role = relationship("Role", backref="permission_logs")
    permission = relationship("Permission", backref="role_logs")
    granter = relationship("User", foreign_keys=[granted_by], backref="granted_permissions")
    revoker = relationship("User", foreign_keys=[revoked_by], backref="revoked_permissions")
    
    def __init__(self, role_id: str, permission_id: str, action_type: str, 
                 granted_by: str = None, reason: str = None):
        self.role_id = role_id
        self.permission_id = permission_id
        self.action_type = action_type
        self.granted_by = granted_by
        self.reason = reason
        self.is_active = action_type == 'grant'
    
    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id}, action={self.action_type})>"
    
    def grant(self, granted_by: str, reason: str = None):
        """授权"""
        self.action_type = 'grant'
        self.granted_by = granted_by
        self.granted_at = func.now()
        self.reason = reason
        self.is_active = True
        self.updated_at = func.now()
    
    def revoke(self, revoked_by: str, reason: str = None):
        """撤销权限"""
        self.action_type = 'revoke'
        self.revoked_by = revoked_by
        self.revoked_at = func.now()
        self.reason = reason
        self.is_active = False
        self.updated_at = func.now()


class UserPermissionCache(Base, BaseModelMixin):
    """用户权限缓存表
    
    用于缓存用户的权限信息，提升权限查询性能
    """
    __tablename__ = "user_permission_cache"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_permission_id, comment='缓存ID')
    user_id = Column(String(25), ForeignKey('users.id'), nullable=False, unique=True, index=True, comment='用户ID')
    permissions_json = Column(Text, comment='权限列表JSON字符串')
    roles_json = Column(Text, comment='角色列表JSON字符串')
    last_updated = Column(DateTime, default=func.now(), comment='最后更新时间')
    expires_at = Column(DateTime, comment='过期时间')
    is_valid = Column(Boolean, default=True, comment='是否有效')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关联关系
    user = relationship("User", backref="permission_cache")
    
    def __init__(self, user_id: str, permissions_json: str = None, roles_json: str = None):
        self.user_id = user_id
        self.permissions_json = permissions_json
        self.roles_json = roles_json
    
    def __repr__(self):
        return f"<UserPermissionCache(user_id={self.user_id}, last_updated={self.last_updated})>"
    
    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.now() > self.expires_at
    
    def invalidate(self):
        """使缓存失效"""
        self.is_valid = False
        self.updated_at = func.now()