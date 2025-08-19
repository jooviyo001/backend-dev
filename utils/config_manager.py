"""配置管理工具模块

提供环境配置、系统设置、功能开关、配置验证等功能
"""
import os
import json
import yaml
from typing import Any, Dict, List, Optional, Union, Type
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
from functools import wraps

from pydantic import BaseModel, Field, field_validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

logger = logging.getLogger(__name__)


class ConfigType(str, Enum):
    """配置类型枚举"""
    SYSTEM = "system"          # 系统配置
    DATABASE = "database"      # 数据库配置
    SECURITY = "security"      # 安全配置
    FEATURE = "feature"        # 功能开关
    BUSINESS = "business"      # 业务配置
    INTEGRATION = "integration" # 集成配置
    PERFORMANCE = "performance" # 性能配置
    LOGGING = "logging"        # 日志配置


class Environment(str, Enum):
    """环境类型枚举"""
    DEVELOPMENT = "development"  # 开发环境
    TESTING = "testing"          # 测试环境
    STAGING = "staging"          # 预发布环境
    PRODUCTION = "production"    # 生产环境


@dataclass
class ConfigItem:
    """配置项"""
    key: str
    value: Any
    config_type: ConfigType
    description: str = ""
    required: bool = True
    default_value: Any = None
    validator_func: Optional[callable] = None
    environment: Optional[Environment] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def validate(self) -> bool:
        """验证配置项"""
        if self.required and self.value is None:
            return False
        
        if self.environment and self.environment != Environment(os.getenv("ENVIRONMENT", "development")):
            try:
                return self.validator_func(self.value)
            except Exception as e:
                logger.error(f"配置项 {self.key} 验证失败: {str(e)}")
                return False
        
        return True
    
    def get_effective_value(self) -> Any:
        """获取有效值"""
        return self.value if self.value is not None else self.default_value


