from fastapi import Depends, HTTPException, Request, Query, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Generator, Annotated
from datetime import datetime
import logging
from functools import wraps

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.auth import verify_token, get_current_user_from_token
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    PermissionException,
    TokenExpiredException,
    TokenInvalidException,
    InsufficientPermissionsException,
    ResourceAccessDeniedException
)
from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task
from app.schemas.common import PaginationParams, SortParams

# 安全相关依赖
security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户"""
    
    if not credentials:
        raise AuthenticationException(message="Authorization header required")
    
    try:
        # 验证令牌并获取用户
        user = await get_current_user_from_token(credentials.credentials, db)
        
        if not user:
            raise AuthenticationException(message="Invalid token")
        
        if not user.is_active:
            raise AuthenticationException(message="Account is disabled")
        
        return user
        
    except TokenExpiredException:
        raise TokenExpiredException()
    except TokenInvalidException:
        raise TokenInvalidException()
    except Exception as e:
        logging.error(f"Authentication error: {str(e)}")
        raise AuthenticationException(message="Authentication failed")

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    
    if not current_user.is_active:
        raise AuthenticationException(message="Account is disabled")
    
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """获取当前管理员用户"""
    
    if not current_user.is_admin:
        raise InsufficientPermissionsException(
            message="Admin privileges required",
            required_permissions=["admin"]
        )
    
    return current_user

async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """获取当前超级用户"""
    
    if not current_user.is_superuser:
        raise InsufficientPermissionsException(
            message="Superuser privileges required",
            required_permissions=["superuser"]
        )
    
    return current_user

# 可选用户依赖（用于公开端点）
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """获取当前用户（可选）"""
    
    if not credentials:
        return None
    
    try:
        user = await get_current_user_from_token(credentials.credentials, db)
        return user if user and user.is_active else None
    except Exception:
        return None

# 权限检查依赖
def require_permissions(required_permissions: List[str]):
    """需要特定权限的依赖"""
    
    async def check_permissions(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # 超级用户拥有所有权限
        if current_user.is_superuser:
            return current_user
        
        # 检查用户权限
        user_permissions = set(current_user.permissions or [])
        required_permissions_set = set(required_permissions)
        
        if not required_permissions_set.issubset(user_permissions):
            missing_permissions = required_permissions_set - user_permissions
            raise InsufficientPermissionsException(
                message=f"Missing required permissions: {', '.join(missing_permissions)}",
                required_permissions=list(missing_permissions)
            )
        
        return current_user
    
    return check_permissions

# 组织相关依赖
async def get_organization_by_id(
    organization_id: str = Path(..., description="Organization ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Organization:
    """根据ID获取组织"""
    
    organization = db.query(Organization).filter(
        Organization.id == organization_id,
        Organization.is_deleted == False
    ).first()
    
    if not organization:
        from app.core.exceptions import OrganizationNotFoundException
        raise OrganizationNotFoundException(organization_id)
    
    # 检查用户是否有访问该组织的权限
    if not current_user.is_superuser and not current_user.can_access_organization(organization_id):
        raise ResourceAccessDeniedException("organization", organization_id)
    
    return organization

# 项目相关依赖
async def get_project_by_id(
    project_id: str = Path(..., description="Project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Project:
    """根据ID获取项目"""
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False
    ).first()
    
    if not project:
        from app.core.exceptions import ProjectNotFoundException
        raise ProjectNotFoundException(project_id)
    
    # 检查用户是否有访问该项目的权限
    if not current_user.is_superuser and not current_user.can_access_project(project_id):
        raise ResourceAccessDeniedException("project", project_id)
    
    return project

# 任务相关依赖
async def get_task_by_id(
    task_id: str = Path(..., description="Task ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Task:
    """根据ID获取任务"""
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.is_deleted == False
    ).first()
    
    if not task:
        from app.core.exceptions import TaskNotFoundException
        raise TaskNotFoundException(task_id)
    
    # 检查用户是否有访问该任务的权限
    if not current_user.is_superuser and not current_user.can_access_task(task_id):
        raise ResourceAccessDeniedException("task", task_id)
    
    return task

# 分页相关依赖
def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size")
) -> PaginationParams:
    """获取分页参数"""
    return PaginationParams(page=page, size=size)

# 排序相关依赖
def get_sort_params(
    sort_by: Optional[str] = Query(None, description="Sort field"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$", description="Sort order")
) -> SortParams:
    """获取排序参数"""
    return SortParams(sort_by=sort_by, sort_order=sort_order)

# 搜索相关依赖
def get_search_params(
    q: Optional[str] = Query(None, description="Search query"),
    search_type: Optional[str] = Query(None, description="Search type"),
    date_from: Optional[datetime] = Query(None, description="Date from"),
    date_to: Optional[datetime] = Query(None, description="Date to")
) -> Dict[str, Any]:
    """获取搜索参数"""
    return {
        "q": q,
        "search_type": search_type,
        "date_from": date_from,
        "date_to": date_to
    }

# 过滤相关依赖
def get_filter_params(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    type: Optional[str] = Query(None, description="Filter by type"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    project_id: Optional[str] = Query(None, description="Filter by project")
) -> Dict[str, Any]:
    """获取过滤参数"""
    filters = {}
    
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority
    if type:
        filters["type"] = type
    if assigned_to:
        filters["assigned_to"] = assigned_to
    if created_by:
        filters["created_by"] = created_by
    if organization_id:
        filters["organization_id"] = organization_id
    if project_id:
        filters["project_id"] = project_id
    
    return filters

# 请求信息依赖
async def get_request_info(request: Request) -> Dict[str, Any]:
    """获取请求信息"""
    return {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "request_id": getattr(request.state, "request_id", "unknown")
    }

# 缓存相关依赖
async def get_cache_key_prefix(
    current_user: User = Depends(get_current_active_user)
) -> str:
    """获取缓存键前缀"""
    return f"user:{current_user.id}"

# 文件上传相关依赖
def validate_file_upload(
    max_size: int = settings.max_file_size,
    allowed_types: List[str] = None
):
    """验证文件上传的依赖"""
    
    def validator(file_size: int, file_type: str) -> bool:
        # 检查文件大小
        if file_size > max_size:
            from app.core.exceptions import FileTooLargeException
            raise FileTooLargeException(file_size, max_size)
        
        # 检查文件类型
        if allowed_types and file_type not in allowed_types:
            from app.core.exceptions import InvalidFileTypeException
            raise InvalidFileTypeException(file_type, allowed_types)
        
        return True
    
    return validator

# 限流相关依赖
def rate_limit(
    requests_per_minute: int = 60,
    burst_size: int = 10
):
    """限流依赖"""
    
    async def check_rate_limit(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user_optional)
    ):
        # 获取客户端标识
        client_id = current_user.id if current_user else request.client.host
        
        # 这里可以实现具体的限流逻辑
        # 通常会使用Redis来存储限流信息
        
        return True
    
    return check_rate_limit

# 组织成员权限检查
def require_organization_permission(permission: str):
    """需要组织权限的依赖"""
    
    async def check_organization_permission(
        organization: Organization = Depends(get_organization_by_id),
        current_user: User = Depends(get_current_active_user)
    ) -> Organization:
        # 超级用户拥有所有权限
        if current_user.is_superuser:
            return organization
        
        # 检查用户在该组织中的权限
        user_org_role = current_user.get_organization_role(organization.id)
        if not user_org_role or not user_org_role.has_permission(permission):
            raise InsufficientPermissionsException(
                message=f"Missing required organization permission: {permission}",
                required_permissions=[permission]
            )
        
        return organization
    
    return check_organization_permission

# 项目成员权限检查
def require_project_permission(permission: str):
    """需要项目权限的依赖"""
    
    async def check_project_permission(
        project: Project = Depends(get_project_by_id),
        current_user: User = Depends(get_current_active_user)
    ) -> Project:
        # 超级用户拥有所有权限
        if current_user.is_superuser:
            return project
        
        # 检查用户在该项目中的权限
        user_project_role = current_user.get_project_role(project.id)
        if not user_project_role or not user_project_role.has_permission(permission):
            raise InsufficientPermissionsException(
                message=f"Missing required project permission: {permission}",
                required_permissions=[permission]
            )
        
        return project
    
    return check_project_permission

# 任务权限检查
def require_task_permission(permission: str):
    """需要任务权限的依赖"""
    
    async def check_task_permission(
        task: Task = Depends(get_task_by_id),
        current_user: User = Depends(get_current_active_user)
    ) -> Task:
        # 超级用户拥有所有权限
        if current_user.is_superuser:
            return task
        
        # 任务创建者和指派人有特殊权限
        if task.created_by == current_user.id or task.assigned_to == current_user.id:
            return task
        
        # 检查用户在该任务所属项目中的权限
        user_project_role = current_user.get_project_role(task.project_id)
        if not user_project_role or not user_project_role.has_permission(permission):
            raise InsufficientPermissionsException(
                message=f"Missing required task permission: {permission}",
                required_permissions=[permission]
            )
        
        return task
    
    return check_task_permission

# 数据访问权限过滤
def get_accessible_organizations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[str]:
    """获取用户可访问的组织ID列表"""
    
    if current_user.is_superuser:
        # 超级用户可以访问所有组织
        return [org.id for org in db.query(Organization).filter(Organization.is_deleted == False).all()]
    
    # 返回用户所属的组织
    return current_user.get_accessible_organization_ids()

def get_accessible_projects(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[str]:
    """获取用户可访问的项目ID列表"""
    
    if current_user.is_superuser:
        # 超级用户可以访问所有项目
        return [proj.id for proj in db.query(Project).filter(Project.is_deleted == False).all()]
    
    # 返回用户可访问的项目
    return current_user.get_accessible_project_ids()

# 批量操作权限检查
def require_bulk_operation_permission(resource_type: str, permission: str):
    """需要批量操作权限的依赖"""
    
    async def check_bulk_permission(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # 超级用户拥有所有权限
        if current_user.is_superuser:
            return current_user
        
        # 检查用户是否有批量操作权限
        bulk_permission = f"bulk_{permission}_{resource_type}"
        if not current_user.has_permission(bulk_permission):
            raise InsufficientPermissionsException(
                message=f"Missing required bulk operation permission: {bulk_permission}",
                required_permissions=[bulk_permission]
            )
        
        return current_user
    
    return check_bulk_permission

# 导出权限检查
def require_export_permission(export_type: str):
    """需要导出权限的依赖"""
    
    async def check_export_permission(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # 超级用户拥有所有权限
        if current_user.is_superuser:
            return current_user
        
        # 检查用户是否有导出权限
        export_permission = f"export_{export_type}"
        if not current_user.has_permission(export_permission):
            raise InsufficientPermissionsException(
                message=f"Missing required export permission: {export_permission}",
                required_permissions=[export_permission]
            )
        
        return current_user
    
    return check_export_permission

# 类型别名，用于简化依赖注入
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
CurrentSuperUser = Annotated[User, Depends(get_current_superuser)]
DatabaseSession = Annotated[Session, Depends(get_db)]
RedisClient = Annotated[Any, Depends(get_redis)]
Pagination = Annotated[PaginationParams, Depends(get_pagination_params)]
Sorting = Annotated[SortParams, Depends(get_sort_params)]
RequestInfo = Annotated[Dict[str, Any], Depends(get_request_info)]

# 常用的组合依赖
def get_list_dependencies():
    """获取列表查询的通用依赖"""
    return {
        "pagination": Depends(get_pagination_params),
        "sorting": Depends(get_sort_params),
        "filters": Depends(get_filter_params),
        "search": Depends(get_search_params),
        "current_user": Depends(get_current_active_user),
        "db": Depends(get_db)
    }

def get_create_dependencies():
    """获取创建操作的通用依赖"""
    return {
        "current_user": Depends(get_current_active_user),
        "db": Depends(get_db),
        "request_info": Depends(get_request_info)
    }

def get_update_dependencies():
    """获取更新操作的通用依赖"""
    return {
        "current_user": Depends(get_current_active_user),
        "db": Depends(get_db),
        "request_info": Depends(get_request_info)
    }

def get_delete_dependencies():
    """获取删除操作的通用依赖"""
    return {
        "current_user": Depends(get_current_active_user),
        "db": Depends(get_db),
        "request_info": Depends(get_request_info)
    }