"""
任务模型模块
包含任务相关的数据模型定义
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Numeric, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import TaskStatus, TaskPriority, TaskType
from utils.snowflake import (
    generate_task_id,
    generate_task_attachment_id,
    generate_task_comment_id
)


class Task(Base):
    """任务表模型"""
    __tablename__ = "tasks"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_task_id, comment='任务ID，格式：T + 雪花算法ID')
    title = Column(String(200), nullable=False, comment='任务标题')
    description = Column(Text, comment='任务描述')
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, comment='任务状态')
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, comment='任务优先级')
    type = Column(Enum(TaskType), default=TaskType.FEATURE, comment='任务类型')
    project_id = Column(String(25), ForeignKey("projects.id"), comment='任务所属项目ID')
    assignee_id = Column(String(25), ForeignKey("users.id"), comment='任务负责人ID')
    assignee_name = Column(String(100), comment='任务负责人姓名')
    reporter_id = Column(String(25), ForeignKey("users.id"), comment='任务报告人ID')
    reporter_name = Column(String(100), comment='任务报告人姓名')
    start_date = Column(DateTime, comment='任务开始时间')
    due_date = Column(DateTime, comment='任务截止时间')
    estimated_hours = Column(Numeric(5, 2), comment='任务预估工时')
    actual_hours = Column(Numeric(5, 2), comment='任务实际工时')
    parent_task_id = Column(String(25), ForeignKey('tasks.id'), nullable=True, comment='父任务ID')
    tags = Column(String(500), comment='任务标签')  # JSON字符串存储标签
    is_deleted = Column(Boolean, default=False, comment='是否已删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关系
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks", overlaps="assigned_tasks")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_tasks", overlaps="reported_tasks")
    parent_task = relationship("Task", remote_side=[id], back_populates="sub_tasks")
    sub_tasks = relationship("Task", back_populates="parent_task")
    attachments = relationship("TaskAttachment", back_populates="task")
    comments = relationship("TaskComment", back_populates="task")


class TaskAttachment(Base):
    """任务附件表模型"""
    __tablename__ = "task_attachments"
    
    id = Column(String(27), primary_key=True, index=True, default=generate_task_attachment_id, comment='任务附件ID，格式：TA + 雪花算法ID')
    task_id = Column(String(25), ForeignKey("tasks.id"), comment='任务附件所属任务ID')
    filename = Column(String(255), nullable=False, comment='附件文件名')
    original_filename = Column(String(255), nullable=False, comment='附件原始文件名')
    file_path = Column(String(500), nullable=False, comment='附件文件路径')
    file_size = Column(Integer, comment='附件文件大小')
    content_type = Column(String(100), comment='附件文件类型')
    uploaded_by = Column(String(25), ForeignKey("users.id"), comment='附件上传人ID')
    is_deleted = Column(Boolean, default=False, comment='是否已删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    task = relationship("Task", back_populates="attachments")
    uploader = relationship("User")


class TaskComment(Base):
    """任务评论表模型"""
    __tablename__ = "task_comments"
    
    id = Column(String(27), primary_key=True, index=True, default=generate_task_comment_id, comment='任务评论ID，格式：TC + 雪花算法ID')
    task_id = Column(String(25), ForeignKey("tasks.id"), comment='评论所属任务ID')
    user_id = Column(String(25), ForeignKey("users.id"), comment='评论用户ID')
    content = Column(Text, nullable=False, comment='评论内容')
    parent_id = Column(String(27), ForeignKey("task_comments.id"), nullable=True, comment='父评论ID')
    is_deleted = Column(Boolean, default=False, comment='是否已删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    task = relationship("Task", back_populates="comments")
    user = relationship("User")
    replies = relationship("TaskComment", back_populates="parent_comment", foreign_keys="[TaskComment.parent_id]")
    parent_comment = relationship("TaskComment", remote_side=[id], back_populates="replies")