from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class File(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    file_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    task_id = Column(String, ForeignKey('tasks.id'), nullable=True)
    project_id = Column(String, ForeignKey('projects.id'), nullable=True)
    uploaded_by_id = Column(String, ForeignKey('users.id'), nullable=False)
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    uploaded_by = relationship("User")