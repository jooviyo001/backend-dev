from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, NoResultFound
from redis.exceptions import RedisError
from pydantic import ValidationError
import logging
from typing import Any, Dict, Optional, Union
from enum import Enum

from app.core.logging import app_logger

class ErrorCode(str, Enum):
    """错误代码枚举"""
    
    # 通用错误
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    BAD_REQUEST = "BAD_REQUEST"
    CONFLICT = "CONFLICT"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    
    # 认证相关错误
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    PASSWORD_EXPIRED = "PASSWORD_EXPIRED"
    TWO_FACTOR_REQUIRED = "TWO_FACTOR_REQUIRED"
    INVALID_TWO_FACTOR_CODE = "INVALID_TWO_FACTOR_CODE"
    
    # 权限相关错误
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    RESOURCE_ACCESS_DENIED = "RESOURCE_ACCESS_DENIED"
    ORGANIZATION_ACCESS_DENIED = "ORGANIZATION_ACCESS_DENIED"
    PROJECT_ACCESS_DENIED = "PROJECT_ACCESS_DENIED"
    
    # 业务逻辑错误
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    USERNAME_ALREADY_EXISTS = "USERNAME_ALREADY_EXISTS"
    ORGANIZATION_ALREADY_EXISTS = "ORGANIZATION_ALREADY_EXISTS"
    PROJECT_ALREADY_EXISTS = "PROJECT_ALREADY_EXISTS"
    TASK_ALREADY_EXISTS = "TASK_ALREADY_EXISTS"
    
    # 资源不存在错误
    USER_NOT_FOUND = "USER_NOT_FOUND"
    ORGANIZATION_NOT_FOUND = "ORGANIZATION_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    
    # 状态错误
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    TASK_ALREADY_COMPLETED = "TASK_ALREADY_COMPLETED"
    PROJECT_ALREADY_ARCHIVED = "PROJECT_ALREADY_ARCHIVED"
    
    # 文件相关错误
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_UPLOAD_FAILED = "FILE_UPLOAD_FAILED"
    FILE_PROCESSING_FAILED = "FILE_PROCESSING_FAILED"
    
    # 数据库相关错误
    DATABASE_ERROR = "DATABASE_ERROR"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    FOREIGN_KEY_VIOLATION = "FOREIGN_KEY_VIOLATION"
    UNIQUE_CONSTRAINT_VIOLATION = "UNIQUE_CONSTRAINT_VIOLATION"
    
    # 外部服务错误
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    EMAIL_SERVICE_ERROR = "EMAIL_SERVICE_ERROR"
    SMS_SERVICE_ERROR = "SMS_SERVICE_ERROR"
    STORAGE_SERVICE_ERROR = "STORAGE_SERVICE_ERROR"
    
    # 缓存相关错误
    CACHE_ERROR = "CACHE_ERROR"
    CACHE_MISS = "CACHE_MISS"
    
    # 导出相关错误
    EXPORT_TASK_NOT_FOUND = "EXPORT_TASK_NOT_FOUND"
    EXPORT_TASK_FAILED = "EXPORT_TASK_FAILED"
    EXPORT_FILE_NOT_FOUND = "EXPORT_FILE_NOT_FOUND"
    
    # 搜索相关错误
    SEARCH_ERROR = "SEARCH_ERROR"
    INVALID_SEARCH_QUERY = "INVALID_SEARCH_QUERY"

class BaseAPIException(HTTPException):
    """基础API异常类"""
    
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code.value,
                "message": message,
                "details": self.details
            },
            headers=headers
        )

# 认证相关异常
class AuthenticationException(BaseAPIException):
    """认证异常"""
    
    def __init__(self, error_code: ErrorCode = ErrorCode.UNAUTHORIZED, message: str = "Authentication required", details: Optional[Dict[str, Any]] = None):
        super().__init__(401, error_code, message, details)

class InvalidCredentialsException(AuthenticationException):
    """无效凭据异常"""
    
    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(ErrorCode.INVALID_CREDENTIALS, message)

class TokenExpiredException(AuthenticationException):
    """令牌过期异常"""
    
    def __init__(self, message: str = "Token has expired"):
        super().__init__(ErrorCode.TOKEN_EXPIRED, message)

