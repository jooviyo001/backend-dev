"""数据库连接池优化配置

提供数据库连接池的优化配置和管理功能
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from contextlib import contextmanager
import time
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DatabasePoolConfig:
    """
    数据库连接池配置类
    """
    
    def __init__(self):
        # 连接池基础配置
        self.pool_size = 10  # 连接池大小
        self.max_overflow = 20  # 最大溢出连接数
        self.pool_timeout = 30  # 获取连接超时时间（秒）
        self.pool_recycle = 3600  # 连接回收时间（秒）
        self.pool_pre_ping = True  # 连接前ping检查
        
        # 连接配置
        self.connect_args = {
            "check_same_thread": False,  # SQLite特定
            "timeout": 20,  # 连接超时
        }
        
        # 引擎配置
        self.echo = False  # 是否打印SQL
        self.echo_pool = False  # 是否打印连接池日志
        self.future = True  # 使用SQLAlchemy 2.0风格
        
        # 性能优化配置
        self.isolation_level = "READ_COMMITTED"  # 事务隔离级别
        self.autocommit = False  # 自动提交
        self.autoflush = True  # 自动刷新
    
    def get_engine_kwargs(self) -> Dict[str, Any]:
        """
        获取引擎创建参数
        """
        return {
            "poolclass": QueuePool,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "connect_args": self.connect_args,
            "echo": self.echo,
            "echo_pool": self.echo_pool,
            "future": self.future,
            "isolation_level": self.isolation_level,
        }


class DatabasePoolMonitor:
    """
    数据库连接池监控器
    """
    
    def __init__(self):
        self.connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "overflow_connections": 0,
            "connection_errors": 0,
            "slow_queries": 0,
            "last_reset": datetime.now()
        }
        self.lock = threading.Lock()
    
    def update_stats(self, engine: Engine):
        """
        更新连接池统计信息
        """
        with self.lock:
            try:
                pool = engine.pool
                self.connection_stats.update({
                    "total_connections": pool.size(),
                    "active_connections": pool.checkedout(),
                    "idle_connections": pool.checkedin(),
                    "overflow_connections": pool.overflow(),
                })
            except Exception as e:
                logger.error(f"更新连接池统计失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取连接池统计信息
        """
        with self.lock:
            return self.connection_stats.copy()
    
    def reset_stats(self):
        """
        重置统计信息
        """
        with self.lock:
            self.connection_stats.update({
                "connection_errors": 0,
                "slow_queries": 0,
                "last_reset": datetime.now()
            })
    
    def log_connection_error(self):
        """
        记录连接错误
        """
        with self.lock:
            self.connection_stats["connection_errors"] += 1
    
    def log_slow_query(self):
        """
        记录慢查询
        """
        with self.lock:
            self.connection_stats["slow_queries"] += 1


# 全局连接池监控器
pool_monitor = DatabasePoolMonitor()


