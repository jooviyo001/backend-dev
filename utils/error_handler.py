"""增强的错误处理工具模块

提供统一的错误处理、异常捕获、错误日志记录和错误响应格式化功能
"""
import traceback
import logging
import json
from typing import Any, Dict, List, Optional, Union, Type
from datetime import datetime
from functools import wraps
from contextlib import contextmanager

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DataError
from pydantic import ValidationError

from utils.exceptions import (
    BusinessException, ValidationException, DatabaseException,
    AuthException, PermissionException, ResourceException, FileException
)
from utils.status_codes import (
    INTERNAL_ERROR, DATABASE_ERROR, VALIDATION_ERROR,
    AUTH_ERROR, PERMISSION_ERROR, RESOURCE_ERROR, FILE_ERROR
)
from utils.response_utils import error_response

# 配置日志
logger = logging.getLogger(__name__)


class ErrorContext:
    """错误上下文信息"""
    
    def __init__(self, request: Request = None, user_id: str = None, 
                 operation: str = None, resource_id: str = None):
        self.request = request
        self.user_id = user_id
        self.operation = operation
        self.resource_id = resource_id
        self.timestamp = datetime.now()
        self.request_id = getattr(request.state, 'request_id', None) if request else None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        context = {
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'operation': self.operation,
            'resource_id': self.resource_id,
            'request_id': self.request_id
        }
        
        if self.request:
            context.update({
                'method': self.request.method,
                'url': str(self.request.url),
                'client_ip': getattr(self.request.client, 'host', None),
                'user_agent': self.request.headers.get('user-agent')
            })
        
        return {k: v for k, v in context.items() if v is not None}


