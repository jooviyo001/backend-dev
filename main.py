from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
from typing import Optional, List
import jwt
from pydantic import BaseModel

# 导入状态码常量
from utils.status_codes import *

# 导入路由模块
from routers import auth, users, projects, organizations, dashboard, tasks
from models.database import engine, Base
from models import models
from utils.snowflake import init_snowflake
from utils.database_initializer import init_database
from utils.logging_middleware import RequestResponseLoggingMiddleware

# 初始化雪花算法（机器ID可以通过环境变量配置）
import os
machine_id = int(os.getenv("MACHINE_ID", "1"))  # 默认机器ID为1
init_snowflake(machine_id)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 初始化数据库数据（仅在开发环境）
try:
    init_database(force=False)
except Exception as e:
    print(f"⚠️  数据库初始化跳过: {e}")

app = FastAPI(
    title="项目管理系统API",
    description="基于FastAPI的项目管理系统后端接口",
    version="1.0.0"
)

# CORS中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求响应日志中间件
log_level = os.getenv("LOG_LEVEL", "INFO")
app.add_middleware(RequestResponseLoggingMiddleware, log_level=log_level)

# 响应格式统一中间件
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import Response, JSONResponse
import json

class ResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
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
            # 确保响应体可以被多次读取
            response_body = [chunk async for chunk in response.body_iterator]
            body = b"".join(response_body)

            if not body:
                return response

            content = json.loads(body.decode('utf-8'))
            
            # 导入 standard_response 函数
            from utils.response_utils import standard_response
            from utils.status_codes import SUCCESS, get_message

            # 提取原始响应的数据、状态码和消息
            original_data = content.get("data", content) # 如果是标准格式，取data字段，否则取整个content
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

app.add_middleware(ResponseMiddleware)

# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证管理"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户管理"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目管理"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["组织管理"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["仪表盘"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["任务管理"])

# 安全配置
security = HTTPBearer()

# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
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
            "timestamp": datetime.now().isoformat()
        }
    )

# 根路径
@app.get("/")
async def root():
    return {
        "code": "200",
        "message": "项目管理系统API",
        "data": {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }
    }

# 健康检查
@app.get("/health")
async def health_check():
    return {
        "code": "200",
        "message": "服务运行正常",
        "data": {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }
    }

# Vite客户端资源
@app.get("/@vite/client")
async def vite_client():
    # 返回一个空的JavaScript文件，避免404错误
    from fastapi.responses import Response
    content = "// Vite client placeholder\n// This is an empty implementation to prevent 404 errors\n"
    return Response(content=content, media_type="application/javascript")

# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户管理"])
app.include_router(users.router, prefix="/api/v1/user", tags=["用户管理"])  # 支持单数形式
app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目管理"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["组织管理"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["仪表盘"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)