class TokenInvalidException(AuthenticationException):
    """无效令牌异常"""
    
    def __init__(self, message: str = "Invalid token"):
        super().__init__(ErrorCode.TOKEN_INVALID, message)

class AccountDisabledException(AuthenticationException):
    """账户禁用异常"""
    
    def __init__(self, message: str = "Account is disabled"):
        super().__init__(ErrorCode.ACCOUNT_DISABLED, message)

class AccountLockedException(AuthenticationException):
    """账户锁定异常"""
    
    def __init__(self, message: str = "Account is locked", details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.ACCOUNT_LOCKED, message, details)

class TwoFactorRequiredException(AuthenticationException):
    """需要双因素认证异常"""
    
    def __init__(self, message: str = "Two-factor authentication required"):
        super().__init__(ErrorCode.TWO_FACTOR_REQUIRED, message)

class InvalidTwoFactorCodeException(AuthenticationException):
    """无效双因素认证代码异常"""
    
    def __init__(self, message: str = "Invalid two-factor authentication code"):
        super().__init__(ErrorCode.INVALID_TWO_FACTOR_CODE, message)

# 权限相关异常
class PermissionException(BaseAPIException):
    """权限异常"""
    
    def __init__(self, error_code: ErrorCode = ErrorCode.FORBIDDEN, message: str = "Permission denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(403, error_code, message, details)

class InsufficientPermissionsException(PermissionException):
    """权限不足异常"""
    
    def __init__(self, message: str = "Insufficient permissions", required_permissions: Optional[list] = None):
        details = {"required_permissions": required_permissions} if required_permissions else None
        super().__init__(ErrorCode.INSUFFICIENT_PERMISSIONS, message, details)

class ResourceAccessDeniedException(PermissionException):
    """资源访问拒绝异常"""
    
    def __init__(self, resource_type: str, resource_id: str, message: str = None):
        message = message or f"Access denied to {resource_type} {resource_id}"
        details = {"resource_type": resource_type, "resource_id": resource_id}
        super().__init__(ErrorCode.RESOURCE_ACCESS_DENIED, message, details)

# 资源不存在异常
class ResourceNotFoundException(BaseAPIException):
    """资源不存在异常"""
    
    def __init__(self, error_code: ErrorCode, resource_type: str, resource_id: str = None, message: str = None):
        if not message:
            if resource_id:
                message = f"{resource_type} with ID {resource_id} not found"
            else:
                message = f"{resource_type} not found"
        
        details = {"resource_type": resource_type}
        if resource_id:
            details["resource_id"] = resource_id
        
        super().__init__(404, error_code, message, details)

class UserNotFoundException(ResourceNotFoundException):
    """用户不存在异常"""
    
    def __init__(self, user_id: str = None):
        super().__init__(ErrorCode.USER_NOT_FOUND, "User", user_id)

class OrganizationNotFoundException(ResourceNotFoundException):
    """组织不存在异常"""
    
    def __init__(self, org_id: str = None):
        super().__init__(ErrorCode.ORGANIZATION_NOT_FOUND, "Organization", org_id)

class ProjectNotFoundException(ResourceNotFoundException):
    """项目不存在异常"""
    
    def __init__(self, project_id: str = None):
        super().__init__(ErrorCode.PROJECT_NOT_FOUND, "Project", project_id)

class TaskNotFoundException(ResourceNotFoundException):
    """任务不存在异常"""
    
    def __init__(self, task_id: str = None):
        super().__init__(ErrorCode.TASK_NOT_FOUND, "Task", task_id)

class FileNotFoundException(ResourceNotFoundException):
    """文件不存在异常"""
    
    def __init__(self, file_id: str = None):
        super().__init__(ErrorCode.FILE_NOT_FOUND, "File", file_id)

# 冲突异常
class ConflictException(BaseAPIException):
    """冲突异常"""
    
    def __init__(self, error_code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(409, error_code, message, details)

class UserAlreadyExistsException(ConflictException):
    """用户已存在异常"""
    
    def __init__(self, field: str, value: str):
        message = f"User with {field} '{value}' already exists"
        details = {"field": field, "value": value}
        super().__init__(ErrorCode.USER_ALREADY_EXISTS, message, details)

class EmailAlreadyExistsException(ConflictException):
    """邮箱已存在异常"""
    
    def __init__(self, email: str):
        message = f"Email '{email}' is already registered"
        details = {"email": email}
        super().__init__(ErrorCode.EMAIL_ALREADY_EXISTS, message, details)

class UsernameAlreadyExistsException(ConflictException):
    """用户名已存在异常"""
    
    def __init__(self, username: str):
        message = f"Username '{username}' is already taken"
        details = {"username": username}
        super().__init__(ErrorCode.USERNAME_ALREADY_EXISTS, message, details)

# 验证异常
class ValidationException(BaseAPIException):
    """验证异常"""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, str]] = None):
        details = {"field_errors": field_errors} if field_errors else None
        super().__init__(422, ErrorCode.VALIDATION_ERROR, message, details)

# 业务逻辑异常
class BusinessLogicException(BaseAPIException):
    """业务逻辑异常"""
    
    def __init__(self, error_code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(400, error_code, message, details)

class InvalidStatusTransitionException(BusinessLogicException):
    """无效状态转换异常"""
    
    def __init__(self, current_status: str, target_status: str, entity_type: str = "entity"):
        message = f"Cannot transition {entity_type} from {current_status} to {target_status}"
        details = {
            "current_status": current_status,
            "target_status": target_status,
            "entity_type": entity_type
        }
        super().__init__(ErrorCode.INVALID_STATUS_TRANSITION, message, details)

# 文件相关异常
class FileException(BaseAPIException):
    """文件异常"""
    
    def __init__(self, error_code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(400, error_code, message, details)

class FileTooLargeException(FileException):
    """文件过大异常"""
    
    def __init__(self, file_size: int, max_size: int):
        message = f"File size {file_size} bytes exceeds maximum allowed size {max_size} bytes"
        details = {"file_size": file_size, "max_size": max_size}
        super().__init__(ErrorCode.FILE_TOO_LARGE, message, details)

class InvalidFileTypeException(FileException):
    """无效文件类型异常"""
    
    def __init__(self, file_type: str, allowed_types: list):
        message = f"File type '{file_type}' is not allowed. Allowed types: {', '.join(allowed_types)}"
        details = {"file_type": file_type, "allowed_types": allowed_types}
        super().__init__(ErrorCode.INVALID_FILE_TYPE, message, details)

# 外部服务异常
class ExternalServiceException(BaseAPIException):
    """外部服务异常"""
    
    def __init__(self, error_code: ErrorCode, service_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        full_message = f"{service_name} service error: {message}"
        service_details = {"service_name": service_name}
        if details:
            service_details.update(details)
        super().__init__(502, error_code, full_message, service_details)

class EmailServiceException(ExternalServiceException):
    """邮件服务异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.EMAIL_SERVICE_ERROR, "Email", message, details)

# 数据库异常
class DatabaseException(BaseAPIException):
    """数据库异常"""
    
    def __init__(self, error_code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(500, error_code, message, details)

# 限流异常
class RateLimitException(BaseAPIException):
    """限流异常"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        details = {"retry_after": retry_after}
        headers = {"Retry-After": str(retry_after)}
        super().__init__(429, ErrorCode.TOO_MANY_REQUESTS, message, details, headers)

# 全局异常处理器
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理器"""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 记录异常
    app_logger.api_logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        request_id=request_id,
        status_code=exc.status_code,
        detail=str(exc.detail),
        url=str(request.url),
        method=request.method
    )
    
    # 构建响应
    if isinstance(exc, BaseAPIException):
        content = exc.detail
    else:
        content = {
            "error_code": "HTTP_EXCEPTION",
            "message": str(exc.detail),
            "details": {}
        }
    
    content["request_id"] = request_id
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """验证异常处理器"""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 提取字段错误
    field_errors = {}
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"][1:])  # 跳过'body'
        field_errors[field_path] = error["msg"]
    
    # 记录验证错误
    app_logger.api_logger.warning(
        f"Validation error: {field_errors}",
        request_id=request_id,
        field_errors=field_errors,
        url=str(request.url),
        method=request.method
    )
    
    content = {
        "error_code": ErrorCode.VALIDATION_ERROR.value,
        "message": "Validation failed",
        "details": {
            "field_errors": field_errors
        },
        "request_id": request_id
    }
    
    return JSONResponse(status_code=422, content=content)

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """SQLAlchemy异常处理器"""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 记录数据库错误
    app_logger.db_logger.error(
        f"Database error: {str(exc)}",
        request_id=request_id,
        error_type=type(exc).__name__,
        url=str(request.url),
        method=request.method,
        exc_info=True
    )
    
    # 根据异常类型返回不同的错误
    if isinstance(exc, IntegrityError):
        error_code = ErrorCode.CONSTRAINT_VIOLATION
        message = "Data integrity constraint violation"
        status_code = 409
    elif isinstance(exc, NoResultFound):
        error_code = ErrorCode.NOT_FOUND
        message = "Requested resource not found"
        status_code = 404
    else:
        error_code = ErrorCode.DATABASE_ERROR
        message = "Database operation failed"
        status_code = 500
    
    content = {
        "error_code": error_code.value,
        "message": message,
        "details": {},
        "request_id": request_id
    }
    
    # 在开发环境中包含详细错误信息
    from app.core.config import settings
    if settings.is_development:
        content["details"]["database_error"] = str(exc)
    
    return JSONResponse(status_code=status_code, content=content)

async def redis_exception_handler(request: Request, exc: RedisError) -> JSONResponse:
    """Redis异常处理器"""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 记录Redis错误
    app_logger.api_logger.error(
        f"Redis error: {str(exc)}",
        request_id=request_id,
        error_type=type(exc).__name__,
        url=str(request.url),
        method=request.method,
        exc_info=True
    )
    
    content = {
        "error_code": ErrorCode.CACHE_ERROR.value,
        "message": "Cache service temporarily unavailable",
        "details": {},
        "request_id": request_id
    }
    
    return JSONResponse(status_code=503, content=content)

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器"""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 记录未处理的异常
    app_logger.api_logger.error(
        f"Unhandled exception: {str(exc)}",
        request_id=request_id,
        error_type=type(exc).__name__,
        url=str(request.url),
        method=request.method,
        exc_info=True
    )
    
    content = {
        "error_code": ErrorCode.INTERNAL_SERVER_ERROR.value,
        "message": "An unexpected error occurred",
        "details": {},
        "request_id": request_id
    }
    
    # 在开发环境中包含详细错误信息
    from app.core.config import settings
    if settings.is_development:
        content["details"]["exception"] = str(exc)
        content["details"]["exception_type"] = type(exc).__name__
    
    return JSONResponse(status_code=500, content=content)

# 异常处理器注册函数
def setup_exception_handlers(app):
    """设置异常处理器"""
    
    # 注册异常处理器
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(RedisError, redis_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

# 异常工具函数
def create_error_response(
    error_code: ErrorCode,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """创建错误响应"""
    
    response = {
        "error_code": error_code.value,
        "message": message,
        "details": details or {}
    }
    
    if request_id:
        response["request_id"] = request_id
    
    return response

def raise_for_status(condition: bool, exception: BaseAPIException):
    """条件异常抛出"""
    if condition:
        raise exception

def handle_database_error(exc: SQLAlchemyError, operation: str = "database operation"):
    """处理数据库错误"""
    
    if isinstance(exc, IntegrityError):
        # 解析约束违反错误
        error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
        
        if "UNIQUE constraint failed" in error_msg or "duplicate key" in error_msg:
            raise ConflictException(
                ErrorCode.UNIQUE_CONSTRAINT_VIOLATION,
                f"Unique constraint violation during {operation}",
                {"database_error": error_msg}
            )
        elif "FOREIGN KEY constraint failed" in error_msg:
            raise ValidationException(
                f"Foreign key constraint violation during {operation}",
                {"database_error": error_msg}
            )
        else:
            raise DatabaseException(
                ErrorCode.CONSTRAINT_VIOLATION,
                f"Constraint violation during {operation}",
                {"database_error": error_msg}
            )
    
    elif isinstance(exc, NoResultFound):
        raise ResourceNotFoundException(
            ErrorCode.NOT_FOUND,
            "Resource",
            message=f"No result found during {operation}"
        )
    
    else:
        raise DatabaseException(
            ErrorCode.DATABASE_ERROR,
            f"Database error during {operation}",
            {"database_error": str(exc)}
        )