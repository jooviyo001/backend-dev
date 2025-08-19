"""API响应格式化和中间件增强工具模块

提供统一的API响应格式、请求处理、性能监控、限流等功能
"""
import time
import json
import uuid
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict, deque

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from utils.status_codes import SUCCESS, INTERNAL_ERROR, RATE_LIMIT_ERROR
from utils.logging_middleware import logger
from utils.security_utils import security_auditor


class APIResponse:
    """统一API响应格式"""
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", 
                code: str = SUCCESS, meta: Dict[str, Any] = None) -> JSONResponse:
        """成功响应"""
        response_data = {
            "success": True,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if meta:
            response_data["meta"] = meta
        
        return JSONResponse(content=response_data, status_code=200)
    
    @staticmethod
    def error(message: str = "操作失败", code: str = INTERNAL_ERROR, 
              data: Any = None, status_code: int = 500, 
              meta: Dict[str, Any] = None) -> JSONResponse:
        """错误响应"""
        response_data = {
            "success": False,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if meta:
            response_data["meta"] = meta
        
        return JSONResponse(content=response_data, status_code=status_code)
    
    @staticmethod
    def paginated(data: List[Any], total: int, page: int = 1, 
                  limit: int = 10, message: str = "查询成功") -> JSONResponse:
        """分页响应"""
        total_pages = (total + limit - 1) // limit
        
        meta = {
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
        return APIResponse.success(data=data, message=message, meta=meta)
    
    @staticmethod
    def created(data: Any = None, message: str = "创建成功", 
                resource_id: str = None) -> JSONResponse:
        """创建成功响应"""
        meta = {}
        if resource_id:
            meta["resource_id"] = resource_id
        
        response = APIResponse.success(data=data, message=message, meta=meta)
        response.status_code = 201
        return response
    
    @staticmethod
    def no_content(message: str = "操作成功") -> JSONResponse:
        """无内容响应"""
        response = APIResponse.success(message=message)
        response.status_code = 204
        return response
    
    @staticmethod
    def not_found(message: str = "资源不存在", resource: str = None) -> JSONResponse:
        """资源不存在响应"""
        meta = {}
        if resource:
            meta["resource"] = resource
        
        return APIResponse.error(
            message=message, 
            code="RESOURCE_NOT_FOUND", 
            status_code=404,
            meta=meta
        )
    
    @staticmethod
    def forbidden(message: str = "权限不足") -> JSONResponse:
        """权限不足响应"""
        return APIResponse.error(
            message=message, 
            code="PERMISSION_DENIED", 
            status_code=403
        )
    
    @staticmethod
    def unauthorized(message: str = "未授权访问") -> JSONResponse:
        """未授权响应"""
        return APIResponse.error(
            message=message, 
            code="UNAUTHORIZED", 
            status_code=401
        )
    
    @staticmethod
    def bad_request(message: str = "请求参数错误", errors: List[str] = None) -> JSONResponse:
        """请求错误响应"""
        data = None
        if errors:
            data = {"errors": errors}
        
        return APIResponse.error(
            message=message, 
            code="BAD_REQUEST", 
            data=data,
            status_code=400
        )
    
    @staticmethod
    def rate_limited(message: str = "请求过于频繁", retry_after: int = None) -> JSONResponse:
        """限流响应"""
        meta = {}
        if retry_after:
            meta["retry_after"] = retry_after
        
        response = APIResponse.error(
            message=message, 
            code=RATE_LIMIT_ERROR, 
            status_code=429,
            meta=meta
        )
        
        if retry_after:
            response.headers["Retry-After"] = str(retry_after)
        
        return response


class RequestTracker:
    """请求跟踪器"""
    
    def __init__(self):
        self.active_requests = {}
        self.request_history = deque(maxlen=1000)
        self.performance_stats = {
            "total_requests": 0,
            "total_response_time": 0,
            "avg_response_time": 0,
            "max_response_time": 0,
            "min_response_time": float('inf'),
            "error_count": 0,
            "success_count": 0
        }
    
    def start_request(self, request_id: str, request: Request) -> Dict[str, Any]:
        """开始跟踪请求"""
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": getattr(request.client, 'host', None),
            "user_agent": request.headers.get('user-agent'),
            "start_time": time.time(),
            "timestamp": datetime.now()
        }
        
        self.active_requests[request_id] = request_info
        return request_info
    
    def end_request(self, request_id: str, response: Response = None, 
                    error: Exception = None) -> Dict[str, Any]:
        """结束跟踪请求"""
        if request_id not in self.active_requests:
            return None
        
        request_info = self.active_requests.pop(request_id)
        end_time = time.time()
        response_time = end_time - request_info["start_time"]
        
        # 更新请求信息
        request_info.update({
            "end_time": end_time,
            "response_time": response_time,
            "status_code": getattr(response, 'status_code', None),
            "error": str(error) if error else None,
            "success": error is None
        })
        
        # 添加到历史记录
        self.request_history.append(request_info)
        
        # 更新性能统计
        self._update_performance_stats(request_info)
        
        return request_info
    
    def _update_performance_stats(self, request_info: Dict[str, Any]):
        """更新性能统计"""
        response_time = request_info["response_time"]
        
        self.performance_stats["total_requests"] += 1
        self.performance_stats["total_response_time"] += response_time
        
        if request_info["success"]:
            self.performance_stats["success_count"] += 1
        else:
            self.performance_stats["error_count"] += 1
        
        # 更新响应时间统计
        if response_time > self.performance_stats["max_response_time"]:
            self.performance_stats["max_response_time"] = response_time
        
        if response_time < self.performance_stats["min_response_time"]:
            self.performance_stats["min_response_time"] = response_time
        
        # 计算平均响应时间
        if self.performance_stats["total_requests"] > 0:
            self.performance_stats["avg_response_time"] = (
                self.performance_stats["total_response_time"] / 
                self.performance_stats["total_requests"]
            )
    
    def get_active_requests(self) -> List[Dict[str, Any]]:
        """获取活跃请求"""
        return list(self.active_requests.values())
    
    def get_request_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取请求历史"""
        return list(self.request_history)[-limit:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = self.performance_stats.copy()
        
        # 计算成功率
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["success_count"] / stats["total_requests"] * 100
            stats["error_rate"] = stats["error_count"] / stats["total_requests"] * 100
        else:
            stats["success_rate"] = 0
            stats["error_rate"] = 0
        
        # 格式化响应时间
        stats["avg_response_time"] = round(stats["avg_response_time"], 3)
        stats["max_response_time"] = round(stats["max_response_time"], 3)
        stats["min_response_time"] = round(stats["min_response_time"], 3) if stats["min_response_time"] != float('inf') else 0
        
        return stats
    
    def clear_stats(self):
        """清除统计信息"""
        self.active_requests.clear()
        self.request_history.clear()
        self.performance_stats = {
            "total_requests": 0,
            "total_response_time": 0,
            "avg_response_time": 0,
            "max_response_time": 0,
            "min_response_time": float('inf'),
            "error_count": 0,
            "success_count": 0
        }


class RateLimiter:
    """限流器"""
    
    def __init__(self):
        self.requests = defaultdict(deque)
        self.blocked_ips = {}
    
    def is_allowed(self, identifier: str, limit: int = 100, 
                   window: int = 3600, block_duration: int = 3600) -> tuple:
        """检查是否允许请求"""
        current_time = time.time()
        
        # 检查是否被阻止
        if identifier in self.blocked_ips:
            if current_time < self.blocked_ips[identifier]:
                remaining_time = int(self.blocked_ips[identifier] - current_time)
                return False, remaining_time
            else:
                # 解除阻止
                del self.blocked_ips[identifier]
        
        # 清理过期的请求记录
        request_times = self.requests[identifier]
        while request_times and request_times[0] < current_time - window:
            request_times.popleft()
        
        # 检查是否超过限制
        if len(request_times) >= limit:
            # 阻止该标识符
            self.blocked_ips[identifier] = current_time + block_duration
            return False, block_duration
        
        # 记录当前请求
        request_times.append(current_time)
        return True, 0
    
    def get_request_count(self, identifier: str, window: int = 3600) -> int:
        """获取指定时间窗口内的请求数量"""
        current_time = time.time()
        request_times = self.requests[identifier]
        
        # 清理过期的请求记录
        while request_times and request_times[0] < current_time - window:
            request_times.popleft()
        
        return len(request_times)
    
    def reset_limit(self, identifier: str):
        """重置限制"""
        if identifier in self.requests:
            del self.requests[identifier]
        if identifier in self.blocked_ips:
            del self.blocked_ips[identifier]
    
    def get_blocked_ips(self) -> Dict[str, float]:
        """获取被阻止的IP列表"""
        current_time = time.time()
        
        # 清理过期的阻止记录
        expired_ips = [ip for ip, unblock_time in self.blocked_ips.items() 
                       if current_time >= unblock_time]
        
        for ip in expired_ips:
            del self.blocked_ips[ip]
        
        return self.blocked_ips.copy()


class APIMiddleware(BaseHTTPMiddleware):
    """API中间件"""
    
    def __init__(self, app, enable_rate_limit: bool = True, 
                 enable_request_tracking: bool = True,
                 enable_security_audit: bool = True,
                 rate_limit_per_hour: int = 1000,
                 rate_limit_per_minute: int = 60):
        super().__init__(app)
        self.enable_rate_limit = enable_rate_limit
        self.enable_request_tracking = enable_request_tracking
        self.enable_security_audit = enable_security_audit
        self.rate_limit_per_hour = rate_limit_per_hour
        self.rate_limit_per_minute = rate_limit_per_minute
        
        # 初始化组件
        self.request_tracker = RequestTracker() if enable_request_tracking else None
        self.rate_limiter = RateLimiter() if enable_rate_limit else None
        
        # 跳过的路径
        self.skip_paths = {
            '/health', '/metrics', '/docs', '/redoc', '/openapi.json'
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """处理请求"""
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 获取客户端IP
        client_ip = self._get_client_ip(request)
        request.state.client_ip = client_ip
        
        # 跳过特定路径
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # 限流检查
        if self.enable_rate_limit and self.rate_limiter:
            # 每小时限制
            allowed, retry_after = self.rate_limiter.is_allowed(
                f"hour:{client_ip}", self.rate_limit_per_hour, 3600
            )
            if not allowed:
                return APIResponse.rate_limited(retry_after=retry_after)
            
            # 每分钟限制
            allowed, retry_after = self.rate_limiter.is_allowed(
                f"minute:{client_ip}", self.rate_limit_per_minute, 60
            )
            if not allowed:
                return APIResponse.rate_limited(retry_after=retry_after)
        
        # 开始请求跟踪
        if self.enable_request_tracking and self.request_tracker:
            self.request_tracker.start_request(request_id, request)
        
        # 安全审计
        if self.enable_security_audit:
            security_auditor.log_security_event(
                event_type="API_REQUEST",
                user_id=getattr(request.state, 'user_id', None),
                resource=request.url.path,
                action=request.method,
                ip_address=client_ip,
                user_agent=request.headers.get('user-agent'),
                success=True
            )
        
        # 处理请求
        start_time = time.time()
        response = None
        error = None
        
        try:
            response = await call_next(request)
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = str(round((time.time() - start_time) * 1000, 2))
            
            return response
            
        except Exception as e:
            error = e
            logger.error(f"请求处理异常: {str(e)}", extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "client_ip": client_ip
            })
            
            # 返回错误响应
            return APIResponse.error(
                message="服务器内部错误",
                code=INTERNAL_ERROR,
                meta={"request_id": request_id}
            )
        
        finally:
            # 结束请求跟踪
            if self.enable_request_tracking and self.request_tracker:
                self.request_tracker.end_request(request_id, response, error)
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # 返回直接连接的IP
        return getattr(request.client, 'host', '127.0.0.1')


class ResponseFormatter:
    """响应格式化器"""
    
    @staticmethod
    def format_validation_errors(errors: List[Dict[str, Any]]) -> List[str]:
        """格式化验证错误"""
        formatted_errors = []
        for error in errors:
            field = '.'.join(str(loc) for loc in error.get('loc', []))
            message = error.get('msg', '验证失败')
            formatted_errors.append(f"{field}: {message}")
        return formatted_errors
    
    @staticmethod
    def format_database_error(error: Exception) -> str:
        """格式化数据库错误"""
        error_msg = str(error).lower()
        
        if 'unique' in error_msg or 'duplicate' in error_msg:
            return "数据已存在，不能重复"
        elif 'foreign key' in error_msg:
            return "关联数据不存在"
        elif 'not null' in error_msg:
            return "必填字段不能为空"
        elif 'check constraint' in error_msg:
            return "数据不符合约束条件"
        else:
            return "数据库操作失败"
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化时间间隔"""
        if seconds < 1:
            return f"{seconds * 1000:.1f} ms"
        elif seconds < 60:
            return f"{seconds:.1f} s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} min"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} h"


class APIValidator:
    """API验证器"""
    
    @staticmethod
    def validate_pagination_params(page: int = 1, limit: int = 10, 
                                   max_page_size: int = 100) -> tuple:
        """验证分页参数"""
        if page < 1:
            raise HTTPException(status_code=400, detail="页码必须大于0")
        
        if limit < 1:
            raise HTTPException(status_code=400, detail="每页大小必须大于0")
        
        if limit > max_page_size:
            raise HTTPException(status_code=400, detail=f"每页大小不能超过{max_page_size}")
        
        return page, limit
    
    @staticmethod
    def validate_sort_params(sort_by: str = None, sort_order: str = "asc", 
                             allowed_fields: List[str] = None) -> tuple:
        """验证排序参数"""
        if sort_order not in ["asc", "desc"]:
            raise HTTPException(status_code=400, detail="排序方向必须是asc或desc")
        
        if sort_by and allowed_fields and sort_by not in allowed_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"排序字段必须是以下之一: {', '.join(allowed_fields)}"
            )
        
        return sort_by, sort_order
    
    @staticmethod
    def validate_date_range(start_date: str = None, end_date: str = None) -> tuple:
        """验证日期范围"""
        start_dt = None
        end_dt = None
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="开始日期格式错误")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="结束日期格式错误")
        
        if start_dt and end_dt and start_dt > end_dt:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        
        return start_dt, end_dt


# 全局实例
api_response = APIResponse()
request_tracker = RequestTracker()
rate_limiter = RateLimiter()
response_formatter = ResponseFormatter()
api_validator = APIValidator()


# 装饰器
def api_response_format(success_message: str = "操作成功", 
                        error_message: str = "操作失败"):
    """API响应格式化装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, JSONResponse):
                    return result
                return APIResponse.success(data=result, message=success_message)
            except HTTPException as e:
                return APIResponse.error(
                    message=str(e.detail),
                    code=str(e.status_code),
                    status_code=e.status_code
                )
            except Exception as e:
                logger.error(f"API处理异常: {str(e)}")
                return APIResponse.error(message=error_message)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if isinstance(result, JSONResponse):
                    return result
                return APIResponse.success(data=result, message=success_message)
            except HTTPException as e:
                return APIResponse.error(
                    message=str(e.detail),
                    code=str(e.status_code),
                    status_code=e.status_code
                )
            except Exception as e:
                logger.error(f"API处理异常: {str(e)}")
                return APIResponse.error(message=error_message)
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def validate_pagination(max_page_size: int = 100):
    """分页验证装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            page = kwargs.get('page', 1)
            limit = kwargs.get('limit', 10)
            
            page, limit = api_validator.validate_pagination_params(
                page, limit, max_page_size
            )
            
            kwargs['page'] = page
            kwargs['limit'] = limit
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def track_performance(operation_name: str = None):
    """性能跟踪装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or func.__name__
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(f"操作 {operation} 完成，耗时: {duration:.3f}s")
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"操作 {operation} 失败，耗时: {duration:.3f}s，错误: {str(e)}")
                raise
        
        return wrapper
    return decorator


# 常用的API工具函数
def get_request_info(request: Request) -> Dict[str, Any]:
    """获取请求信息"""
    return {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "client_ip": getattr(request.client, 'host', None),
        "user_agent": request.headers.get('user-agent'),
        "request_id": getattr(request.state, 'request_id', None)
    }


def extract_user_info(request: Request) -> Dict[str, Any]:
    """从请求中提取用户信息"""
    return {
        "user_id": getattr(request.state, 'user_id', None),
        "username": getattr(request.state, 'username', None),
        "roles": getattr(request.state, 'roles', []),
        "permissions": getattr(request.state, 'permissions', [])
    }


def build_query_filters(params: Dict[str, Any], 
                        allowed_filters: List[str] = None) -> Dict[str, Any]:
    """构建查询过滤器"""
    filters = {}
    
    for key, value in params.items():
        if value is not None and (not allowed_filters or key in allowed_filters):
            filters[key] = value
    
    return filters