def create_optimized_engine(database_url: str, config: Optional[DatabasePoolConfig] = None) -> Engine:
    """
    创建优化的数据库引擎
    
    Args:
        database_url: 数据库连接URL
        config: 连接池配置
        
    Returns:
        优化的SQLAlchemy引擎
    """
    if config is None:
        config = DatabasePoolConfig()
    
    # 根据数据库类型调整配置
    if "sqlite" in database_url.lower():
        # SQLite特定优化
        config.pool_size = 1
        config.max_overflow = 0
        config.connect_args.update({
            "check_same_thread": False,
            "timeout": 20,
        })
    elif "postgresql" in database_url.lower():
        # PostgreSQL特定优化
        config.connect_args.update({
            "application_name": "defect_management_system",
            "connect_timeout": 10,
        })
    elif "mysql" in database_url.lower():
        # MySQL特定优化
        config.connect_args.update({
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        })
    
    # 创建引擎
    engine = create_engine(database_url, **config.get_engine_kwargs())
    
    # 设置事件监听器
    setup_engine_events(engine)
    
    logger.info(f"数据库引擎已创建: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    return engine


def setup_engine_events(engine: Engine):
    """
    设置引擎事件监听器
    
    Args:
        engine: SQLAlchemy引擎
    """
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """
        SQLite连接优化设置
        """
        if "sqlite" in str(engine.url).lower():
            cursor = dbapi_connection.cursor()
            # 启用外键约束
            cursor.execute("PRAGMA foreign_keys=ON")
            # 设置WAL模式提升并发性能
            cursor.execute("PRAGMA journal_mode=WAL")
            # 设置同步模式
            cursor.execute("PRAGMA synchronous=NORMAL")
            # 设置缓存大小
            cursor.execute("PRAGMA cache_size=10000")
            # 设置临时存储
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
    
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """
        连接检出事件
        """
        pool_monitor.update_stats(engine)
    
    @event.listens_for(engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """
        连接检入事件
        """
        pool_monitor.update_stats(engine)
    
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        """
        新连接创建事件
        """
        logger.debug("新数据库连接已创建")
    
    @event.listens_for(engine, "close")
    def receive_close(dbapi_connection, connection_record):
        """
        连接关闭事件
        """
        logger.debug("数据库连接已关闭")
    
    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """
        查询执行前事件
        """
        context._query_start_time = time.time()
    
    @event.listens_for(engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """
        查询执行后事件
        """
        total = time.time() - context._query_start_time
        if total > 1.0:  # 慢查询阈值1秒
            pool_monitor.log_slow_query()
            logger.warning(f"慢查询检测: {total:.3f}s - {statement[:100]}...")
    
    @event.listens_for(engine, "handle_error")
    def receive_handle_error(exception_context):
        """
        错误处理事件
        """
        pool_monitor.log_connection_error()
        logger.error(f"数据库错误: {exception_context.original_exception}")


@contextmanager
def get_db_connection(engine: Engine):
    """
    获取数据库连接的上下文管理器
    
    Args:
        engine: SQLAlchemy引擎
        
    Yields:
        数据库连接
    """
    connection = None
    try:
        connection = engine.connect()
        yield connection
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"数据库连接错误: {e}")
        raise
    finally:
        if connection:
            connection.close()


class ConnectionPoolHealthChecker:
    """
    连接池健康检查器
    """
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.last_check = datetime.now()
        self.check_interval = timedelta(minutes=5)
    
    def check_health(self) -> Dict[str, Any]:
        """
        检查连接池健康状态
        
        Returns:
            健康状态报告
        """
        now = datetime.now()
        if now - self.last_check < self.check_interval:
            return {"status": "skipped", "message": "检查间隔未到"}
        
        self.last_check = now
        health_report = {
            "status": "healthy",
            "timestamp": now.isoformat(),
            "issues": []
        }
        
        try:
            # 检查连接池状态
            pool = self.engine.pool
            stats = pool_monitor.get_stats()
            
            # 检查连接池是否过载
            if stats["active_connections"] > pool.size() * 0.8:
                health_report["issues"].append("连接池使用率过高")
                health_report["status"] = "warning"
            
            # 检查溢出连接
            if stats["overflow_connections"] > 0:
                health_report["issues"].append("存在溢出连接")
                health_report["status"] = "warning"
            
            # 检查连接错误率
            if stats["connection_errors"] > 10:
                health_report["issues"].append("连接错误率过高")
                health_report["status"] = "error"
            
            # 检查慢查询
            if stats["slow_queries"] > 50:
                health_report["issues"].append("慢查询过多")
                health_report["status"] = "warning"
            
            # 测试连接
            with get_db_connection(self.engine) as conn:
                conn.execute("SELECT 1")
            
            health_report["pool_stats"] = stats
            
        except Exception as e:
            health_report["status"] = "error"
            health_report["issues"].append(f"连接测试失败: {str(e)}")
            logger.error(f"连接池健康检查失败: {e}")
        
        return health_report
    
    def get_recommendations(self) -> List[str]:
        """
        获取优化建议
        
        Returns:
            优化建议列表
        """
        recommendations = []
        stats = pool_monitor.get_stats()
        
        if stats["active_connections"] > self.engine.pool.size() * 0.8:
            recommendations.append("考虑增加连接池大小")
        
        if stats["overflow_connections"] > 5:
            recommendations.append("考虑增加max_overflow设置")
        
        if stats["slow_queries"] > 20:
            recommendations.append("优化慢查询，添加适当索引")
        
        if stats["connection_errors"] > 5:
            recommendations.append("检查网络连接和数据库服务器状态")
        
        return recommendations


# 连接池配置预设
PRODUCTION_CONFIG = DatabasePoolConfig()
PRODUCTION_CONFIG.pool_size = 20
PRODUCTION_CONFIG.max_overflow = 30
PRODUCTION_CONFIG.pool_timeout = 30
PRODUCTION_CONFIG.pool_recycle = 3600
PRODUCTION_CONFIG.echo = False

DEVELOPMENT_CONFIG = DatabasePoolConfig()
DEVELOPMENT_CONFIG.pool_size = 5
DEVELOPMENT_CONFIG.max_overflow = 10
DEVELOPMENT_CONFIG.pool_timeout = 10
DEVELOPMENT_CONFIG.pool_recycle = 1800
DEVELOPMENT_CONFIG.echo = True

TEST_CONFIG = DatabasePoolConfig()
TEST_CONFIG.pool_size = 1
TEST_CONFIG.max_overflow = 0
TEST_CONFIG.pool_timeout = 5
TEST_CONFIG.pool_recycle = 300
TEST_CONFIG.echo = False