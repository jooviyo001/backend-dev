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
from routers import auth, users, projects, organizations, dashboard
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
            # 获取响应体
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
                
            if body:
                content = json.loads(body.decode())
                
                # 如果响应已经是标准格式，则不做修改
                if "code" in content and "message" in content and "data" in content:
                    return Response(
                        content=body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
                
                # 根据HTTP状态码映射到自定义状态码
                if response.status_code < 400:
                    code = SUCCESS
                    message = get_message(SUCCESS)
                elif response.status_code == 400:
                    code = BAD_REQUEST
                    message = get_message(BAD_REQUEST)
                elif response.status_code == 401:
                    code = UNAUTHORIZED
                    message = get_message(UNAUTHORIZED)
                elif response.status_code == 403:
                    code = FORBIDDEN
                    message = get_message(FORBIDDEN)
                elif response.status_code == 404:
                    code = NOT_FOUND
                    message = get_message(NOT_FOUND)
                elif response.status_code >= 500:
                    code = INTERNAL_ERROR
                    message = get_message(INTERNAL_ERROR)
                else:
                    code = str(response.status_code)
                    message = "操作失败"
                
                # 将响应转换为标准格式
                new_content = {
                    "code": code,
                    "message": message,
                    "data": content,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 创建新的响应
                return JSONResponse(
                    content=new_content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            
            # 如果没有响应体，返回原始响应
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
        except Exception as e:
            # 发生异常时，返回原始响应
            return response

app.add_middleware(ResponseMiddleware)

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
app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目管理"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["组织管理"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["仪表盘"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)