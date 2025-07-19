import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from app.core.config import settings
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "ip_address"):
            log_entry["ip_address"] = record.ip_address
        
        if hasattr(record, "user_agent"):
            log_entry["user_agent"] = record.user_agent
        
        if hasattr(record, "endpoint"):
            log_entry["endpoint"] = record.endpoint
        
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        
        if hasattr(record, "response_time"):
            log_entry["response_time"] = record.response_time
        
        return json.dumps(log_entry, ensure_ascii=False)

class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # 获取颜色
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # 格式化时间
        record.asctime = self.formatTime(record, self.datefmt)
        
        # 构建日志消息
        log_message = (
            f"{color}[{record.asctime}] "
            f"{record.levelname:8} "
            f"{record.name}:{record.lineno} - "
            f"{record.getMessage()}{reset}"
        )
        
        # 添加异常信息
        if record.exc_info:
            log_message += "\n" + self.formatException(record.exc_info)
        
        return log_message

class RequestLogFilter(logging.Filter):
    """请求日志过滤器"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # 过滤掉健康检查等不重要的请求
        if hasattr(record, 'endpoint'):
            excluded_endpoints = ['/health', '/metrics', '/favicon.ico']
            return record.endpoint not in excluded_endpoints
        return True

class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""
    
    SENSITIVE_FIELDS = [
        'password', 'token', 'secret', 'key', 'authorization',
        'cookie', 'session', 'csrf', 'api_key'
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        # 检查并替换敏感信息
        message = record.getMessage().lower()
        
        for field in self.SENSITIVE_FIELDS:
            if field in message:
                # 简单的敏感信息掩码
                record.msg = str(record.msg).replace(
                    field, f"{field}=***MASKED***"
                )
        
        return True

def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_json: bool = False,
    enable_colors: bool = True
) -> None:
    """设置日志配置"""
    
    # 使用配置中的默认值
    log_level = log_level or settings.log_level
    log_file = log_file or settings.log_file
    
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    if enable_colors and sys.stdout.isatty():
        console_formatter = ColoredFormatter(
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用轮转文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=settings.log_max_size,
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        if enable_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)-8s %(name)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("aioredis").setLevel(logging.WARNING)
    
    # 如果是开发环境，显示更多SQL日志
    if settings.is_development and settings.database_echo:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)

class LoggerMixin:
    """日志记录器混入类"""
    
    @property
    def logger(self) -> logging.Logger:
        """获取类的日志记录器"""
        return logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: int, message: str, **kwargs):
        """记录结构化日志"""
        extra = {}
        for key, value in kwargs.items():
            extra[key] = value
        
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """记录异常日志"""
        kwargs['exc_info'] = True
        self._log(logging.ERROR, message, **kwargs)

# 应用程序特定的日志记录器
class AppLogger:
    """应用程序日志记录器"""
    
    def __init__(self):
        self.auth_logger = StructuredLogger("app.auth")
        self.api_logger = StructuredLogger("app.api")
        self.db_logger = StructuredLogger("app.database")
        self.security_logger = StructuredLogger("app.security")
        self.business_logger = StructuredLogger("app.business")
    
    def log_login_attempt(self, username: str, ip_address: str, success: bool, **kwargs):
        """记录登录尝试"""
        message = f"Login {'successful' if success else 'failed'} for user: {username}"
        level = logging.INFO if success else logging.WARNING
        
        self.auth_logger._log(
            level, message,
            username=username,
            ip_address=ip_address,
            success=success,
            **kwargs
        )
    
    def log_api_request(self, method: str, endpoint: str, user_id: str = None, 
                       ip_address: str = None, response_time: float = None, 
                       status_code: int = None, **kwargs):
        """记录API请求"""
        message = f"{method} {endpoint}"
        
        self.api_logger._log(
            logging.INFO, message,
            method=method,
            endpoint=endpoint,
            user_id=user_id,
            ip_address=ip_address,
            response_time=response_time,
            status_code=status_code,
            **kwargs
        )
    
    def log_database_operation(self, operation: str, table: str, user_id: str = None, 
                              record_id: str = None, **kwargs):
        """记录数据库操作"""
        message = f"Database {operation} on {table}"
        
        self.db_logger._log(
            logging.INFO, message,
            operation=operation,
            table=table,
            user_id=user_id,
            record_id=record_id,
            **kwargs
        )
    
    def log_security_event(self, event_type: str, user_id: str = None, 
                          ip_address: str = None, details: str = None, **kwargs):
        """记录安全事件"""
        message = f"Security event: {event_type}"
        
        self.security_logger._log(
            logging.WARNING, message,
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            **kwargs
        )
    
    def log_business_event(self, event_type: str, user_id: str = None, 
                          entity_type: str = None, entity_id: str = None, 
                          details: str = None, **kwargs):
        """记录业务事件"""
        message = f"Business event: {event_type}"
        
        self.business_logger._log(
            logging.INFO, message,
            event_type=event_type,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            **kwargs
        )

# 全局应用程序日志记录器实例
app_logger = AppLogger()

# 日志装饰器
def log_function_call(logger: logging.Logger = None):
    """函数调用日志装饰器"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or logging.getLogger(func.__module__)
            func_name = f"{func.__module__}.{func.__name__}"
            
            func_logger.debug(f"Calling function: {func_name}")
            
            try:
                result = func(*args, **kwargs)
                func_logger.debug(f"Function {func_name} completed successfully")
                return result
            except Exception as e:
                func_logger.error(
                    f"Function {func_name} failed with error: {str(e)}",
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator

def log_async_function_call(logger: logging.Logger = None):
    """异步函数调用日志装饰器"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            func_logger = logger or logging.getLogger(func.__module__)
            func_name = f"{func.__module__}.{func.__name__}"
            
            func_logger.debug(f"Calling async function: {func_name}")
            
            try:
                result = await func(*args, **kwargs)
                func_logger.debug(f"Async function {func_name} completed successfully")
                return result
            except Exception as e:
                func_logger.error(
                    f"Async function {func_name} failed with error: {str(e)}",
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator

# 性能监控日志
class PerformanceLogger:
    """性能监控日志记录器"""
    
    def __init__(self):
        self.logger = StructuredLogger("app.performance")
    
    def log_slow_query(self, query: str, execution_time: float, threshold: float = 1.0):
        """记录慢查询"""
        if execution_time > threshold:
            self.logger.warning(
                f"Slow query detected: {execution_time:.3f}s",
                query=query,
                execution_time=execution_time,
                threshold=threshold
            )
    
    def log_memory_usage(self, memory_mb: float, threshold: float = 500.0):
        """记录内存使用情况"""
        if memory_mb > threshold:
            self.logger.warning(
                f"High memory usage: {memory_mb:.2f}MB",
                memory_mb=memory_mb,
                threshold=threshold
            )
    
    def log_response_time(self, endpoint: str, response_time: float, threshold: float = 2.0):
        """记录响应时间"""
        if response_time > threshold:
            self.logger.warning(
                f"Slow response: {endpoint} took {response_time:.3f}s",
                endpoint=endpoint,
                response_time=response_time,
                threshold=threshold
            )

# 全局性能日志记录器实例
performance_logger = PerformanceLogger()

# 初始化日志系统
def init_logging():
    """初始化日志系统"""
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        enable_json=settings.is_production,
        enable_colors=settings.is_development
    )
    
    logger = get_logger(__name__)
    logger.info(f"Logging initialized - Level: {settings.log_level}, Environment: {settings.environment}")