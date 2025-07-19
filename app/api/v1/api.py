from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, projects, tasks, organizations, dashboard, files, search, export

api_router = APIRouter()

# 认证相关路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])

# 用户管理路由
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])

# 项目管理路由
api_router.include_router(projects.router, prefix="/projects", tags=["项目管理"])

# 任务管理路由
api_router.include_router(tasks.router, prefix="/tasks", tags=["任务管理"])

# 组织管理路由
api_router.include_router(organizations.router, prefix="/organizations", tags=["组织管理"])

# 仪表盘路由
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["仪表盘"])

# 文件上传路由
api_router.include_router(files.router, prefix="/files", tags=["文件管理"])

# 搜索路由
api_router.include_router(search.router, prefix="/search", tags=["搜索"])

# 导出路由
api_router.include_router(export.router, prefix="/export", tags=["导出"])