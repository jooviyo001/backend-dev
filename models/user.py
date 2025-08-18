"""
用户模型模块
包含用户相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import UserRole
from .associations import project_members, organization_members
from utils.snowflake import generate_user_id
from models.base import BaseModelMixin
import json


class User(Base, BaseModelMixin):
    """用户表模型"""
    __tablename__ = "users"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_user_id, comment='用户ID，格式：U + 雪花算法ID')
    username = Column(String(50), unique=True, index=True, nullable=False, comment='用户名，唯一标识')
    email = Column(String(100), unique=True, index=True, nullable=False, comment='邮箱地址，唯一标识')
    password_hash = Column(String(255), nullable=False, comment='密码哈希值')
    name = Column(String(100), comment='用户真实姓名')
    avatar = Column(String(255), comment='头像URL地址')
    phone = Column(String(20), comment='手机号码')
    position_id = Column(String(25), ForeignKey("positions.id"), comment='用户岗位/职位ID')
    position = relationship("Position", foreign_keys=[position_id], overlaps="users")
    department = Column(String(100), comment='用户所属组织名称')
    department_id = Column(String(25), ForeignKey("organizations.id"), comment='用户所属组织ID')
    role_id = Column(String(25), ForeignKey("roles.id"), comment='用户角色ID')
    role = Column(Enum(UserRole), default=UserRole.MEMBER, comment='用户角色枚举(备用)')
    is_active = Column(Boolean, default=True, comment='是否激活状态')
    is_verified = Column(Boolean, default=False, comment='是否已验证邮箱')
    last_login = Column(DateTime, comment='最后登录时间')
    last_logout = Column(DateTime, comment='最后登出时间')
    notification_settings = Column(Text, comment='通知设置JSON字符串')
    language_settings = Column(Text, comment='语言设置JSON字符串')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    organization = relationship("Organization", foreign_keys=[department_id])
    user_role = relationship("Role", back_populates="users", foreign_keys=[role_id])
    created_projects = relationship("Project", back_populates="creator", foreign_keys="Project.creator_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    reported_tasks = relationship("Task", back_populates="reporter", foreign_keys="Task.reporter_id")
    projects = relationship("Project", secondary=project_members, back_populates="members")
    organizations = relationship("Organization", secondary=organization_members, back_populates="members")
    comments = relationship("Comment", back_populates="author")
    
    def get_notification_settings(self):
        """获取通知设置"""
        settings = str(self.notification_settings) if self.notification_settings else ""  # type: ignore
        if settings:
            try:
                return json.loads(settings)
            except json.JSONDecodeError:
                pass
        # 返回默认设置
        return {
            "email_notifications": True,
            "push_notifications": True,
            "sms_notifications": False,
            "wechat_notifications": False
        }
    
    def set_notification_settings(self, settings_dict):
        """设置通知设置"""
        self.notification_settings = json.dumps(settings_dict, ensure_ascii=False)  # type: ignore
    
    def get_language_settings(self):
        """获取语言设置"""
        settings = str(self.language_settings) if self.language_settings else ""  # type: ignore
        if settings:
            try:
                return json.loads(settings)
            except json.JSONDecodeError:
                pass
        # 返回默认设置
        return {
            "language": "zh-CN",
            "timezone": "Asia/Shanghai",
            "date_format": "YYYY-MM-DD",
            "time_format": "HH:mm:ss"
        }
    
    def set_language_settings(self, settings_dict):
        """设置语言设置"""
        self.language_settings = json.dumps(settings_dict, ensure_ascii=False)  # type: ignore