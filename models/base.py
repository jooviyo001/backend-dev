"""模型基类模块

包含模型的基类和混入类
"""
from sqlalchemy import Column, Boolean, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declared_attr
from datetime import datetime


class SoftDeleteMixin:
    """软删除混入类"""
    
    is_deleted = Column(Boolean, default=False, comment='是否已删除')
    deleted_at = Column(DateTime, comment='删除时间')
    deleted_by = Column(String(25), comment='删除人ID')
    
    def soft_delete(self, deleted_by: str = None):
        """软删除"""
        self.is_deleted = True
        self.deleted_at = func.now()
        if deleted_by:
            self.deleted_by = deleted_by
    
    def restore(self):
        """恢复删除"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
    
    @classmethod
    def get_active_query(cls, query):
        """获取未删除的记录查询"""
        return query.filter(cls.is_deleted == False)
    
    @classmethod
    def get_deleted_query(cls, query):
        """获取已删除的记录查询"""
        return query.filter(cls.is_deleted == True)


class TimestampMixin:
    """时间戳混入类"""
    
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')


class AuditMixin:
    """审计混入类"""
    
    created_by = Column(String(25), comment='创建人ID')
    updated_by = Column(String(25), comment='更新人ID')
    
    def set_created_by(self, user_id: str):
        """设置创建人"""
        self.created_by = user_id
    
    def set_updated_by(self, user_id: str):
        """设置更新人"""
        self.updated_by = user_id


class BaseModelMixin(TimestampMixin, AuditMixin, SoftDeleteMixin):
    """基础模型混入类，包含时间戳、审计和软删除功能"""
    pass


class VersionMixin:
    """版本控制混入类"""
    
    version = Column(String(20), default='1.0.0', comment='版本号')
    
    def increment_version(self):
        """增加版本号"""
        if self.version:
            try:
                major, minor, patch = map(int, self.version.split('.'))
                patch += 1
                self.version = f"{major}.{minor}.{patch}"
            except ValueError:
                self.version = '1.0.1'
        else:
            self.version = '1.0.1'