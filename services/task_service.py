"""任务服务模块

包含任务相关的业务逻辑处理
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, and_
from datetime import date, datetime

from models import Task, User, Project, TaskStatus, TaskPriority, TaskType, UserRole
from schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from utils.exceptions import BusinessException, ResourceNotFoundException, ValidationException
from utils.status_codes import NOT_FOUND, VALIDATION_ERROR, FORBIDDEN


class TaskService:
    """任务服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_task(self, task_data: TaskCreate, current_user: User) -> Task:
        """创建新任务"""
        # 检查项目是否存在
        project = self.db.query(Project).filter(Project.id == task_data.project_id).first()
        if not project:
            raise ResourceNotFoundException(
                code=NOT_FOUND,
                message=f"项目 {task_data.project_id} 不存在"
            )
        
        # 检查负责人是否存在
        if task_data.assignee_id:
            assignee = self.db.query(User).filter(User.id == task_data.assignee_id).first()
            if not assignee:
                raise ResourceNotFoundException(
                    code=NOT_FOUND,
                    message=f"用户 {task_data.assignee_id} 不存在"
                )
        
        # 创建任务
        import json
        task = Task(
            title=task_data.title,
            description=task_data.description,
            status=task_data.status or TaskStatus.TODO,
            priority=task_data.priority or TaskPriority.MEDIUM,
            type=task_data.type or TaskType.FEATURE,
            project_id=task_data.project_id,
            assignee_id=task_data.assignee_id,
            assignee_name=assignee.name if task_data.assignee_id and assignee else None,
            reporter_id=current_user.id,
            reporter_name=current_user.name,
            start_date=task_data.start_date,
            due_date=task_data.due_date,
            estimated_hours=task_data.estimated_hours,
            parent_task_id=task_data.parent_task_id,
            tags=json.dumps(task_data.tags, ensure_ascii=False) if task_data.tags else None
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return task
    
    def get_task_by_id(self, task_id: str, current_user: User) -> Task:
        """根据ID获取任务"""
        query = self.db.query(Task).options(
            joinedload(Task.project),
            joinedload(Task.assignee),
            joinedload(Task.reporter)
        ).filter(Task.id == task_id)
        
        # 权限检查：非管理员只能查看自己相关的任务
        if current_user.role != UserRole.ADMIN:
            query = query.filter(
                or_(
                    Task.assignee_id == current_user.id,
                    Task.reporter_id == current_user.id,
                    Task.project.has(Project.members.any(User.id == current_user.id))
                )
            )
        
        task = query.first()
        if not task:
            raise ResourceNotFoundException(
                code=NOT_FOUND,
                message=f"任务 {task_id} 不存在或无权限访问"
            )
        
        return task
    
    def update_task(self, task_id: str, task_data: TaskUpdate, current_user: User) -> Task:
        """更新任务"""
        task = self.get_task_by_id(task_id, current_user)
        
        # 权限检查：只有任务负责人、报告人或管理员可以更新任务
        if (current_user.role != UserRole.ADMIN and 
            current_user.id != task.assignee_id and 
            current_user.id != task.reporter_id):
            raise BusinessException(
                code=FORBIDDEN,
                message="无权限更新此任务"
            )
        
        # 更新字段
        update_data = task_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(task, field):
                setattr(task, field, value)
        
        # 如果更新了负责人，同时更新负责人姓名
        if task_data.assignee_id:
            assignee = self.db.query(User).filter(User.id == task_data.assignee_id).first()
            if assignee:
                task.assignee_name = assignee.name
        
        self.db.commit()
        self.db.refresh(task)
        
        return task
    
    def delete_task(self, task_id: str, current_user: User) -> bool:
        """删除任务"""
        task = self.get_task_by_id(task_id, current_user)
        
        # 权限检查：只有任务报告人或管理员可以删除任务
        if (current_user.role != UserRole.ADMIN and 
            current_user.id != task.reporter_id):
            raise BusinessException(
                code=FORBIDDEN,
                message="无权限删除此任务"
            )
        
        self.db.delete(task)
        self.db.commit()
        
        return True
    
    def get_tasks_list(self, 
                      limit: int = 5,
                      status: Optional[TaskStatus] = None,
                      priority: Optional[TaskPriority] = None,
                      project_id: Optional[str] = None,
                      assignee_id: Optional[str] = None,
                      current_user: User = None) -> List[TaskListResponse]:
        """获取任务列表"""
        query = self.db.query(Task).options(
            joinedload(Task.project),
            joinedload(Task.assignee)
        )
        
        # 权限过滤
        if current_user and current_user.role != UserRole.ADMIN:
            query = query.filter(
                or_(
                    Task.assignee_id == current_user.id,
                    Task.reporter_id == current_user.id,
                    Task.project.has(Project.members.any(User.id == current_user.id))
                )
            )
        
        # 应用筛选条件
        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if assignee_id:
            query = query.filter(Task.assignee_id == assignee_id)
        
        tasks = query.order_by(desc(Task.created_at)).limit(limit).all()
        
        # 构建响应数据
        task_list = []
        for task in tasks:
            task_data = {
                "id": task.id,
                "title": task.title,
                "project_name": task.project.name if task.project else None,
                "project_id": task.project_id,
                "assignee_name": task.assignee.username if task.assignee else None,
                "assignee_id": task.assignee_id,
                "priority": task.priority,
                "status": task.status,
                "due_date": task.due_date,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            }
            task_list.append(TaskListResponse(**task_data))
        
        return task_list
    
    def get_tasks_page(self,
                      page: int = 1,
                      size: int = 10,
                      keyword: Optional[str] = None,
                      status: Optional[TaskStatus] = None,
                      department_id: Optional[str] = None,
                      project_id: Optional[str] = None,
                      assignee_id: Optional[str] = None,
                      reporter_id: Optional[str] = None,
                      priority: Optional[TaskPriority] = None,
                      type: Optional[TaskType] = None,
                      start_date: Optional[date] = None,
                      end_date: Optional[date] = None,
                      current_user: User = None) -> Tuple[int, List[Task]]:
        """获取任务分页数据"""
        query = self.db.query(Task).options(
            joinedload(Task.assignee),
            joinedload(Task.reporter),
            joinedload(Task.project)
        )
        
        # 权限过滤
        if current_user and current_user.role != UserRole.ADMIN:
            query = query.filter(
                or_(
                    Task.assignee_id == current_user.id,
                    Task.reporter_id == current_user.id,
                    Task.project.has(Project.members.any(User.id == current_user.id))
                )
            )
        
        # 应用筛选条件
        if keyword:
            query = query.filter(
                or_(
                    Task.title.contains(keyword),
                    Task.description.contains(keyword)
                )
            )
        if status:
            query = query.filter(Task.status == status)
        if department_id:
            query = query.join(Project).filter(Project.department_id == department_id)
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if assignee_id:
            query = query.filter(Task.assignee_id == assignee_id)
        if reporter_id:
            query = query.filter(Task.reporter_id == reporter_id)
        if priority:
            query = query.filter(Task.priority == priority)
        if type:
            query = query.filter(Task.type == type)
        if start_date:
            query = query.filter(Task.created_at >= start_date)
        if end_date:
            query = query.filter(Task.created_at <= end_date)
        
        total = query.count()
        tasks = query.offset((page - 1) * size).limit(size).all()
        
        return total, tasks
    
    def batch_update_status(self, task_ids: List[str], status: TaskStatus, current_user: User) -> List[Task]:
        """批量更新任务状态"""
        tasks = self.db.query(Task).filter(Task.id.in_(task_ids)).all()
        
        if not tasks:
            raise ResourceNotFoundException(
                code=NOT_FOUND,
                message="未找到指定的任务"
            )
        
        updated_tasks = []
        for task in tasks:
            # 权限检查
            if (current_user.role != UserRole.ADMIN and 
                current_user.id != task.assignee_id and 
                current_user.id != task.reporter_id):
                continue
            
            task.status = status
            updated_tasks.append(task)
        
        if not updated_tasks:
            raise BusinessException(
                code=FORBIDDEN,
                message="无权限更新任何任务"
            )
        
        self.db.commit()
        
        return updated_tasks
    
    def batch_update_assignee(self, task_ids: List[str], assignee_id: str, current_user: User) -> List[Task]:
        """批量更新任务负责人"""
        # 检查新负责人是否存在
        assignee = self.db.query(User).filter(User.id == assignee_id).first()
        if not assignee:
            raise ResourceNotFoundException(
                code=NOT_FOUND,
                message=f"用户 {assignee_id} 不存在"
            )
        
        tasks = self.db.query(Task).filter(Task.id.in_(task_ids)).all()
        
        if not tasks:
            raise ResourceNotFoundException(
                code=NOT_FOUND,
                message="未找到指定的任务"
            )
        
        updated_tasks = []
        for task in tasks:
            # 权限检查
            if (current_user.role != UserRole.ADMIN and 
                current_user.id != task.assignee_id and 
                current_user.id != task.reporter_id):
                continue
            
            task.assignee_id = assignee_id
            task.assignee_name = assignee.name
            updated_tasks.append(task)
        
        if not updated_tasks:
            raise BusinessException(
                code=FORBIDDEN,
                message="无权限更新任何任务"
            )
        
        self.db.commit()
        
        return updated_tasks
    
    def batch_delete_tasks(self, task_ids: List[str], current_user: User) -> int:
        """批量删除任务"""
        tasks = self.db.query(Task).filter(Task.id.in_(task_ids)).all()
        
        if not tasks:
            raise ResourceNotFoundException(
                code=NOT_FOUND,
                message="未找到指定的任务"
            )
        
        deleted_count = 0
        for task in tasks:
            # 权限检查：只有任务报告人或管理员可以删除任务
            if (current_user.role != UserRole.ADMIN and 
                current_user.id != task.reporter_id):
                continue
            
            self.db.delete(task)
            deleted_count += 1
        
        if deleted_count == 0:
            raise BusinessException(
                code=FORBIDDEN,
                message="无权限删除任何任务"
            )
        
        self.db.commit()
        
        return deleted_count