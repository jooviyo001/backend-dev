from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False) # e.g., pending, in_progress, completed, cancelled
    priority = Column(String, default="medium", nullable=False) # e.g., low, medium, high, urgent
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=False)
    created_by_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    organization = relationship("Organization", backref="projects")
    created_by = relationship("User", foreign_keys=[created_by_id])
    tasks = relationship("Task", backref="project")
    members = relationship("User", secondary="project_members", backref="projects_joined")

from sqlalchemy import Table, Column, String, ForeignKey, DateTime

project_members = Table(
    'project_members',
    Base.metadata,
    Column('project_id', String, ForeignKey('projects.id'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('role', String, default="member", nullable=False),
    Column('assigned_at', DateTime, default=func.now(), nullable=False)
)