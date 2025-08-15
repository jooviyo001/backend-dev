"""异常处理器配置模块

配置全局异常处理器
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.exceptions import BusinessException
from utils.status_codes import (
    BAD_REQUEST, UNAUTHORIZED, FORBIDDEN, NOT_FOUND, METHOD_NOT_ALLOWED,
    CONFLICT, TOO_MANY_REQUESTS, INTERNAL_ERROR, NOT_IMPLEMENTED,
    BAD_GATEWAY, SERVICE_UNAVAILABLE
)


def configure_exception_handlers(app: FastAPI) -> None:
    """配置全局异常处理器"""
    
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request, exc: BusinessException):
        """业务异常处理器"""
        from utils.response_utils import format_timestamp
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
                "timestamp": format_timestamp()
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException):
        """HTTP异常处理器"""
        from utils.response_utils import format_timestamp
        
        # 根据HTTP状态码映射到自定义状态码
        if exc.status_code == 400:
            code = BAD_REQUEST
        elif exc.status_code == 401:
            code = UNAUTHORIZED
        elif exc.status_code == 403:
            code = FORBIDDEN
        elif exc.status_code == 404:
            code = NOT_FOUND
        elif exc.status_code == 405:
            code = METHOD_NOT_ALLOWED
        elif exc.status_code == 409:
            code = CONFLICT
        elif exc.status_code == 429:
            code = TOO_MANY_REQUESTS
        elif exc.status_code == 500:
            code = INTERNAL_ERROR
        elif exc.status_code == 501:
            code = NOT_IMPLEMENTED
        elif exc.status_code == 502:
            code = BAD_GATEWAY
        elif exc.status_code == 503:
            code = SERVICE_UNAVAILABLE
        else:
            code = str(exc.status_code)
        
        # 处理详细信息
        detail = exc.detail
        if isinstance(detail, dict):
            # 如果detail是字典，可能包含自定义的错误信息
            message = detail.get("message", str(detail))
            data = detail.get("data")
        else:
            message = str(detail)
            data = None
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": message,
                "data": data,
                "timestamp": format_timestamp()
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request, exc: StarletteHTTPException):
        """Starlette HTTP异常处理器"""
        from utils.response_utils import format_timestamp
        
        # 根据HTTP状态码映射到自定义状态码
        if exc.status_code == 400:
            code = BAD_REQUEST
        elif exc.status_code == 401:
            code = UNAUTHORIZED
        elif exc.status_code == 403:
            code = FORBIDDEN
        elif exc.status_code == 404:
            code = NOT_FOUND
        elif exc.status_code == 405:
            code = METHOD_NOT_ALLOWED
        elif exc.status_code == 409:
            code = CONFLICT
        elif exc.status_code == 429:
            code = TOO_MANY_REQUESTS
        elif exc.status_code == 500:
            code = INTERNAL_ERROR
        elif exc.status_code == 501:
            code = NOT_IMPLEMENTED
        elif exc.status_code == 502:
            code = BAD_GATEWAY
        elif exc.status_code == 503:
            code = SERVICE_UNAVAILABLE
        else:
            code = str(exc.status_code)
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": exc.detail,
                "data": None,
                "timestamp": format_timestamp()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc: Exception):
        """通用异常处理器"""
        from utils.response_utils import format_timestamp
        import traceback
        
        # 记录异常信息
        print(f"Unhandled exception: {exc}")
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "code": INTERNAL_ERROR,
                "message": "服务器内部错误",
                "data": None,
                "timestamp": format_timestamp()
            }
        )