class ErrorLogger:
    """错误日志记录器"""
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
    
    def log_error(self, error: Exception, context: ErrorContext = None, 
                  extra_data: Dict[str, Any] = None):
        """记录错误日志"""
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        }
        
        if context:
            error_data['context'] = context.to_dict()
        
        if extra_data:
            error_data['extra'] = extra_data
        
        # 根据错误类型选择日志级别
        if isinstance(error, (ValidationException, AuthException, PermissionException)):
            self.logger.warning(f"业务异常: {json.dumps(error_data, ensure_ascii=False, default=str)}")
        elif isinstance(error, (DatabaseException, SQLAlchemyError)):
            self.logger.error(f"数据库异常: {json.dumps(error_data, ensure_ascii=False, default=str)}")
        else:
            self.logger.error(f"系统异常: {json.dumps(error_data, ensure_ascii=False, default=str)}")
    
    def log_warning(self, message: str, context: ErrorContext = None, 
                    extra_data: Dict[str, Any] = None):
        """记录警告日志"""
        log_data = {'message': message}
        
        if context:
            log_data['context'] = context.to_dict()
        
        if extra_data:
            log_data['extra'] = extra_data
        
        self.logger.warning(json.dumps(log_data, ensure_ascii=False, default=str))
    
    def log_info(self, message: str, context: ErrorContext = None, 
                 extra_data: Dict[str, Any] = None):
        """记录信息日志"""
        log_data = {'message': message}
        
        if context:
            log_data['context'] = context.to_dict()
        
        if extra_data:
            log_data['extra'] = extra_data
        
        self.logger.info(json.dumps(log_data, ensure_ascii=False, default=str))


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.error_logger = ErrorLogger()
        self.error_mappings = {
            ValidationError: self._handle_pydantic_validation_error,
            SQLAlchemyError: self._handle_sqlalchemy_error,
            IntegrityError: self._handle_integrity_error,
            DataError: self._handle_data_error,
            BusinessException: self._handle_business_exception,
            HTTPException: self._handle_http_exception,
            ValueError: self._handle_value_error,
            TypeError: self._handle_type_error,
            KeyError: self._handle_key_error,
            AttributeError: self._handle_attribute_error,
            FileNotFoundError: self._handle_file_not_found_error,
            PermissionError: self._handle_permission_error,
            ConnectionError: self._handle_connection_error,
            TimeoutError: self._handle_timeout_error
        }
    
    def handle_error(self, error: Exception, context: ErrorContext = None) -> JSONResponse:
        """处理错误并返回响应"""
        # 记录错误日志
        self.error_logger.log_error(error, context)
        
        # 查找对应的错误处理器
        handler = None
        for error_type, error_handler in self.error_mappings.items():
            if isinstance(error, error_type):
                handler = error_handler
                break
        
        if handler:
            return handler(error, context)
        else:
            return self._handle_unknown_error(error, context)
    
    def _handle_pydantic_validation_error(self, error: ValidationError, 
                                          context: ErrorContext = None) -> JSONResponse:
        """处理Pydantic验证错误"""
        errors = []
        for err in error.errors():
            field = '.'.join(str(loc) for loc in err['loc'])
            message = err['msg']
            errors.append(f"{field}: {message}")
        
        return error_response(
            code=VALIDATION_ERROR,
            message=f"数据验证失败: {errors[0]}",
            data={'errors': errors},
            status_code=400
        )
    
    def _handle_sqlalchemy_error(self, error: SQLAlchemyError, 
                                 context: ErrorContext = None) -> JSONResponse:
        """处理SQLAlchemy错误"""
        return error_response(
            code=DATABASE_ERROR,
            message="数据库操作失败",
            data={'detail': str(error)},
            status_code=500
        )
    
    def _handle_integrity_error(self, error: IntegrityError, 
                                context: ErrorContext = None) -> JSONResponse:
        """处理数据完整性错误"""
        message = "数据完整性约束违反"
        
        # 尝试解析具体的约束违反类型
        error_msg = str(error.orig).lower()
        if 'unique' in error_msg or 'duplicate' in error_msg:
            message = "数据已存在，不能重复"
        elif 'foreign key' in error_msg:
            message = "关联数据不存在"
        elif 'not null' in error_msg:
            message = "必填字段不能为空"
        
        return error_response(
            code=DATABASE_ERROR,
            message=message,
            data={'detail': str(error.orig)},
            status_code=400
        )
    
    def _handle_data_error(self, error: DataError, 
                           context: ErrorContext = None) -> JSONResponse:
        """处理数据类型错误"""
        return error_response(
            code=DATABASE_ERROR,
            message="数据格式错误",
            data={'detail': str(error.orig)},
            status_code=400
        )
    
    def _handle_business_exception(self, error: BusinessException, 
                                   context: ErrorContext = None) -> JSONResponse:
        """处理业务异常"""
        return error_response(
            code=error.code,
            message=error.message,
            data=error.data,
            status_code=error.status_code
        )
    
    def _handle_http_exception(self, error: HTTPException, 
                               context: ErrorContext = None) -> JSONResponse:
        """处理HTTP异常"""
        return error_response(
            code=str(error.status_code),
            message=str(error.detail),
            status_code=error.status_code
        )
    
    def _handle_value_error(self, error: ValueError, 
                            context: ErrorContext = None) -> JSONResponse:
        """处理值错误"""
        return error_response(
            code=VALIDATION_ERROR,
            message=f"参数值错误: {str(error)}",
            status_code=400
        )
    
    def _handle_type_error(self, error: TypeError, 
                           context: ErrorContext = None) -> JSONResponse:
        """处理类型错误"""
        return error_response(
            code=VALIDATION_ERROR,
            message=f"参数类型错误: {str(error)}",
            status_code=400
        )
    
    def _handle_key_error(self, error: KeyError, 
                          context: ErrorContext = None) -> JSONResponse:
        """处理键错误"""
        return error_response(
            code=VALIDATION_ERROR,
            message=f"缺少必要参数: {str(error)}",
            status_code=400
        )
    
    def _handle_attribute_error(self, error: AttributeError, 
                                context: ErrorContext = None) -> JSONResponse:
        """处理属性错误"""
        return error_response(
            code=INTERNAL_ERROR,
            message="系统内部错误",
            data={'detail': str(error)},
            status_code=500
        )
    
    def _handle_file_not_found_error(self, error: FileNotFoundError, 
                                     context: ErrorContext = None) -> JSONResponse:
        """处理文件未找到错误"""
        return error_response(
            code=FILE_ERROR,
            message="文件不存在",
            data={'detail': str(error)},
            status_code=404
        )
    
    def _handle_permission_error(self, error: PermissionError, 
                                 context: ErrorContext = None) -> JSONResponse:
        """处理权限错误"""
        return error_response(
            code=PERMISSION_ERROR,
            message="权限不足",
            data={'detail': str(error)},
            status_code=403
        )
    
    def _handle_connection_error(self, error: ConnectionError, 
                                 context: ErrorContext = None) -> JSONResponse:
        """处理连接错误"""
        return error_response(
            code=INTERNAL_ERROR,
            message="服务连接失败",
            data={'detail': str(error)},
            status_code=503
        )
    
    def _handle_timeout_error(self, error: TimeoutError, 
                              context: ErrorContext = None) -> JSONResponse:
        """处理超时错误"""
        return error_response(
            code=INTERNAL_ERROR,
            message="请求超时",
            data={'detail': str(error)},
            status_code=504
        )
    
    def _handle_unknown_error(self, error: Exception, 
                              context: ErrorContext = None) -> JSONResponse:
        """处理未知错误"""
        return error_response(
            code=INTERNAL_ERROR,
            message="系统内部错误",
            data={'detail': str(error)},
            status_code=500
        )


# 全局错误处理器实例
global_error_handler = ErrorHandler()


