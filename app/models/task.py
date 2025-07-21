from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="todo", nullable=False) # e.g., todo, in_progress, done, blocked
    priority = Column(String, default="medium", nullable=False) # e.g., low, medium, high, urgent
    due_date = Column(DateTime, nullable=True)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    assigned_to_id = Column(String, ForeignKey('users.id'), nullable=True)
    created_by_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="tasks")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    files = relationship("File", backref="task")