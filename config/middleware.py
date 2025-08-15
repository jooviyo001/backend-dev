"""中间件配置模块

包含所有中间件的配置和定义
"""
import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.logging_middleware import RequestResponseLoggingMiddleware


class ResponseMiddleware(BaseHTTPMiddleware):
    """响应格式统一中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 跳过特定路径的处理
        if (request.url.path == "/@vite/client" or
            request.url.path == "/openapi.json" or
            request.url.path.startswith("/docs") or
            request.url.path == "/redoc"):
            return await call_next(request)
        
        response = await call_next(request)
        
        # 跳过非JSON响应
        if response.headers.get("content-type") != "application/json":
            return response
            
        try:
            # 获取响应体内容
            body = b""
            if hasattr(response, 'body'):
                # 如果响应已经有body属性，直接使用
                body = response.body
                # 如果body是memoryview类型，需要先转换为bytes
                if not isinstance(body, bytes):
                    body = bytes(body)
            else:
                # 尝试安全访问body_iterator属性
                body_iterator = getattr(response, 'body_iterator', None)
                if body_iterator is not None:
                    # 对于流式响应，需要迭代获取内容
                    try:
                        async for chunk in body_iterator:
                            body += chunk
                    except Exception:
                        # 如果无法访问body_iterator，直接返回原响应
                        return response
                else:
                    # 无法获取响应体，直接返回原响应
                    return response

            if not body:
                return response

            content = json.loads(body.decode('utf-8'))
            
            # 导入 standard_response 函数
            from utils.response_utils import standard_response
            from utils.status_codes import SUCCESS, get_message

            # 提取原始响应的数据、状态码和消息
            original_data = content.get("data", content)  # 如果是标准格式，取data字段，否则取整个content
            original_code = content.get("code", SUCCESS)
            original_message = content.get("message", get_message(SUCCESS))

            # 统一使用 standard_response 处理，确保ID前缀和编码
            standard_res = standard_response(
                data=original_data,
                code=original_code,
                message=original_message,
                status_code=response.status_code
            )
            
            # 重新构建响应，确保原始响应头不变
            new_response = JSONResponse(
                content=standard_res,
                status_code=response.status_code
            )
            # 复制原始响应的头部，除了Content-Length，让FastAPI重新计算
            for header_name, header_value in response.headers.items():
                if header_name.lower() != "content-length":
                    new_response.headers[header_name] = header_value
            return new_response
        except Exception as e:
            import traceback
            print(f"Error in ResponseMiddleware: {e}")
            traceback.print_exc()
            # 返回一个通用的错误响应，防止服务器崩溃
            from utils.response_utils import standard_response
            error_res = standard_response(
                data={"detail": f"Internal Server Error: {e}"},
                code="500",
                message="服务器内部错误",
                status_code=500
            )
            error_response = JSONResponse(content=error_res, status_code=500)
            return error_response


def configure_middleware(app: FastAPI) -> None:
    """配置应用中间件"""
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 在生产环境中应该设置具体的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Mx-ReqToken",
            "Keep-Alive",
            "X-Requested-With",
            "X-CSRF-Token",
            "Cache-Control",
            "Pragma"
        ],
        expose_headers=["*"],  # 允许前端访问所有响应头
    )
    
    # 请求响应日志中间件
    log_level = os.getenv("LOG_LEVEL", "INFO")
    app.add_middleware(RequestResponseLoggingMiddleware, log_level=log_level)
    
    # 响应格式统一中间件
    app.add_middleware(ResponseMiddleware)