class DatabaseConfig(BaseSettings):
    """数据库配置"""
    model_config = {"extra": "allow", "env_file": ".env", "env_file_encoding": "utf-8"} # 允许额外字段
    
    host: str = Field(default="localhost", env="DB_HOST", description="数据库主机")
    port: int = Field(default=5432, env="DB_PORT", description="数据库端口")
    username: str = Field(default="postgres", env="DB_USERNAME", description="数据库用户名")
    password: str = Field(default="", env="DB_PASSWORD", description="数据库密码")
    database: str = Field(default="project_db", env="DB_DATABASE", description="数据库名称")
    pool_size: int = Field(default=10, env="DB_POOL_SIZE", description="连接池大小")
    max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW", description="最大溢出连接数")
    pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT", description="连接池超时时间")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE", description="连接池回收时间")
    echo: bool = Field(default=False, env="DB_ECHO", description="是否打印SQL语句")
    
    @field_validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('端口号必须在1-65535之间')
        return v
    
    @field_validator('pool_size')
    def validate_pool_size(cls, v):
        if v < 1:
            raise ValueError('连接池大小必须大于0')
        return v
    
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class SecurityConfig(BaseSettings):
    """安全配置"""
    model_config = {"extra": "allow", "env_file": ".env", "env_file_encoding": "utf-8"}
    
    secret_key: str = Field(env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    password_min_length: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    password_require_uppercase: bool = Field(default=True, env="PASSWORD_REQUIRE_UPPERCASE")
    password_require_lowercase: bool = Field(default=True, env="PASSWORD_REQUIRE_LOWERCASE")
    password_require_numbers: bool = Field(default=True, env="PASSWORD_REQUIRE_NUMBERS")
    password_require_symbols: bool = Field(default=False, env="PASSWORD_REQUIRE_SYMBOLS")
    max_login_attempts: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    lockout_duration_minutes: int = Field(default=15, env="LOCKOUT_DURATION_MINUTES")
    enable_2fa: bool = Field(default=False, env="ENABLE_2FA")
    session_timeout_minutes: int = Field(default=60, env="SESSION_TIMEOUT_MINUTES")
    
    @field_validator('secret_key')
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError('密钥长度至少32个字符')
        return v
    
    @field_validator('access_token_expire_minutes')
    def validate_token_expire(cls, v):
        if v < 1:
            raise ValueError('令牌过期时间必须大于0')
        return v


class FeatureFlags(BaseSettings):
    """功能开关配置"""
    model_config = {"extra": "allow", "env_file": ".env", "env_file_encoding": "utf-8"}
    
    enable_user_registration: bool = Field(default=True, env="ENABLE_USER_REGISTRATION")
    enable_email_verification: bool = Field(default=True, env="ENABLE_EMAIL_VERIFICATION")
    enable_sms_notification: bool = Field(default=False, env="ENABLE_SMS_NOTIFICATION")
    enable_file_upload: bool = Field(default=True, env="ENABLE_FILE_UPLOAD")
    enable_export_data: bool = Field(default=True, env="ENABLE_EXPORT_DATA")
    enable_api_rate_limiting: bool = Field(default=True, env="ENABLE_API_RATE_LIMITING")
    enable_audit_logging: bool = Field(default=True, env="ENABLE_AUDIT_LOGGING")
    enable_performance_monitoring: bool = Field(default=False, env="ENABLE_PERFORMANCE_MONITORING")
    enable_cache: bool = Field(default=True, env="ENABLE_CACHE")
    enable_background_tasks: bool = Field(default=True, env="ENABLE_BACKGROUND_TASKS")
    enable_websocket: bool = Field(default=False, env="ENABLE_WEBSOCKET")
    enable_swagger_ui: bool = Field(default=True, env="ENABLE_SWAGGER_UI")
    enable_debug_mode: bool = Field(default=False, env="ENABLE_DEBUG_MODE")
    enable_maintenance_mode: bool = Field(default=False, env="ENABLE_MAINTENANCE_MODE")


class BusinessConfig(BaseSettings):
    """业务配置"""
    model_config = {"extra": "allow", "env_file": ".env", "env_file_encoding": "utf-8"}
    
    default_page_size: int = Field(default=10, env="DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=100, env="MAX_PAGE_SIZE")
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    allowed_file_extensions: str = Field(default=".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.xls,.xlsx", env="ALLOWED_FILE_EXTENSIONS")
    default_language: str = Field(default="zh-CN", env="DEFAULT_LANGUAGE")
    default_timezone: str = Field(default="Asia/Shanghai", env="DEFAULT_TIMEZONE")
    company_name: str = Field(default="项目管理系统", env="COMPANY_NAME")
    support_email: str = Field(default="support@example.com", env="SUPPORT_EMAIL")
    max_projects_per_user: int = Field(default=50, env="MAX_PROJECTS_PER_USER")
    max_tasks_per_project: int = Field(default=1000, env="MAX_TASKS_PER_PROJECT")
    defect_auto_assign: bool = Field(default=True, env="DEFECT_AUTO_ASSIGN")
    task_reminder_hours: int = Field(default=24, env="TASK_REMINDER_HOURS")
    
    @field_validator('max_file_size_mb')
    def validate_file_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError('文件大小限制必须在1-100MB之间')
        return v
    
    def get_allowed_extensions(self) -> List[str]:
        """获取允许的文件扩展名列表"""
        return [ext.strip() for ext in self.allowed_file_extensions.split(',')]


class PerformanceConfig(BaseSettings):
    """性能配置"""
    model_config = {"extra": "allow", "env_file": ".env", "env_file_encoding": "utf-8"}
    
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL_SECONDS")
    query_timeout_seconds: int = Field(default=30, env="QUERY_TIMEOUT_SECONDS")
    api_rate_limit_per_minute: int = Field(default=60, env="API_RATE_LIMIT_PER_MINUTE")
    api_rate_limit_per_hour: int = Field(default=1000, env="API_RATE_LIMIT_PER_HOUR")
    background_task_workers: int = Field(default=4, env="BACKGROUND_TASK_WORKERS")
    max_concurrent_requests: int = Field(default=100, env="MAX_CONCURRENT_REQUESTS")
    connection_pool_size: int = Field(default=20, env="CONNECTION_POOL_SIZE")
    slow_query_threshold_ms: int = Field(default=1000, env="SLOW_QUERY_THRESHOLD_MS")


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config", environment: Environment = None):
        self.config_dir = Path(config_dir)
        self.environment = environment or self._detect_environment()
        self.configs: Dict[str, ConfigItem] = {}
        self.config_files: Dict[str, Path] = {}
        self._watchers: List[callable] = []
        
        # 初始化配置
        self._load_default_configs()
        self._load_config_files()
    
    def _detect_environment(self) -> Environment:
        """检测当前环境"""
        env = os.getenv('ENVIRONMENT', 'development').lower()
        try:
            return Environment(env)
        except ValueError:
            logger.warning(f"未知环境类型: {env}，使用默认环境: development")
            return Environment.DEVELOPMENT
    
    def _load_default_configs(self):
        """加载默认配置"""
        # 系统配置
        self.set_config("app_name", "项目管理系统", ConfigType.SYSTEM, "应用名称")
        self.set_config("app_version", "1.0.0", ConfigType.SYSTEM, "应用版本")
        self.set_config("debug", self.environment == Environment.DEVELOPMENT, ConfigType.SYSTEM, "调试模式")
        self.set_config("host", "0.0.0.0", ConfigType.SYSTEM, "服务器主机")
        self.set_config("port", 8000, ConfigType.SYSTEM, "服务器端口")
        
        # 日志配置
        self.set_config("log_level", "INFO", ConfigType.LOGGING, "日志级别")
        self.set_config("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s", ConfigType.LOGGING, "日志格式")
        self.set_config("log_file", "app.log", ConfigType.LOGGING, "日志文件")
        self.set_config("log_max_size", 10 * 1024 * 1024, ConfigType.LOGGING, "日志文件最大大小")
        self.set_config("log_backup_count", 5, ConfigType.LOGGING, "日志备份数量")
    
    def _load_config_files(self):
        """加载配置文件"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return
        
        # 加载通用配置文件
        common_config = self.config_dir / "config.yaml"
        if common_config.exists():
            self._load_yaml_config(common_config)
        
        # 加载环境特定配置文件
        env_config = self.config_dir / f"config.{self.environment.value}.yaml"
        if env_config.exists():
            self._load_yaml_config(env_config)
        
        # 加载JSON配置文件
        json_config = self.config_dir / "config.json"
        if json_config.exists():
            self._load_json_config(json_config)
    
    def _load_yaml_config(self, config_file: Path):
        """加载YAML配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            self._process_config_data(config_data, str(config_file))
            self.config_files[str(config_file)] = config_file
            
        except Exception as e:
            logger.error(f"加载配置文件失败 {config_file}: {str(e)}")
    
    def _load_json_config(self, config_file: Path):
        """加载JSON配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self._process_config_data(config_data, str(config_file))
            self.config_files[str(config_file)] = config_file
            
        except Exception as e:
            logger.error(f"加载配置文件失败 {config_file}: {str(e)}")
    
    def _process_config_data(self, config_data: Dict[str, Any], source: str):
        """处理配置数据"""
        for key, value in config_data.items():
            if isinstance(value, dict):
                # 嵌套配置
                for sub_key, sub_value in value.items():
                    full_key = f"{key}.{sub_key}"
                    config_type = self._infer_config_type(key)
                    self.set_config(full_key, sub_value, config_type, f"来自 {source}")
            else:
                config_type = self._infer_config_type(key)
                self.set_config(key, value, config_type, f"来自 {source}")
    
    def _infer_config_type(self, key: str) -> ConfigType:
        """推断配置类型"""
        key_lower = key.lower()
        
        if any(word in key_lower for word in ['db', 'database', 'sql']):
            return ConfigType.DATABASE
        elif any(word in key_lower for word in ['secret', 'password', 'token', 'auth', 'security']):
            return ConfigType.SECURITY
        elif any(word in key_lower for word in ['enable', 'disable', 'flag', 'feature']):
            return ConfigType.FEATURE
        elif any(word in key_lower for word in ['log', 'logging']):
            return ConfigType.LOGGING
        elif any(word in key_lower for word in ['cache', 'pool', 'timeout', 'limit', 'performance']):
            return ConfigType.PERFORMANCE
        elif any(word in key_lower for word in ['api', 'webhook', 'integration']):
            return ConfigType.INTEGRATION
        elif any(word in key_lower for word in ['business', 'company', 'default']):
            return ConfigType.BUSINESS
        else:
            return ConfigType.SYSTEM
    
    def set_config(self, key: str, value: Any, config_type: ConfigType = ConfigType.SYSTEM, 
                   description: str = "", required: bool = False, 
                   default_value: Any = None, validator_func: callable = None) -> bool:
        """设置配置项"""
        try:
            config_item = ConfigItem(
                key=key,
                value=value,
                config_type=config_type,
                description=description,
                required=required,
                default_value=default_value,
                validator_func=validator_func,
                environment=self.environment
            )
            
            if not config_item.validate():
                logger.error(f"配置项验证失败: {key}")
                return False
            
            # 更新现有配置项的时间戳
            if key in self.configs:
                config_item.created_at = self.configs[key].created_at
                config_item.updated_at = datetime.now()
            
            self.configs[key] = config_item
            
            # 通知观察者
            self._notify_watchers(key, value)
            
            return True
            
        except Exception as e:
            logger.error(f"设置配置项失败 {key}: {str(e)}")
            return False
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        if key in self.configs:
            return self.configs[key].get_effective_value()
        
        # 尝试从环境变量获取
        env_value = os.getenv(key.upper().replace('.', '_'))
        if env_value is not None:
            return self._convert_env_value(env_value)
        
        return default
    
    def _convert_env_value(self, value: str) -> Any:
        """转换环境变量值"""
        # 布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # 字符串
        return value
    
    def get_config_item(self, key: str) -> Optional[ConfigItem]:
        """获取配置项对象"""
        return self.configs.get(key)
    
    def has_config(self, key: str) -> bool:
        """检查配置是否存在"""
        return key in self.configs or os.getenv(key.upper().replace('.', '_')) is not None
    
    def remove_config(self, key: str) -> bool:
        """删除配置项"""
        if key in self.configs:
            del self.configs[key]
            self._notify_watchers(key, None)
            return True
        return False
    
    def get_configs_by_type(self, config_type: ConfigType) -> Dict[str, ConfigItem]:
        """按类型获取配置项"""
        return {k: v for k, v in self.configs.items() if v.config_type == config_type}
    
    def get_all_configs(self) -> Dict[str, ConfigItem]:
        """获取所有配置项"""
        return self.configs.copy()
    
    def validate_all_configs(self) -> Dict[str, bool]:
        """验证所有配置项"""
        results = {}
        for key, config_item in self.configs.items():
            results[key] = config_item.validate()
        return results
    
    def export_config(self, file_path: str, config_type: ConfigType = None, 
                      format: str = 'yaml') -> bool:
        """导出配置"""
        try:
            configs_to_export = self.configs
            if config_type:
                configs_to_export = self.get_configs_by_type(config_type)
            
            export_data = {}
            for key, config_item in configs_to_export.items():
                export_data[key] = {
                    'value': config_item.get_effective_value(),
                    'type': config_item.config_type.value,
                    'description': config_item.description,
                    'required': config_item.required,
                    'environment': config_item.environment.value if config_item.environment else None
                }
            
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == 'yaml':
                with open(file_path_obj, 'w', encoding='utf-8') as f:
                    yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)
            elif format.lower() == 'json':
                with open(file_path_obj, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"不支持的格式: {format}")
            
            return True
            
        except Exception as e:
            logger.error(f"导出配置失败: {str(e)}")
            return False
    
    def import_config(self, file_path: str, override: bool = False) -> bool:
        """导入配置"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"配置文件不存在: {file_path}")
                return False
            
            if file_path_obj.suffix.lower() in ['.yaml', '.yml']:
                with open(file_path_obj, 'r', encoding='utf-8') as f:
                    import_data = yaml.safe_load(f)
            elif file_path_obj.suffix.lower() == '.json':
                with open(file_path_obj, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
            else:
                logger.error(f"不支持的文件格式: {file_path_obj.suffix}")
                return False
            
            for key, config_data in import_data.items():
                if not override and key in self.configs:
                    continue
                
                if isinstance(config_data, dict):
                    value = config_data.get('value')
                    config_type_str = config_data.get('type', 'system')
                    description = config_data.get('description', '')
                    required = config_data.get('required', False)
                    
                    try:
                        config_type = ConfigType(config_type_str)
                    except ValueError:
                        config_type = ConfigType.SYSTEM
                    
                    self.set_config(key, value, config_type, description, required)
                else:
                    # 简单值
                    self.set_config(key, config_data)
            
            return True
            
        except Exception as e:
            logger.error(f"导入配置失败: {str(e)}")
            return False
    
    def watch_config(self, callback: callable):
        """监听配置变化"""
        self._watchers.append(callback)
    
    def unwatch_config(self, callback: callable):
        """取消监听配置变化"""
        if callback in self._watchers:
            self._watchers.remove(callback)
    
    def _notify_watchers(self, key: str, value: Any):
        """通知观察者"""
        for watcher in self._watchers:
            try:
                watcher(key, value)
            except Exception as e:
                logger.error(f"配置监听器执行失败: {str(e)}")
    
    def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            # 清除当前配置（保留默认配置）
            system_configs = {k: v for k, v in self.configs.items() 
                             if v.config_type == ConfigType.SYSTEM and v.description == "应用名称"}
            self.configs = system_configs
            
            # 重新加载
            self._load_default_configs()
            self._load_config_files()
            
            logger.info("配置重新加载成功")
            return True
            
        except Exception as e:
            logger.error(f"重新加载配置失败: {str(e)}")
            return False
    
    def get_environment_info(self) -> Dict[str, Any]:
        """获取环境信息"""
        return {
            "environment": self.environment.value,
            "config_dir": str(self.config_dir),
            "config_files": list(self.config_files.keys()),
            "total_configs": len(self.configs),
            "config_types": list(set(item.config_type.value for item in self.configs.values()))
        }


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_database_config(config: DatabaseConfig) -> List[str]:
        """验证数据库配置"""
        errors = []
        
        if not config.host:
            errors.append("数据库主机不能为空")
        
        if not config.username:
            errors.append("数据库用户名不能为空")
        
        if not config.database:
            errors.append("数据库名不能为空")
        
        try:
            # 尝试连接数据库（这里只是示例，实际可能需要更复杂的验证）
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((config.host, config.port))
            sock.close()
            
            if result != 0:
                errors.append(f"无法连接到数据库服务器 {config.host}:{config.port}")
        except Exception as e:
            errors.append(f"数据库连接验证失败: {str(e)}")
        
        return errors
    
    @staticmethod
    def validate_security_config(config: SecurityConfig) -> List[str]:
        """验证安全配置"""
        errors = []
        
        if len(config.secret_key) < 32:
            errors.append("密钥长度至少32个字符")
        
        if config.access_token_expire_minutes < 1:
            errors.append("访问令牌过期时间必须大于0")
        
        if config.password_min_length < 6:
            errors.append("密码最小长度不能小于6")
        
        if config.max_login_attempts < 1:
            errors.append("最大登录尝试次数必须大于0")
        
        return errors
    
    @staticmethod
    def validate_business_config(config: BusinessConfig) -> List[str]:
        """验证业务配置"""
        errors = []
        
        if config.default_page_size < 1:
            errors.append("默认页面大小必须大于0")
        
        if config.max_page_size < config.default_page_size:
            errors.append("最大页面大小不能小于默认页面大小")
        
        if config.max_file_size_mb < 1 or config.max_file_size_mb > 100:
            errors.append("文件大小限制必须在1-100MB之间")
        
        # 验证邮箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, config.support_email):
            errors.append("支持邮箱格式不正确")
        
        return errors


# 全局配置管理器实例
config_manager = ConfigManager()

# 配置实例
database_config = DatabaseConfig()
security_config = SecurityConfig()
feature_flags = FeatureFlags()
business_config = BusinessConfig()
performance_config = PerformanceConfig()

# 配置验证器实例
config_validator = ConfigValidator()


# 装饰器
def require_config(config_key: str, default_value: Any = None):
    """要求配置装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            config_value = config_manager.get_config(config_key, default_value)
            if config_value is None:
                raise ValueError(f"缺少必需的配置: {config_key}")
            
            # 将配置值作为参数传递给函数
            kwargs[f'config_{config_key.replace(".", "_")}'] = config_value
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def feature_flag(flag_name: str, default: bool = False):
    """功能开关装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            is_enabled = config_manager.get_config(flag_name, default)
            if not is_enabled:
                raise ValueError(f"功能未启用: {flag_name}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def config_cached(cache_key: str = None, ttl: int = 300):
    """配置缓存装饰器"""
    cache = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = cache_key or f"{func.__name__}_{hash(str(args) + str(kwargs))}"
            current_time = datetime.now().timestamp()
            
            # 检查缓存
            if key in cache:
                cached_time, cached_value = cache[key]
                if current_time - cached_time < ttl:
                    return cached_value
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[key] = (current_time, result)
            
            return result
        
        return wrapper
    return decorator


# 常用配置获取函数
def get_database_url() -> str:
    """获取数据库连接URL"""
    return database_config.get_database_url()


def get_redis_config() -> Dict[str, Any]:
    """获取Redis配置"""
    return {
        'enabled': config_manager.get_config('redis_enabled', True),
        'host': config_manager.get_config('redis_host', 'localhost'),
        'port': config_manager.get_config('redis_port', 6379),
        'db': config_manager.get_config('redis_db', 0),
        'password': config_manager.get_config('redis_password', None),
        'socket_timeout': config_manager.get_config('redis_socket_timeout', 30),
        'socket_connect_timeout': config_manager.get_config('redis_socket_connect_timeout', 30),
        'socket_keepalive': config_manager.get_config('redis_socket_keepalive', 30),
        'socket_keepalive_delay': config_manager.get_config('redis_socket_keepalive_delay', 30),
        'socket_keepalive_interval': config_manager.get_config('redis_socket_keepalive_interval', 30),
        'socket_keepalive_max_failures': config_manager.get_config('redis_socket_keepalive_max_failures', 3)
    }


def is_debug_mode() -> bool:
    """是否调试模式"""
    return config_manager.get_config('debug', False)


def is_feature_enabled(feature_name: str) -> bool:
    """检查功能是否启用"""
    return config_manager.get_config(f'enable_{feature_name}', False)


def get_app_info() -> Dict[str, Any]:
    """获取应用信息"""
    return {
        'name': config_manager.get_config('app_name', '项目管理系统'),
        'version': config_manager.get_config('app_version', '1.0.0'),
        'environment': config_manager.environment.value,
        'debug': is_debug_mode()
    }


def get_security_settings() -> Dict[str, Any]:
    """获取安全设置"""
    return {
        'password_min_length': security_config.password_min_length,
        'max_login_attempts': security_config.max_login_attempts,
        'session_timeout': security_config.session_timeout_minutes,
        'enable_2fa': security_config.enable_2fa
    }


def get_business_settings() -> Dict[str, Any]:
    """获取业务设置"""
    return {
        'default_page_size': business_config.default_page_size,
        'max_page_size': business_config.max_page_size,
        'max_file_size_mb': business_config.max_file_size_mb,
        'allowed_extensions': business_config.get_allowed_extensions(),
        'company_name': business_config.company_name,
        'support_email': business_config.support_email
    }


def validate_all_configs() -> Dict[str, List[str]]:
    """验证所有配置"""
    validation_results = {}
    
    # 验证数据库配置
    db_errors = config_validator.validate_database_config(database_config)
    if db_errors:
        validation_results['database'] = db_errors
    
    # 验证安全配置
    security_errors = config_validator.validate_security_config(security_config)
    if security_errors:
        validation_results['security'] = security_errors
    
    # 验证业务配置
    business_errors = config_validator.validate_business_config(business_config)
    if business_errors:
        validation_results['business'] = business_errors
    
    # 验证配置管理器中的配置
    config_validation = config_manager.validate_all_configs()
    invalid_configs = [k for k, v in config_validation.items() if not v]
    if invalid_configs:
        validation_results['config_manager'] = [f"配置项验证失败: {', '.join(invalid_configs)}"]
    
    return validation_results