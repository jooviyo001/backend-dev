"""
请求和响应日志中间件
用于记录API请求和响应的详细信息，方便调试
"""

import time
import json
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
import uuid

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("API_Logger")

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """请求响应日志中间件"""
    
    def __init__(self, app, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        logger.setLevel(self.log_level)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID用于追踪
        request_id = str(uuid.uuid4())[:8]
        
        # 记录请求开始时间
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        url = str(request.url)
        headers = dict(request.headers)
        client_ip = request.client.host if request.client else "unknown"
        
        # 读取请求体（如果存在）
        request_body = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # 尝试解析JSON
                    try:
                        request_body = json.loads(body.decode('utf-8'))
                        # 隐藏敏感信息
                        if isinstance(request_body, dict):
                            request_body = self._mask_sensitive_data(request_body)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_body = f"<binary data: {len(body)} bytes>"
                
                # 重新构建请求体供后续处理
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.warning(f"读取请求体失败: {e}")
        
        # 记录请求日志
        self._log_request(request_id, method, url, headers, client_ip, request_body)
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 获取响应信息
            status_code = response.status_code
            response_headers = dict(response.headers)
            
            # 读取响应体
            response_body = None
            if hasattr(response, 'body'):
                try:
                    if isinstance(response, StreamingResponse):
                        # 对于流式响应，不读取内容
                        response_body = "<streaming response>"
                    else:
                        # 读取响应体
                        body_bytes = b""
                        async for chunk in response.body_iterator:
                            body_bytes += chunk
                        
                        if body_bytes:
                            try:
                                response_body = json.loads(body_bytes.decode('utf-8'))
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                response_body = f"<binary data: {len(body_bytes)} bytes>"
                        
                        # 重新创建响应
                        response = Response(
                            content=body_bytes,
                            status_code=status_code,
                            headers=response_headers,
                            media_type=response.media_type
                        )
                except Exception as e:
                    logger.warning(f"读取响应体失败: {e}")
                    response_body = f"<error reading response: {e}>"
            
            # 记录响应日志
            self._log_response(request_id, status_code, response_headers, response_body, process_time)
            
            return response
            
        except Exception as e:
            # 记录异常
            process_time = time.time() - start_time
            logger.error(f"[{request_id}] 请求处理异常: {str(e)}, 耗时: {process_time:.3f}s")
            raise
    
    def _log_request(self, request_id: str, method: str, url: str, headers: dict, client_ip: str, body):
        """记录请求日志"""
        # 过滤敏感头信息
        filtered_headers = self._filter_headers(headers)
        
        logger.info("=" * 80)
        logger.info(f"[{request_id}] 📥 收到请求")
        logger.info(f"[{request_id}] 方法: {method}")
        logger.info(f"[{request_id}] URL: {url}")
        logger.info(f"[{request_id}] 客户端IP: {client_ip}")
        
        if filtered_headers:
            logger.info(f"[{request_id}] 请求头:")
            for key, value in filtered_headers.items():
                logger.info(f"[{request_id}]   {key}: {value}")
        
        if body is not None:
            logger.info(f"[{request_id}] 请求体:")
            if isinstance(body, dict):
                logger.info(f"[{request_id}]   {json.dumps(body, ensure_ascii=False, indent=2)}")
            else:
                logger.info(f"[{request_id}]   {body}")
    
    def _log_response(self, request_id: str, status_code: int, headers: dict, body, process_time: float):
        """记录响应日志"""
        # 根据状态码选择日志级别
        if status_code >= 500:
            log_func = logger.error
            emoji = "❌"
        elif status_code >= 400:
            log_func = logger.warning
            emoji = "⚠️"
        else:
            log_func = logger.info
            emoji = "✅"
        
        log_func(f"[{request_id}] {emoji} 响应完成")
        log_func(f"[{request_id}] 状态码: {status_code}")
        log_func(f"[{request_id}] 处理时间: {process_time:.3f}s")
        
        # 记录重要的响应头
        important_headers = ['content-type', 'content-length', 'location']
        for header in important_headers:
            if header in headers:
                log_func(f"[{request_id}] {header}: {headers[header]}")
        
        if body is not None:
            log_func(f"[{request_id}] 响应体:")
            if isinstance(body, dict):
                log_func(f"[{request_id}]   {json.dumps(body, ensure_ascii=False, indent=2)}")
            else:
                log_func(f"[{request_id}]   {body}")
        
        logger.info("=" * 80)
    
    def _filter_headers(self, headers: dict) -> dict:
        """过滤敏感的请求头信息"""
        sensitive_headers = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token',
            'password', 'secret', 'token'
        }
        
        filtered = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_headers):
                filtered[key] = "***MASKED***"
            else:
                filtered[key] = value
        
        return filtered
    
    def _mask_sensitive_data(self, data: dict) -> dict:
        """隐藏敏感数据"""
        sensitive_fields = {
            'password', 'passwd', 'secret', 'token', 'key',
            'authorization', 'auth', 'credential', 'private'
        }
        
        masked_data = data.copy()
        for key, value in masked_data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_fields):
                masked_data[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked_data[key] = self._mask_sensitive_data(value)
        
        return masked_data


def setup_logging(log_level: str = "INFO"):
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )