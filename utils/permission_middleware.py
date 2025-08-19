"""权限验证中间件模块

提供统一的权限验证中间件和装饰器
"""
import json
from typing import Optional, List, Callable, Any
from functools import wraps
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

from models.database import get_db
from utils.auth import get_current_user
from utils.exceptions import BusinessException
from utils.status_codes import FORBIDDEN, UNAUTHORIZED
from utils.response_utils import standard_response


security = HTTPBearer(auto_error=False)


class PermissionMiddleware(BaseHTTPMiddleware):
    """权限验证中间件
    
    在请求处理前进行权限检查，确保用户有足够的权限访问资源
    """
    
    def __init__(self, app, skip_paths: Optional[List[str]] = None):
        super().__init__(app)
        # 默认跳过的路径
        self.skip_paths = skip_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/health",
            "/favicon.ico",
            "/@vite/client"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """中间件处理逻辑"""
        # 检查是否需要跳过权限验证
        if self._should_skip_permission_check(request):
            return await call_next(request)
        
        try:
            # 从请求中提取权限要求
            permission_requirement = self._extract_permission_requirement(request)
            
            if permission_requirement:
                # 验证用户权限
                await self._verify_permission(request, permission_requirement)
            
            # 继续处理请求
            return await call_next(request)
            
        except HTTPException as e:
            # 返回标准错误响应
            error_response = standard_response(
                data=None,
                code=str(e.status_code),
                message=e.detail,
                status_code=e.status_code
            )
            return JSONResponse(content=error_response, status_code=e.status_code)
        except Exception as e:
            # 处理其他异常
            error_response = standard_response(
                data=None,
                code="500",
                message=f"权限验证失败: {str(e)}",
                status_code=500
            )
            return JSONResponse(content=error_response, status_code=500)
    
    def _should_skip_permission_check(self, request: Request) -> bool:
        """判断是否应该跳过权限检查
        
        Args:
            request: HTTP请求对象
            
        Returns:
            bool: 是否跳过权限检查
        """
        path = request.url.path
        
        # 检查是否在跳过列表中
        for skip_path in self.skip_paths:
            if path == skip_path or path.startswith(skip_path):
                return True
        
        # 检查是否是OPTIONS请求（CORS预检请求）
        if request.method == "OPTIONS":
            return True
        
        return False
    
    def _extract_permission_requirement(self, request: Request) -> Optional[dict]:
        """从请求中提取权限要求
        
        Args:
            request: HTTP请求对象
            
        Returns:
            Optional[dict]: 权限要求信息，包含resource_type和action_type
        """
        # 根据请求路径和方法推断权限要求
        path = request.url.path
        method = request.method
        
        # 定义路径到资源类型的映射
        path_resource_mapping = {
            "/users": "user",
            "/roles": "role",
            "/projects": "project",
            "/tasks": "task",
            "/defects": "defect",
            "/documents": "document",
            "/organizations": "organization",
            "/permissions": "permission"
        }
        
        # 定义HTTP方法到操作类型的映射
        method_action_mapping = {
            "GET": "read",
            "POST": "write",
            "PUT": "write",
            "PATCH": "write",
            "DELETE": "delete"
        }
        
        # 查找匹配的资源类型
        resource_type = None
        for path_prefix, resource in path_resource_mapping.items():
            if path.startswith(path_prefix):
                resource_type = resource
                break
        
        if not resource_type:
            return None
        
        # 获取操作类型
        action_type = method_action_mapping.get(method, "read")
        
        # 特殊路径处理
        if "/manage" in path or "/admin" in path:
            action_type = "manage"
        elif "/approve" in path:
            action_type = "approve"
        elif "/execute" in path:
            action_type = "execute"
        
        return {
            "resource_type": resource_type,
            "action_type": action_type
        }
    
    async def _verify_permission(self, request: Request, permission_requirement: dict) -> None:
        """验证用户权限
        
        Args:
            request: HTTP请求对象
            permission_requirement: 权限要求
            
        Raises:
            HTTPException: 当权限验证失败时
        """
        # 获取授权头
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=UNAUTHORIZED,
                detail="缺少授权令牌"
            )
        
        # 这里需要实现用户身份验证和权限检查逻辑
        # 由于涉及到依赖注入，实际的权限检查会在装饰器中进行
        # 中间件主要用于预处理和统一错误处理
        pass


def require_permission(resource_type: str, action_type: str, 
                      resource_id_param: Optional[str] = None):
    """权限验证装饰器
    
    Args:
        resource_type: 资源类型
        action_type: 操作类型
        resource_id_param: 资源ID参数名（可选）
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中获取数据库会话和当前用户
            db: Session = None
            current_user = None
            
            # 查找db和current_user参数
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                elif hasattr(arg, 'id') and hasattr(arg, 'username'):
                    current_user = arg
            
            # 从kwargs中查找
            if not db:
                db = kwargs.get('db')
            if not current_user:
                current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=500,
                    detail="权限验证装饰器配置错误：缺少必要参数"
                )
            
            # 获取权限服务（延迟导入避免循环依赖）
            from services.permission_service import get_permission_service
            permission_service = get_permission_service(db)
            
            # 获取资源ID（如果需要）
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = kwargs[resource_id_param]
            
            # 检查用户权限
            has_permission = permission_service.check_user_permission(
                user_id=current_user.id,
                resource_type=resource_type,
                action_type=action_type,
                resource_id=resource_id
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=FORBIDDEN,
                    detail=f"权限不足：需要 {resource_type}:{action_type} 权限"
                )
            
            # 执行原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_permissions(permissions: List[tuple], require_all: bool = True):
    """多权限验证装饰器
    
    Args:
        permissions: 权限列表，每个元素为(resource_type, action_type)元组
        require_all: 是否需要所有权限（True）还是任一权限（False）
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中获取数据库会话和当前用户
            db: Session = None
            current_user = None
            
            # 查找db和current_user参数
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                elif hasattr(arg, 'id') and hasattr(arg, 'username'):
                    current_user = arg
            
            # 从kwargs中查找
            if not db:
                db = kwargs.get('db')
            if not current_user:
                current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=500,
                    detail="权限验证装饰器配置错误：缺少必要参数"
                )
            
            # 获取权限服务
            permission_service = get_permission_service(db)
            
            # 批量检查权限
            permission_results = permission_service.batch_check_permissions(
                user_id=current_user.id,
                permission_checks=permissions
            )
            
            # 根据require_all参数判断权限
            if require_all:
                # 需要所有权限
                missing_permissions = []
                for resource_type, action_type in permissions:
                    key = f"{resource_type}:{action_type}"
                    if not permission_results.get(key, False):
                        missing_permissions.append(f"{resource_type}:{action_type}")
                
                if missing_permissions:
                    raise HTTPException(
                        status_code=FORBIDDEN,
                        detail=f"权限不足：缺少权限 {', '.join(missing_permissions)}"
                    )
            else:
                # 只需要任一权限
                has_any_permission = any(permission_results.values())
                if not has_any_permission:
                    required_permissions = [f"{rt}:{at}" for rt, at in permissions]
                    raise HTTPException(
                        status_code=FORBIDDEN,
                        detail=f"权限不足：需要以下权限之一 {', '.join(required_permissions)}"
                    )
            
            # 执行原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(role_codes: List[str]):
    """角色验证装饰器
    
    Args:
        role_codes: 允许的角色编码列表
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中获取当前用户
            current_user = None
            
            # 查找current_user参数
            for arg in args:
                if hasattr(arg, 'id') and hasattr(arg, 'username') and hasattr(arg, 'user_role'):
                    current_user = arg
                    break
            
            # 从kwargs中查找
            if not current_user:
                current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=500,
                    detail="角色验证装饰器配置错误：缺少当前用户参数"
                )
            
            # 检查用户角色
            user_role_code = current_user.user_role.code if current_user.user_role else None
            
            if user_role_code not in role_codes:
                raise HTTPException(
                    status_code=FORBIDDEN,
                    detail=f"角色权限不足：需要角色 {', '.join(role_codes)}"
                )
            
            # 执行原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_admin(func: Callable) -> Callable:
    """管理员权限装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    return require_role(["SYSTEM_ADMIN", "ADMIN"])(func)


def require_manager_or_admin(func: Callable) -> Callable:
    """管理员或经理权限装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    return require_role(["SYSTEM_ADMIN", "ADMIN", "PROJECT_MANAGER", "MANAGER"])(func)


class PermissionChecker:
    """权限检查器类
    
    提供更灵活的权限检查方法
    """
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.permission_service = get_permission_service(db)
    
    def has_permission(self, resource_type: str, action_type: str, 
                      resource_id: Optional[str] = None) -> bool:
        """检查是否具有指定权限
        
        Args:
            resource_type: 资源类型
            action_type: 操作类型
            resource_id: 资源ID（可选）
            
        Returns:
            bool: 是否具有权限
        """
        return self.permission_service.check_user_permission(
            user_id=self.user_id,
            resource_type=resource_type,
            action_type=action_type,
            resource_id=resource_id
        )
    
    def has_any_permission(self, permissions: List[tuple]) -> bool:
        """检查是否具有任一权限
        
        Args:
            permissions: 权限列表，每个元素为(resource_type, action_type)元组
            
        Returns:
            bool: 是否具有任一权限
        """
        results = self.permission_service.batch_check_permissions(
            user_id=self.user_id,
            permission_checks=permissions
        )
        return any(results.values())
    
    def has_all_permissions(self, permissions: List[tuple]) -> bool:
        """检查是否具有所有权限
        
        Args:
            permissions: 权限列表，每个元素为(resource_type, action_type)元组
            
        Returns:
            bool: 是否具有所有权限
        """
        results = self.permission_service.batch_check_permissions(
            user_id=self.user_id,
            permission_checks=permissions
        )
        return all(results.values())
    
    def get_accessible_resources(self, resource_type: str, action_type: str) -> List[str]:
        """获取可访问的资源列表
        
        Args:
            resource_type: 资源类型
            action_type: 操作类型
            
        Returns:
            List[str]: 可访问的资源ID列表
        """
        return self.permission_service.get_user_accessible_resources(
            user_id=self.user_id,
            resource_type=resource_type,
            action_type=action_type
        )


def get_permission_checker(db: Session = Depends(get_db), 
                          current_user = Depends(get_current_user)) -> PermissionChecker:
    """获取权限检查器实例
    
    Args:
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        PermissionChecker: 权限检查器实例
    """
    return PermissionChecker(db, current_user.id)