"""权限缓存机制模块

提供高性能的权限缓存功能，减少数据库查询，提升权限验证效率
"""
import json
import hashlib
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from redis import Redis
from redis.exceptions import RedisError

from models.database import get_db
# from services.permission_service import get_permission_service  # 避免循环导入，在函数内部导入
from utils.cache_manager import cache_manager
from utils.logging_middleware import logger
from utils.config_manager import get_redis_config


class PermissionCacheConfig:
    """权限缓存配置类"""
    
    def __init__(self):
        # 缓存过期时间配置（秒）
        self.user_permissions_ttl = 3600  # 用户权限缓存1小时
        self.role_permissions_ttl = 7200  # 角色权限缓存2小时
        self.permission_matrix_ttl = 1800  # 权限矩阵缓存30分钟
        self.resource_access_ttl = 1800   # 资源访问权限缓存30分钟
        
        # 缓存键前缀
        self.user_permissions_prefix = "perm:user:"
        self.role_permissions_prefix = "perm:role:"
        self.permission_matrix_prefix = "perm:matrix:"
        self.resource_access_prefix = "perm:resource:"
        self.batch_check_prefix = "perm:batch:"
        
        # 缓存刷新配置
        self.auto_refresh_enabled = True
        self.refresh_threshold = 0.8  # 缓存剩余时间低于80%时触发刷新
        self.max_refresh_workers = 3  # 最大刷新工作线程数
        
        # 缓存预热配置
        self.warmup_enabled = True
        self.warmup_batch_size = 100
        self.warmup_delay = 60  # 启动后延迟60秒开始预热
        
        # 性能监控配置
        self.enable_metrics = True
        self.metrics_window = 300  # 性能指标统计窗口5分钟


class PermissionCacheMetrics:
    """权限缓存性能指标类"""
    
    def __init__(self):
        self.hit_count = 0
        self.miss_count = 0
        self.error_count = 0
        self.refresh_count = 0
        self.warmup_count = 0
        
        self.response_times = []
        self.cache_sizes = defaultdict(int)
        
        self._lock = threading.Lock()
    
    def record_hit(self, response_time: float = 0):
        """记录缓存命中"""
        with self._lock:
            self.hit_count += 1
            if response_time > 0:
                self.response_times.append(response_time)
    
    def record_miss(self, response_time: float = 0):
        """记录缓存未命中"""
        with self._lock:
            self.miss_count += 1
            if response_time > 0:
                self.response_times.append(response_time)
    
    def record_error(self):
        """记录缓存错误"""
        with self._lock:
            self.error_count += 1
    
    def record_refresh(self):
        """记录缓存刷新"""
        with self._lock:
            self.refresh_count += 1
    
    def record_warmup(self):
        """记录缓存预热"""
        with self._lock:
            self.warmup_count += 1
    
    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0
    
    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "error_count": self.error_count,
            "hit_rate": self.get_hit_rate(),
            "avg_response_time": self.get_avg_response_time(),
            "refresh_count": self.refresh_count,
            "warmup_count": self.warmup_count,
            "cache_sizes": dict(self.cache_sizes)
        }


