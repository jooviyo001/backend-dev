from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import asyncio
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis_client import redis_client
from app.core.logging import init_logging, get_logger
from app.core.middleware import setup_middleware
from app.core.exceptions import setup_exception_handlers
from app.core.init_db import init_database

# 导入API路由
from app.api.v1.api import api_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    # 启动时执行
    logger.info("Starting application...")
    init_logging()
    
    try:
        # 初始化Redis连接
        await redis_client.connect()
        logger.info("Redis connection initialized")
        

        
        # 初始化数据库数据
        if settings.INIT_DB_ON_STARTUP:
            logger.info("Initializing database data...")
            await init_database()
        
        # 创建上传目录
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory created: {upload_dir}")
        
        # 创建导出目录
        export_dir = Path(settings.EXPORT_DIR)
        export_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Export directory created: {export_dir}")
        
        logger.info("Application startup completed")
        
        yield
        
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}", exc_info=True)
        raise
    
    finally:
        # 关闭时执行
        logger.info("Shutting down application...")
        
        try:
            # 关闭Redis连接
            await redis_client.disconnect()
            logger.info("Redis connection closed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        
        logger.info("Application shutdown completed")

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENVIRONMENT != "production" else None,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# 设置中间件
setup_middleware(app)

# 设置异常处理器
setup_exception_handlers(app)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

# 系统信息端点
@app.get("/info")
async def system_info():
    """系统信息端点"""
    import psutil
    import platform
    from datetime import datetime
    
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": datetime.now().isoformat()
    }

# 指标端点（用于监控）
@app.get("/metrics")
async def metrics():
    """指标端点"""
    import psutil
    from app.core.redis_client import redis_client
    
    metrics_data = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "active_connections": 0,  # 这里可以添加实际的连接数统计
    }
    
    # 检查Redis连接状态
    try:
        if redis_client:
            await redis_client.ping()
            metrics_data["redis_status"] = "connected"
        else:
            metrics_data["redis_status"] = "disconnected"
    except Exception:
        metrics_data["redis_status"] = "error"
    
    return metrics_data

# 根路径重定向
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.VERSION,
        "docs_url": "/docs" if settings.ENVIRONMENT != "production" else None,
        "api_url": settings.API_V1_STR
    }

# 包含API路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 静态文件服务（如果需要）
if settings.SERVE_STATIC_FILES:
    static_dir = Path(settings.STATIC_DIR)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info(f"Static files served from: {static_dir}")

# 上传文件服务
if settings.SERVE_UPLOAD_FILES:
    upload_dir = Path(settings.UPLOAD_DIR)
    if upload_dir.exists():
        app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
        logger.info(f"Upload files served from: {upload_dir}")

# 自定义中间件示例
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """添加处理时间头"""
    import time
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 错误处理示例
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404错误处理"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested resource was not found",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """500错误处理"""
    logger.error(f"Internal server error: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

# 启动事件（已弃用，使用lifespan代替）
# @app.on_event("startup")
# async def startup_event():
#     pass

# 关闭事件（已弃用，使用lifespan代替）
# @app.on_event("shutdown")
# async def shutdown_event():
#     pass

# 开发模式下的额外配置
if settings.is_development:
    # 添加开发工具
    @app.get("/dev/reset-db")
    async def reset_database():
        """重置数据库（仅开发环境）"""
        if not settings.is_development:
            return JSONResponse(
                status_code=403,
                content={"error": "This endpoint is only available in development mode"}
            )
        
        try:
            # 删除所有表
            Base.metadata.drop_all(bind=engine)
            # 重新创建表
            Base.metadata.create_all(bind=engine)
            # 初始化数据
            await init_database()
            
            return {"message": "Database reset successfully"}
        
        except Exception as e:
            logger.error(f"Database reset failed: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "Database reset failed", "detail": str(e)}
            )
    
    @app.get("/dev/clear-cache")
    async def clear_cache():
        """清除缓存（仅开发环境）"""
        if not settings.is_development:
            return JSONResponse(
                status_code=403,
                content={"error": "This endpoint is only available in development mode"}
            )
        
        try:
            from app.core.redis_client import redis_client
            if redis_client:
                await redis_client.flushdb()
                return {"message": "Cache cleared successfully"}
            else:
                return {"message": "Redis not available"}
        
        except Exception as e:
            logger.error(f"Cache clear failed: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "Cache clear failed", "detail": str(e)}
            )

# 应用程序元数据
app.state.app_name = settings.app_name
app.state.app_version = settings.app_version
app.state.environment = settings.environment

# 日志应用程序启动信息
logger.info(f"Application initialized: {settings.app_name} v{settings.app_version}")
logger.info(f"Environment: {settings.environment}")
logger.info(f"Debug mode: {settings.debug}")
logger.info(f"API prefix: {settings.api_v1_str}")

if __name__ == "__main__":
    import uvicorn
    
    # 运行配置
    run_config = {
        "app": "app.main:app",
        "host": settings.server_host,
        "port": settings.server_port,
        "reload": settings.is_development,
        "log_level": settings.log_level.lower(),
        "access_log": True,
        "use_colors": settings.is_development,
    }
    
    # 在生产环境中使用更多的worker
    if settings.is_production:
        run_config["workers"] = settings.server_workers
    
    logger.info(f"Starting server on {settings.server_host}:{settings.server_port}")
    
    try:
        uvicorn.run(**run_config)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}", exc_info=True)