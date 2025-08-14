"""应用配置模块

负责创建FastAPI应用实例和配置路由
"""
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# 导入路由
from routers import (
    auth, users, projects, tasks, defects, 
    organizations, positons, comments, dashboard, uploads, documents
)


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="项目管理系统API",
        description="一个功能完整的项目管理系统后端API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    return app


def configure_routes(app: FastAPI) -> None:
    """配置应用路由"""
    # API路由
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["用户管理"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目管理"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["任务管理"])
    app.include_router(defects.router, prefix="/api/v1/defects", tags=["缺陷管理"])
    app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["组织管理"])
    app.include_router(positons.router, prefix="/api/v1/positions", tags=["岗位管理"])
    app.include_router(comments.router, prefix="/api/v1/comments", tags=["评论管理"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["仪表板"])
    app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["文件上传"])
    app.include_router(documents.router, prefix="/api/v1", tags=["文档管理"])
    
    # 根路径
    @app.get("/")
    async def root():
        from utils.response_utils import format_timestamp
        return {
            "code": "20000",
            "message": "项目管理系统API",
            "data": {
                "version": "1.0.0",
                "timestamp": format_timestamp()
            }
        }
    
    # 健康检查
    @app.get("/health")
    async def health_check():
        from utils.response_utils import format_timestamp
        return {
            "code": "20000",
            "message": "服务运行正常",
            "data": {
                "status": "healthy",
                "timestamp": format_timestamp()
            }
        }
    
    # Vite客户端资源
    @app.get("/@vite/client")
    async def vite_client():
        from fastapi.responses import Response
        content = "// Vite client placeholder\n// This is an empty implementation to prevent 404 errors\n"
        return Response(content=content, media_type="application/javascript")
    
    # 自定义Swagger UI路由
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>API Documentation</title>
            <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
            <style>
                html {
                    box-sizing: border-box;
                    overflow: -moz-scrollbars-vertical;
                    overflow-y: scroll;
                }
                *, *:before, *:after {
                    box-sizing: inherit;
                }
                body {
                    margin:0;
                    background: #fafafa;
                }
            </style>
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
            <script>
                const ui = SwaggerUIBundle({
                    url: '/openapi.json',
                    dom_id: '#swagger-ui',
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.presets.standalone
                    ],
                    layout: "StandaloneLayout"
                });
            </script>
        </body>
        </html>
        """)