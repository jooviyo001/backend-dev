from pydantic_settings import BaseSettings
from typing import Optional
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "项目管理系统"
    APP_DESCRIPTION: str = "一个基于FastAPI的项目管理系统"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_V1_STR: str = "/api/v1"
    INIT_DB_ON_STARTUP: bool = True
    
    # 服务器配置
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8000
    SERVER_WORKERS: int = 1
    
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./project_management.db"  # 开发环境使用SQLite
    DATABASE_ECHO: bool = False # 是否显示SQLAlchemy的SQL日志
    MYSQL_URL: Optional[str] = None  # 生产环境MySQL连接
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: str = "jpg,jpeg,png,gif,pdf,doc,docx,xls,xlsx,ppt,pptx,txt,zip,rar"
    EXPORT_DIR: str = "./exports"
    SERVE_STATIC_FILES: bool = False
    STATIC_DIR: str = "./static"
    SERVE_UPLOAD_FILES: bool = True
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # 缓存配置
    CACHE_EXPIRE_SECONDS: int = 3600  # 1小时

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(levelname)s:     %(message)s"
    LOG_ENABLE_COLORS: bool = True
    LOG_FILE: Optional[str] = None
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5
    
    # CORS配置
    cors_origins: list[str] = ["*"] # 允许所有来源，生产环境请修改
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # 受信任主机配置
    trusted_hosts: list[str] = ["*"] # 允许所有主机，生产环境请修改

    # 会话配置
    session_secret_key: str = "your-session-secret-key-change-in-production"
    session_max_age: int = 14 * 24 * 60 * 60  # 14天

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    enable_rate_limiting: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 100
    require_api_key: bool = False
    enable_response_caching: bool = False
    is_development: bool = False
    app_name: str = "My App"
    environment: str = "development"
    app_version: str = "0.1.0"
    app_description: str = "My App Description"
    app_contact: str = "My App Contact"
    app_license: str = "My App License"
    app_terms_of_service: str = "My App Terms of Service"
    app_security_scheme: str = "bearer"
    debug: bool = False
    api_v1_str: str = "/api/v1"
    log_level: str = "INFO"
    auto_create_admin: bool = False
    log_format: str = "%(levelname)s:     %(message)s"
    log_enable_colors: bool = True
    log_file: Optional[str] = None
    log_max_size: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5
    auto_create_admin_user: bool = True
    admin_user_username: str = "admin"
    admin_user_password: str = "admin123"
    admin_user_email: str = "admin@example.com"
    admin_user_role: str = "admin"

    

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

# 创建全局设置实例
settings = Settings()

# 根据环境切换数据库
if os.getenv("ENVIRONMENT") == "production" and settings.MYSQL_URL:
    settings.DATABASE_URL = settings.MYSQL_URL