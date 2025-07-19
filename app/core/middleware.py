from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
import time
import uuid
import json
import asyncio
from typing import Callable, Dict, Any, Optional, List
from collections import defaultdict, deque
from datetime import datetime, timedelta
import logging
import traceback
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.logging import app_logger, performance_logger
from app.core.security import verify_api_key

class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成或获取请求ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # 将请求ID添加到请求状态
        request.state.request_id = request_id
        
        # 调用下一个中间件或路由处理器
        response = await call_next(request)
        
        # 在响应头中添加请求ID
        response.headers["X-Request-ID"] = request_id
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """日志记录中间件"""
    
    def __init__(self, app, exclude_paths: List[str] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过不需要记录的路径
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        url = str(request.url)
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        request_id = getattr(request.state, "request_id", "unknown")
        
        # 记录请求开始
        app_logger.api_logger.info(
            f"Request started: {method} {url}",
            request_id=request_id,
            method=method,
            url=url,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算响应时间
            process_time = time.time() - start_time
            
            # 记录请求完成
            app_logger.api_logger.info(
                f"Request completed: {method} {url} - {response.status_code}",
                request_id=request_id,
                method=method,
                url=url,
                status_code=response.status_code,
                response_time=process_time,
                ip_address=client_ip
            )
            
            # 记录慢请求
            performance_logger.log_response_time(
                endpoint=url,
                response_time=process_time,
                threshold=settings.slow_request_threshold
            )
            
            # 在响应头中添加处理时间
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # 计算响应时间
            process_time = time.time() - start_time
            
            # 记录请求错误
            app_logger.api_logger.error(
                f"Request failed: {method} {url} - {str(e)}",
                request_id=request_id,
                method=method,
                url=url,
                error=str(e),
                response_time=process_time,
                ip_address=client_ip,
                exc_info=True
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 返回直接连接的IP
        return request.client.host if request.client else "unknown"

class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    def __init__(self, app, requests_per_minute: int = 60, burst_size: int = 10):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.request_counts = defaultdict(deque)
        self.burst_counts = defaultdict(int)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)
        current_time = datetime.now()
        
        # 检查限流
        if await self._is_rate_limited(client_ip, current_time):
            app_logger.security_logger.warning(
                f"Rate limit exceeded for IP: {client_ip}",
                ip_address=client_ip,
                endpoint=str(request.url),
                event_type="rate_limit_exceeded"
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_minute} requests per minute"
                },
                headers={"Retry-After": "60"}
            )
        
        # 记录请求
        await self._record_request(client_ip, current_time)
        
        return await call_next(request)
    
    async def _is_rate_limited(self, client_ip: str, current_time: datetime) -> bool:
        """检查是否超过限流"""
        # 使用Redis进行分布式限流
        if redis_client:
            try:
                # 滑动窗口限流
                key = f"rate_limit:{client_ip}"
                pipe = redis_client.pipeline()
                
                # 移除过期的请求记录
                cutoff_time = current_time - timedelta(minutes=1)
                pipe.zremrangebyscore(key, 0, cutoff_time.timestamp())
                
                # 获取当前窗口内的请求数
                pipe.zcard(key)
                
                # 添加当前请求
                pipe.zadd(key, {str(uuid.uuid4()): current_time.timestamp()})
                
                # 设置过期时间
                pipe.expire(key, 60)
                
                results = await pipe.execute()
                request_count = results[1]
                
                return request_count >= self.requests_per_minute
                
            except Exception as e:
                logging.error(f"Redis rate limiting error: {e}")
                # Redis失败时使用内存限流
                pass
        
        # 内存限流（单机模式）
        request_times = self.request_counts[client_ip]
        
        # 移除过期的请求记录
        cutoff_time = current_time - timedelta(minutes=1)
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        # 检查是否超过限制
        return len(request_times) >= self.requests_per_minute
    
    async def _record_request(self, client_ip: str, current_time: datetime):
        """记录请求"""
        if not redis_client:
            # 内存记录
            self.request_counts[client_ip].append(current_time)
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 添加安全头
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none';"
            ),
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            )
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response

class APIKeyMiddleware(BaseHTTPMiddleware):
    """API密钥中间件"""
    
    def __init__(self, app, exclude_paths: List[str] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs", "/redoc", "/openapi.json", "/health", "/metrics"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过不需要API密钥的路径
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # 检查API密钥
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "API key required", "message": "X-API-Key header is required"}
            )
        
        # 验证API密钥
        if not await verify_api_key(api_key):
            app_logger.security_logger.warning(
                "Invalid API key used",
                api_key=api_key[:8] + "...",  # 只记录前8位
                ip_address=request.client.host if request.client else "unknown",
                event_type="invalid_api_key"
            )
            
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid API key", "message": "The provided API key is invalid"}
            )
        
        return await call_next(request)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """错误处理中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            # FastAPI的HTTP异常直接抛出
            raise
        except Exception as e:
            # 记录未处理的异常
            request_id = getattr(request.state, "request_id", "unknown")
            
            app_logger.api_logger.error(
                f"Unhandled exception in {request.method} {request.url}",
                request_id=request_id,
                error=str(e),
                traceback=traceback.format_exc(),
                exc_info=True
            )
            
            # 返回通用错误响应
            error_response = {
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "request_id": request_id
            }
            
            # 在开发环境中包含详细错误信息
            if settings.is_development:
                error_response["detail"] = str(e)
                error_response["traceback"] = traceback.format_exc()
            
            return JSONResponse(
                status_code=500,
                content=error_response
            )

class DatabaseMiddleware(BaseHTTPMiddleware):
    """数据库中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 在请求开始时可以进行数据库连接检查等操作
        response = await call_next(request)
        
        # 在请求结束时可以进行清理操作
        return response