class PermissionCache:
    """权限缓存管理器"""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.config = PermissionCacheConfig()
        self.metrics = PermissionCacheMetrics()
        
        # Redis客户端
        self.redis_client = redis_client or self._create_redis_client()
        
        # 本地缓存（作为Redis的备份）
        self.local_cache = {}
        self.local_cache_lock = threading.RLock()
        
        # 刷新任务执行器
        self.refresh_executor = ThreadPoolExecutor(max_workers=self.config.max_refresh_workers)
        
        # 缓存状态
        self.is_healthy = True
        self.last_health_check = datetime.now()
        
        # 启动后台任务
        if self.config.auto_refresh_enabled:
            self._start_background_tasks()
    
    def _create_redis_client(self) -> Optional[Redis]:
        """创建Redis客户端"""
        try:
            redis_config = get_redis_config()
            
            # 检查Redis是否被启用
            if not redis_config.get('enabled', True):
                logger.info("Redis缓存已被配置禁用，将仅使用本地缓存")
                return None
                
            return Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password'),
                decode_responses=True,
                socket_timeout=redis_config.get('socket_timeout', 5),
                socket_connect_timeout=redis_config.get('socket_connect_timeout', 5),
                retry_on_timeout=True
            )
        except Exception as e:
            logger.warning(f"Redis连接失败，将使用本地缓存: {e}")
            return None
    
    def _start_background_tasks(self):
        """启动后台任务"""
        # 启动缓存预热任务
        if self.config.warmup_enabled:
            threading.Timer(self.config.warmup_delay, self._warmup_cache).start()
        
        # 启动健康检查任务
        threading.Timer(60, self._health_check_loop).start()
    
    def _generate_cache_key(self, prefix: str, *args) -> str:
        """生成缓存键
        
        Args:
            prefix: 键前缀
            *args: 键参数
            
        Returns:
            str: 缓存键
        """
        key_parts = [str(arg) for arg in args]
        key_suffix = ":".join(key_parts)
        return f"{prefix}{key_suffix}"
    
    def _serialize_value(self, value: Any) -> str:
        """序列化缓存值"""
        return json.dumps(value, ensure_ascii=False, default=str)
    
    def _deserialize_value(self, value: str) -> Any:
        """反序列化缓存值"""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    def _set_cache(self, key: str, value: Any, ttl: int) -> bool:
        """设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        try:
            serialized_value = self._serialize_value(value)
            
            # 优先使用Redis
            if self.redis_client and self.is_healthy:
                self.redis_client.setex(key, ttl, serialized_value)
                self.metrics.cache_sizes['redis'] += 1
            
            # 同时设置本地缓存
            with self.local_cache_lock:
                expire_time = datetime.now() + timedelta(seconds=ttl)
                self.local_cache[key] = {
                    'value': serialized_value,
                    'expire_time': expire_time
                }
                self.metrics.cache_sizes['local'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"设置缓存失败 {key}: {e}")
            self.metrics.record_error()
            return False
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值，不存在返回None
        """
        try:
            # 优先从Redis获取
            if self.redis_client and self.is_healthy:
                value = self.redis_client.get(key)
                if value is not None:
                    return self._deserialize_value(value)
            
            # 从本地缓存获取
            with self.local_cache_lock:
                cache_item = self.local_cache.get(key)
                if cache_item:
                    if datetime.now() < cache_item['expire_time']:
                        return self._deserialize_value(cache_item['value'])
                    else:
                        # 缓存已过期，删除
                        del self.local_cache[key]
            
            return None
            
        except Exception as e:
            logger.error(f"获取缓存失败 {key}: {e}")
            self.metrics.record_error()
            return None
    
    def _delete_cache(self, key: str) -> bool:
        """删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 从Redis删除
            if self.redis_client and self.is_healthy:
                self.redis_client.delete(key)
            
            # 从本地缓存删除
            with self.local_cache_lock:
                self.local_cache.pop(key, None)
            
            return True
            
        except Exception as e:
            logger.error(f"删除缓存失败 {key}: {e}")
            self.metrics.record_error()
            return False
    
    def get_user_permissions(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        """获取用户权限（带缓存）
        
        Args:
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            List[Dict[str, Any]]: 用户权限列表
        """
        start_time = datetime.now()
        cache_key = self._generate_cache_key(self.config.user_permissions_prefix, user_id)
        
        # 尝试从缓存获取
        cached_permissions = self._get_cache(cache_key)
        if cached_permissions is not None:
            self.metrics.record_hit((datetime.now() - start_time).total_seconds())
            return cached_permissions
        
        # 缓存未命中，从数据库获取
        try:
            from services.permission_service import get_permission_service  # 避免循环导入
            permission_service = get_permission_service(db)
            permissions = permission_service.get_user_permissions(user_id)
            
            # 转换为可序列化的格式
            serializable_permissions = [
                {
                    'id': perm.id,
                    'code': perm.code,
                    'name': perm.name,
                    'resource_type': perm.resource_type,
                    'action_type': perm.action_type,
                    'description': perm.description
                }
                for perm in permissions
            ]
            
            # 设置缓存
            self._set_cache(cache_key, serializable_permissions, self.config.user_permissions_ttl)
            
            self.metrics.record_miss((datetime.now() - start_time).total_seconds())
            return serializable_permissions
            
        except Exception as e:
            logger.error(f"获取用户权限失败 {user_id}: {e}")
            self.metrics.record_error()
            return []
    
    def check_user_permission(self, user_id: str, resource_type: str, action_type: str, 
                            resource_id: Optional[str] = None, db: Session = None) -> bool:
        """检查用户权限（带缓存）
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            action_type: 操作类型
            resource_id: 资源ID（可选）
            db: 数据库会话
            
        Returns:
            bool: 是否有权限
        """
        start_time = datetime.now()
        
        # 生成缓存键
        cache_key_parts = [user_id, resource_type, action_type]
        if resource_id:
            cache_key_parts.append(resource_id)
        cache_key = self._generate_cache_key(self.config.resource_access_prefix, *cache_key_parts)
        
        # 尝试从缓存获取
        cached_result = self._get_cache(cache_key)
        if cached_result is not None:
            self.metrics.record_hit((datetime.now() - start_time).total_seconds())
            return cached_result
        
        # 缓存未命中，从数据库检查
        try:
            if not db:
                db = next(get_db())
            
            from services.permission_service import get_permission_service  # 避免循环导入
            permission_service = get_permission_service(db)
            has_permission = permission_service.check_user_permission(
                user_id=user_id,
                resource_type=resource_type,
                action_type=action_type,
                resource_id=resource_id
            )
            
            # 设置缓存
            self._set_cache(cache_key, has_permission, self.config.resource_access_ttl)
            
            self.metrics.record_miss((datetime.now() - start_time).total_seconds())
            return has_permission
            
        except Exception as e:
            logger.error(f"检查用户权限失败 {user_id}: {e}")
            self.metrics.record_error()
            return False
    
    def batch_check_permissions(self, user_id: str, permission_checks: List[Tuple[str, str]], 
                              db: Session = None) -> Dict[str, bool]:
        """批量检查权限（带缓存）
        
        Args:
            user_id: 用户ID
            permission_checks: 权限检查列表，每个元素为(resource_type, action_type)元组
            db: 数据库会话
            
        Returns:
            Dict[str, bool]: 权限检查结果，键为"resource_type:action_type"
        """
        start_time = datetime.now()
        
        # 生成批量检查的缓存键
        checks_hash = hashlib.md5(
            json.dumps(sorted(permission_checks), ensure_ascii=False).encode()
        ).hexdigest()
        cache_key = self._generate_cache_key(self.config.batch_check_prefix, user_id, checks_hash)
        
        # 尝试从缓存获取
        cached_results = self._get_cache(cache_key)
        if cached_results is not None:
            self.metrics.record_hit((datetime.now() - start_time).total_seconds())
            return cached_results
        
        # 缓存未命中，执行批量检查
        try:
            if not db:
                db = next(get_db())
            
            from services.permission_service import get_permission_service  # 避免循环导入
            permission_service = get_permission_service(db)
            results = permission_service.batch_check_permissions(
                user_id=user_id,
                permission_checks=permission_checks
            )
            
            # 设置缓存
            self._set_cache(cache_key, results, self.config.resource_access_ttl)
            
            self.metrics.record_miss((datetime.now() - start_time).total_seconds())
            return results
            
        except Exception as e:
            logger.error(f"批量检查权限失败 {user_id}: {e}")
            self.metrics.record_error()
            return {f"{rt}:{at}": False for rt, at in permission_checks}
    
    def invalidate_user_cache(self, user_id: str):
        """清除用户相关缓存
        
        Args:
            user_id: 用户ID
        """
        try:
            # 清除用户权限缓存
            user_perm_key = self._generate_cache_key(self.config.user_permissions_prefix, user_id)
            self._delete_cache(user_perm_key)
            
            # 清除用户资源访问缓存（需要模糊匹配）
            self._delete_cache_pattern(f"{self.config.resource_access_prefix}{user_id}:*")
            self._delete_cache_pattern(f"{self.config.batch_check_prefix}{user_id}:*")
            
            logger.info(f"已清除用户 {user_id} 的权限缓存")
            
        except Exception as e:
            logger.error(f"清除用户缓存失败 {user_id}: {e}")
    
    def invalidate_role_cache(self, role_id: str):
        """清除角色相关缓存
        
        Args:
            role_id: 角色ID
        """
        try:
            # 清除角色权限缓存
            role_perm_key = self._generate_cache_key(self.config.role_permissions_prefix, role_id)
            self._delete_cache(role_perm_key)
            
            # 清除权限矩阵缓存
            self._delete_cache_pattern(f"{self.config.permission_matrix_prefix}*")
            
            logger.info(f"已清除角色 {role_id} 的权限缓存")
            
        except Exception as e:
            logger.error(f"清除角色缓存失败 {role_id}: {e}")
    
    def _delete_cache_pattern(self, pattern: str):
        """删除匹配模式的缓存键
        
        Args:
            pattern: 匹配模式
        """
        try:
            # Redis模式删除
            if self.redis_client and self.is_healthy:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            
            # 本地缓存模式删除
            with self.local_cache_lock:
                import fnmatch
                keys_to_delete = [
                    key for key in self.local_cache.keys() 
                    if fnmatch.fnmatch(key, pattern)
                ]
                for key in keys_to_delete:
                    del self.local_cache[key]
                    
        except Exception as e:
            logger.error(f"删除缓存模式失败 {pattern}: {e}")
    
    def _warmup_cache(self):
        """缓存预热"""
        try:
            logger.info("开始权限缓存预热")
            
            # 获取活跃用户列表进行预热
            db = next(get_db())
            from services.permission_service import get_permission_service  # 避免循环导入
            permission_service = get_permission_service(db)
            
            # 这里可以根据实际需求实现预热逻辑
            # 例如：预热最近活跃的用户权限
            
            self.metrics.record_warmup()
            logger.info("权限缓存预热完成")
            
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
    
    def _health_check_loop(self):
        """健康检查循环"""
        try:
            self._health_check()
            # 每分钟检查一次
            threading.Timer(60, self._health_check_loop).start()
        except Exception as e:
            logger.error(f"健康检查循环异常: {e}")
    
    def _health_check(self):
        """健康检查"""
        try:
            if self.redis_client:
                # 测试Redis连接
                self.redis_client.ping()
                self.is_healthy = True
            
            self.last_health_check = datetime.now()
            
        except Exception as e:
            logger.warning(f"Redis健康检查失败: {e}")
            self.is_healthy = False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 缓存统计信息
        """
        stats = self.metrics.get_metrics_summary()
        stats.update({
            'is_healthy': self.is_healthy,
            'last_health_check': self.last_health_check.isoformat(),
            'redis_available': self.redis_client is not None and self.is_healthy,
            'local_cache_size': len(self.local_cache)
        })
        return stats
    
    def clear_all_cache(self):
        """清除所有缓存"""
        try:
            # 清除Redis缓存
            if self.redis_client and self.is_healthy:
                # 删除所有权限相关的键
                patterns = [
                    f"{self.config.user_permissions_prefix}*",
                    f"{self.config.role_permissions_prefix}*",
                    f"{self.config.permission_matrix_prefix}*",
                    f"{self.config.resource_access_prefix}*",
                    f"{self.config.batch_check_prefix}*"
                ]
                
                for pattern in patterns:
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
            
            # 清除本地缓存
            with self.local_cache_lock:
                self.local_cache.clear()
            
            logger.info("已清除所有权限缓存")
            
        except Exception as e:
            logger.error(f"清除所有缓存失败: {e}")


# 全局权限缓存实例
permission_cache = PermissionCache()


def cached_permission_check(resource_type: str, action_type: str, 
                          resource_id_param: Optional[str] = None):
    """带缓存的权限检查装饰器
    
    Args:
        resource_type: 资源类型
        action_type: 操作类型
        resource_id_param: 资源ID参数名（可选）
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取当前用户和数据库会话
            current_user = kwargs.get('current_user')
            db = kwargs.get('db')
            
            if not current_user or not db:
                raise HTTPException(status_code=500, detail="权限检查装饰器配置错误")
            
            # 获取资源ID
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = kwargs[resource_id_param]
            
            # 使用缓存检查权限
            has_permission = permission_cache.check_user_permission(
                user_id=current_user.id,
                resource_type=resource_type,
                action_type=action_type,
                resource_id=resource_id,
                db=db
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail=f"权限不足：需要 {resource_type}:{action_type} 权限"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_permission_cache() -> PermissionCache:
    """获取权限缓存实例
    
    Returns:
        PermissionCache: 权限缓存实例
    """
    return permission_cache