def handle_exceptions(context_factory: callable = None):
    """异常处理装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = None
                if context_factory:
                    context = context_factory(*args, **kwargs)
                
                response = global_error_handler.handle_error(e, context)
                raise HTTPException(
                    status_code=response.status_code,
                    detail=json.loads(response.body.decode())
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = None
                if context_factory:
                    context = context_factory(*args, **kwargs)
                
                response = global_error_handler.handle_error(e, context)
                raise HTTPException(
                    status_code=response.status_code,
                    detail=json.loads(response.body.decode())
                )
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def safe_execute(func, *args, default_value=None, log_error=True, **kwargs):
    """安全执行函数，捕获异常并返回默认值"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            global_error_handler.error_logger.log_error(e)
        return default_value


@contextmanager
def error_context(operation: str = None, resource_id: str = None, 
                  user_id: str = None, request: Request = None):
    """错误上下文管理器"""
    context = ErrorContext(
        request=request,
        user_id=user_id,
        operation=operation,
        resource_id=resource_id
    )
    
    try:
        yield context
    except Exception as e:
        response = global_error_handler.handle_error(e, context)
        raise HTTPException(
            status_code=response.status_code,
            detail=json.loads(response.body.decode())
        )


class DatabaseErrorHandler:
    """数据库错误处理器"""
    
    @staticmethod
    def handle_db_operation(func):
        """数据库操作错误处理装饰器"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrityError as e:
                error_msg = str(e.orig).lower()
                if 'unique' in error_msg or 'duplicate' in error_msg:
                    raise ValidationException("数据已存在，不能重复")
                elif 'foreign key' in error_msg:
                    raise ValidationException("关联数据不存在")
                elif 'not null' in error_msg:
                    raise ValidationException("必填字段不能为空")
                else:
                    raise DatabaseException(f"数据完整性约束违反: {str(e.orig)}")
            except DataError as e:
                raise ValidationException(f"数据格式错误: {str(e.orig)}")
            except SQLAlchemyError as e:
                raise DatabaseException(f"数据库操作失败: {str(e)}")
        
        return wrapper


class ValidationErrorHandler:
    """验证错误处理器"""
    
    @staticmethod
    def format_validation_errors(errors: List[Dict[str, Any]]) -> List[str]:
        """格式化验证错误信息"""
        formatted_errors = []
        for error in errors:
            field = '.'.join(str(loc) for loc in error.get('loc', []))
            message = error.get('msg', '验证失败')
            formatted_errors.append(f"{field}: {message}")
        return formatted_errors
    
    @staticmethod
    def create_validation_response(errors: List[str]) -> JSONResponse:
        """创建验证错误响应"""
        return error_response(
            code=VALIDATION_ERROR,
            message=f"数据验证失败: {errors[0]}",
            data={'errors': errors},
            status_code=400
        )


class APIErrorHandler:
    """API错误处理器"""
    
    def __init__(self):
        self.error_handler = ErrorHandler()
    
    async def handle_api_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理API错误"""
        # 创建错误上下文
        context = ErrorContext(
            request=request,
            user_id=getattr(request.state, 'user_id', None),
            operation=f"{request.method} {request.url.path}"
        )
        
        return self.error_handler.handle_error(exc, context)


# 预定义的错误处理器实例
api_error_handler = APIErrorHandler()
db_error_handler = DatabaseErrorHandler()
validation_error_handler = ValidationErrorHandler()


# 常用的错误处理装饰器
def handle_db_errors(func):
    """数据库错误处理装饰器"""
    return db_error_handler.handle_db_operation(func)


def handle_api_errors(func):
    """API错误处理装饰器"""
    return handle_exceptions()(func)


def log_errors(operation: str = None):
    """错误日志记录装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(operation=operation or func.__name__)
                global_error_handler.error_logger.log_error(e, context)
                raise
        return wrapper
    return decorator


# 错误统计和监控
class ErrorMonitor:
    """错误监控器"""
    
    def __init__(self):
        self.error_counts = {}
        self.error_history = []
        self.max_history_size = 1000
    
    def record_error(self, error: Exception, context: ErrorContext = None):
        """记录错误"""
        error_type = type(error).__name__
        
        # 更新错误计数
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # 添加到历史记录
        error_record = {
            'timestamp': datetime.now(),
            'error_type': error_type,
            'error_message': str(error),
            'context': context.to_dict() if context else None
        }
        
        self.error_history.append(error_record)
        
        # 限制历史记录大小
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_counts': self.error_counts.copy(),
            'recent_errors': self.error_history[-10:],  # 最近10个错误
            'error_rate': len([e for e in self.error_history 
                              if (datetime.now() - e['timestamp']).seconds < 3600]) / 3600  # 每小时错误率
        }
    
    def clear_statistics(self):
        """清除统计信息"""
        self.error_counts.clear()
        self.error_history.clear()


# 全局错误监控器
global_error_monitor = ErrorMonitor()