class CacheMiddleware(BaseHTTPMiddleware):
    """缓存中间件"""
    
    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
        self.cacheable_methods = {"GET"}
        self.cache_exclude_paths = ["/health", "/metrics"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 只缓存GET请求
        if request.method not in self.cacheable_methods:
            return await call_next(request)
        
        # 跳过不需要缓存的路径
        if request.url.path in self.cache_exclude_paths:
            return await call_next(request)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(request)
        
        # 尝试从缓存获取响应
        if redis_client:
            try:
                cached_response = await redis_client.get(cache_key)
                if cached_response:
                    response_data = json.loads(cached_response)
                    return JSONResponse(
                        content=response_data["content"],
                        status_code=response_data["status_code"],
                        headers={**response_data["headers"], "X-Cache": "HIT"}
                    )
            except Exception as e:
                logging.error(f"Cache retrieval error: {e}")
        
        # 处理请求
        response = await call_next(request)
        
        # 缓存响应（仅对成功的响应进行缓存）
        if response.status_code == 200 and redis_client:
            try:
                # 读取响应内容
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                
                # 解析响应内容
                content = json.loads(response_body.decode())
                
                # 准备缓存数据
                cache_data = {
                    "content": content,
                    "status_code": response.status_code,
                    "headers": dict(response.headers)
                }
                
                # 存储到缓存
                await redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(cache_data)
                )
                
                # 重新创建响应
                response = JSONResponse(
                    content=content,
                    status_code=response.status_code,
                    headers={**response.headers, "X-Cache": "MISS"}
                )
                
            except Exception as e:
                logging.error(f"Cache storage error: {e}")
        
        return response
    
    def _generate_cache_key(self, request: Request) -> str:
        """生成缓存键"""
        # 包含路径、查询参数和用户信息
        key_parts = [
            "cache",
            request.url.path,
            str(sorted(request.query_params.items())),
        ]
        
        # 如果有用户信息，包含用户ID
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            key_parts.append(f"user:{user_id}")
        
        return ":".join(key_parts)

class CompressionMiddleware(BaseHTTPMiddleware):
    """压缩中间件（自定义实现）"""
    
    def __init__(self, app, minimum_size: int = 1024):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 检查是否支持gzip压缩
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding:
            return response
        
        # 检查响应大小
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) < self.minimum_size:
            return response
        
        # 检查内容类型
        content_type = response.headers.get("Content-Type", "")
        compressible_types = [
            "application/json",
            "application/javascript",
            "text/html",
            "text/css",
            "text/plain",
            "text/xml"
        ]
        
        if not any(ct in content_type for ct in compressible_types):
            return response
        
        # 添加压缩头
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
        
        return response

# 中间件配置函数
def setup_middleware(app):
    """设置中间件"""
    
    # 错误处理中间件（最外层）
    app.add_middleware(ErrorHandlingMiddleware)
    
    # 安全头中间件
    app.add_middleware(SecurityHeadersMiddleware)
    
    # CORS中间件
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # 受信任主机中间件
    if settings.trusted_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_hosts
        )
    
    # Gzip压缩中间件
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # 会话中间件
    if settings.session_secret_key:
        app.add_middleware(
            SessionMiddleware,
            secret_key=settings.session_secret_key,
            max_age=settings.session_max_age,
            same_site="lax",
            https_only=settings.is_production
        )
    
    # 限流中间件
    if settings.enable_rate_limiting:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst_size=settings.rate_limit_burst_size
        )
    
    # API密钥中间件（如果启用）
    if settings.require_api_key:
        app.add_middleware(APIKeyMiddleware)
    
    # 缓存中间件
    if settings.enable_response_caching:
        app.add_middleware(
            CacheMiddleware,
            cache_ttl=settings.cache_ttl
        )
    
    # 日志记录中间件
    app.add_middleware(LoggingMiddleware)
    
    # 请求ID中间件（最内层）
    app.add_middleware(RequestIDMiddleware)
    
    # 数据库中间件
    app.add_middleware(DatabaseMiddleware)

# 中间件工具函数
async def get_request_id(request: Request) -> str:
    """获取请求ID"""
    return getattr(request.state, "request_id", "unknown")

async def get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"

async def get_user_agent(request: Request) -> str:
    """获取用户代理"""
    return request.headers.get("User-Agent", "unknown")

# 性能监控装饰器
def monitor_performance(threshold: float = 1.0):
    """性能监控装饰器"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # 记录慢操作
                if execution_time > threshold:
                    performance_logger.log_response_time(
                        endpoint=func.__name__,
                        response_time=execution_time,
                        threshold=threshold
                    )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logging.error(
                    f"Function {func.__name__} failed after {execution_time:.3f}s: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator