"""统一异常处理模块

定义系统中使用的自定义异常类和异常处理逻辑
"""
from typing import Any, Optional
from fastapi import HTTPException
from utils.status_codes import (
    BUSINESS_ERROR, VALIDATION_ERROR, DATABASE_ERROR, 
    AUTH_ERROR, PERMISSION_ERROR, RESOURCE_ERROR, FILE_ERROR,
    BAD_REQUEST, UNAUTHORIZED, FORBIDDEN, NOT_FOUND, CONFLICT
)


class BusinessException(Exception):
    """业务异常基类"""
    
    def __init__(self, code: str, message: str, data: Any = None, status_code: int = 400):
        self.code = code
        self.message = message
        self.data = data
        self.status_code = status_code
        super().__init__(message)


class ValidationException(BusinessException):
    """数据验证异常"""
    
    def __init__(self, message: str, data: Any = None):
        super().__init__(
            code=VALIDATION_ERROR,
            message=message,
            data=data,
            status_code=400
        )


class DatabaseException(BusinessException):
    """数据库操作异常"""
    
    def __init__(self, message: str, data: Any = None):
        super().__init__(
            code=DATABASE_ERROR,
            message=message,
            data=data,
            status_code=500
        )


class AuthenticationException(BusinessException):
    """认证异常"""
    
    def __init__(self, message: str = "认证失败", data: Any = None):
        super().__init__(
            code=AUTH_ERROR,
            message=message,
            data=data,
            status_code=401
        )


class PermissionException(BusinessException):
    """权限异常"""
    
    def __init__(self, message: str = "权限不足", data: Any = None):
        super().__init__(
            code=PERMISSION_ERROR,
            message=message,
            data=data,
            status_code=403
        )


class ResourceNotFoundException(BusinessException):
    """资源不存在异常"""
    
    def __init__(self, message: str = "资源不存在", data: Any = None, code: str = RESOURCE_ERROR):
        super().__init__(
            code=code,
            message=message,
            data=data,
            status_code=404
        )


class ResourceConflictException(BusinessException):
    """资源冲突异常"""
    
    def __init__(self, message: str = "资源冲突", data: Any = None):
        super().__init__(
            code=CONFLICT,
            message=message,
            data=data,
            status_code=409
        )


class FileOperationException(BusinessException):
    """文件操作异常"""
    
    def __init__(self, message: str, data: Any = None):
        super().__init__(
            code=FILE_ERROR,
            message=message,
            data=data,
            status_code=400
        )


def create_http_exception_from_business_exception(exc: BusinessException) -> HTTPException:
    """将业务异常转换为HTTP异常"""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data
        }
    )


# 异常处理装饰器
def handle_exceptions(func):
    """异常处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BusinessException as e:
            raise create_http_exception_from_business_exception(e)
        except Exception as e:
            # 未知异常，转换为通用业务异常
            raise HTTPException(
                status_code=500,
                detail={
                    "code": BUSINESS_ERROR,
                    "message": f"系统内部错误: {str(e)}",
                    "data": None
                }
            )
    return wrapper


# 异步异常处理装饰器
def handle_async_exceptions(func):
    """异步异常处理装饰器"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BusinessException as e:
            raise create_http_exception_from_business_exception(e)
        except Exception as e:
            # 未知异常，转换为通用业务异常
            raise HTTPException(
                status_code=500,
                detail={
                    "code": BUSINESS_ERROR,
                    "message": f"系统内部错误: {str(e)}",
                    "data": None
                }
            )
    return wrapper