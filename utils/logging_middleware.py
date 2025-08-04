"""
请求和响应日志中间件
用于记录API请求和响应的详细信息，方便调试
"""

import time
import json
import logging
import os
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
import uuid
from logging.handlers import RotatingFileHandler

# 配置日志格式
logger = logging.getLogger("API_Logger")

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """请求响应日志中间件"""
    
    def __init__(self, app, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.debug_mode = os.getenv("DEBUG", "false").lower() == "true"

        # 清除所有已存在的处理器，避免重复日志
        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)
        
        logger.setLevel(self.log_level)

        if self.debug_mode:
            # 调试模式：只输出到控制台，精简格式
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        else:
            # 非调试模式：输出到文件，并控制台输出服务状态
            # 文件处理器
            log_file_path = os.path.join(os.getcwd(), "logs", "api.log")
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5              # 最多保留5个备份文件
            )
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # 控制台处理器（用于服务状态等少量信息）
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

    
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
                        # 根据调试模式决定是否隐藏敏感信息
                        if isinstance(request_body, dict) and not self.debug_mode:
                            request_body = self._mask_sensitive_data(request_body)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_body = f"<binary data: {len(body)} bytes>"
                
                # 重新构建请求体供后续处理
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.warning(f"读取请求体失败: {e}")
        
        if self.debug_mode:
            # 调试模式下精简日志
            self._log_debug_request(request_id, method, url, request_body)
        else:
            # 非调试模式下详细日志写入文件
            self._log_request_to_file(request_id, method, url, headers, client_ip, request_body)
        
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
            
            if self.debug_mode:
                # 调试模式下精简日志
                self._log_debug_response(request_id, status_code, response_body, process_time)
            else:
                # 非调试模式下详细日志写入文件
                self._log_response_to_file(request_id, status_code, response_headers, response_body, process_time)
            
            return response
            
        except Exception as e:
            # 记录异常
            process_time = time.time() - start_time
            logger.error(f"[{request_id}] 请求处理异常: {str(e)}, 耗时: {process_time:.3f}s")
            raise
    
    def _log_debug_request(self, request_id: str, method: str, url: str, body):
        """调试模式下记录精简请求日志"""
        logger.info(f"[{request_id}] 接口: {method} {url}")
        if body is not None:
            logger.info(f"[{request_id}] 请求体: {json.dumps(body, ensure_ascii=False)}")

    def _log_debug_response(self, request_id: str, status_code: int, body, process_time: float):
        """调试模式下记录精简响应日志"""
        logger.info(f"[{request_id}] 状态码: {status_code}")
        logger.info(f"[{request_id}] 处理时间: {process_time:.3f}s")
        if body is not None:
            logger.info(f"[{request_id}] 响应体: {json.dumps(body, ensure_ascii=False)}")
        logger.info("-" * 40) # 分隔符

    def _log_request_to_file(self, request_id: str, method: str, url: str, headers: dict, client_ip: str, body):
        """非调试模式下记录详细请求日志到文件"""
        filtered_headers = self._filter_headers(headers)
        logger.info(f"[{request_id}] 📥 收到请求")
        logger.info(f"[{request_id}] 方法: {method}")
        logger.info(f"[{request_id}] URL: {url}")
        logger.info(f"[{request_id}] 客户端IP: {client_ip}")
        if filtered_headers:
            logger.info(f"[{request_id}] 请求头: {json.dumps(filtered_headers, ensure_ascii=False)}")
        if body is not None:
            logger.info(f"[{request_id}] 请求体: {json.dumps(body, ensure_ascii=False)}")

    def _log_response_to_file(self, request_id: str, status_code: int, headers: dict, body, process_time: float):
        """非调试模式下记录详细响应日志到文件"""
        logger.info(f"[{request_id}] 📤 响应完成")
        logger.info(f"[{request_id}] 状态码: {status_code}")
        logger.info(f"[{request_id}] 处理时间: {process_time:.3f}s")
        important_headers = ['content-type', 'content-length', 'location']
        logged_headers = {h: headers[h] for h in important_headers if h in headers}
        if logged_headers:
            logger.info(f"[{request_id}] 响应头: {json.dumps(logged_headers, ensure_ascii=False)}")
        if body is not None:
            logger.info(f"[{request_id}] 响应体: {json.dumps(body, ensure_ascii=False)}")
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
        
        return filtered
    
    def _mask_sensitive_data(self, data: dict) -> dict:
        """隐藏敏感数据"""
        if self.debug_mode:
            return data  # 调试模式下不隐藏敏感数据
            
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