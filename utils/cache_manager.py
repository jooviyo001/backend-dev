"""缓存管理器模块

提供Redis缓存功能和缓存装饰器
"""

import json
import pickle
import hashlib
import time
from typing import Any, Optional, Union, Callable, Dict, List
from functools import wraps
import asyncio
from datetime import datetime, timedelta
import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    import redis
    from redis.asyncio import Redis as AsyncRedis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    AsyncRedis = None

import os
from utils.response_utils import format_timestamp


class CacheManager:
    """
    缓存管理器
    
    支持Redis缓存，提供同步和异步接口，包含缓存统计和性能监控
    """
    
    def __init__(self):
        self.redis_client = None
        self.async_redis_client = None
        self.enabled = False
        
        # 缓存统计
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
            "total_requests": 0,
            "start_time": time.time()
        }
        self.stats_lock = threading.Lock()
        
        # 本地缓存（作为Redis的备份）
        self.local_cache = {}
        self.local_cache_ttl = {}
        self.local_cache_lock = threading.Lock()
        self.max_local_cache_size = 1000
        
        self._init_redis()
    
    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            print("⚠️ Redis未安装，缓存功能将被禁用")
            return
        
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD")
            
            # 同步Redis客户端
            if redis_url.startswith("redis://"):
                self.redis_client = redis.from_url(redis_url)
            else:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=False
                )
            
            # 异步Redis客户端
            self.async_redis_client = AsyncRedis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=False
            )
            
            # 测试连接
            self.redis_client.ping()
            self.enabled = True
            print("✅ Redis缓存已启用")
            
        except Exception as e:
            print(f"⚠️ Redis连接失败，缓存功能将被禁用: {e}")
            self.enabled = False
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        # 创建一个包含所有参数的字符串
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        # 使用MD5哈希来创建固定长度的键
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"cache:{prefix}:{key_hash}"
    
    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        # 设置到本地缓存
        self._set_to_local_cache(key, value, expire)
        
        if not self.enabled:
            return True  # 本地缓存设置成功
        
        try:
            # 序列化数据
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, ensure_ascii=False, default=str)
            else:
                serialized_value = pickle.dumps(value)
            
            # 添加元数据
            cache_data = {
                "data": serialized_value,
                "type": "json" if isinstance(value, (dict, list)) else "pickle",
                "timestamp": format_timestamp(),
                "expire": expire
            }
            
            self.redis_client.setex(
                key,
                expire,
                pickle.dumps(cache_data)
            )
            
            with self.stats_lock:
                self.stats["sets"] += 1
            
            return True
        except Exception as e:
            print(f"缓存设置失败: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self.stats_lock:
            self.stats["total_requests"] += 1
        
        # 首先尝试本地缓存
        local_value = self._get_from_local_cache(key)
        if local_value is not None:
            with self.stats_lock:
                self.stats["hits"] += 1
            return local_value
        
        if not self.enabled:
            with self.stats_lock:
                self.stats["misses"] += 1
            return None
        
        try:
            cached_data = self.redis_client.get(key)
            if cached_data is None:
                with self.stats_lock:
                    self.stats["misses"] += 1
                return None
            
            # 反序列化元数据
            cache_info = pickle.loads(cached_data)
            data_type = cache_info.get("type", "pickle")
            data = cache_info.get("data")
            
            # 反序列化数据
            if data_type == "json":
                deserialized_value = json.loads(data)
            else:
                deserialized_value = pickle.loads(data)
            
            # 存储到本地缓存
            self._set_to_local_cache(key, deserialized_value, 3600)
            
            with self.stats_lock:
                self.stats["hits"] += 1
            
            return deserialized_value
                
        except Exception as e:
            print(f"缓存获取失败: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1
            return None
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        # 从本地缓存删除
        self._delete_from_local_cache(key)
        
        if not self.enabled:
            return True
        
        try:
            result = bool(self.redis_client.delete(key))
            
            with self.stats_lock:
                self.stats["deletes"] += 1
            
            return result
        except Exception as e:
            print(f"缓存删除失败: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """根据模式清除缓存"""
        if not self.enabled:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"批量缓存删除失败: {e}")
            return 0
    
    async def async_set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """异步设置缓存"""
        if not self.enabled or not self.async_redis_client:
            return False
        
        try:
            # 序列化数据
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, ensure_ascii=False, default=str)
            else:
                serialized_value = pickle.dumps(value)
            
            # 添加元数据
            cache_data = {
                "data": serialized_value,
                "type": "json" if isinstance(value, (dict, list)) else "pickle",
                "timestamp": format_timestamp(),
                "expire": expire
            }
            
            await self.async_redis_client.setex(
                key,
                expire,
                pickle.dumps(cache_data)
            )
            return True
        except Exception as e:
            print(f"异步缓存设置失败: {e}")
            return False
    
    def _get_from_local_cache(self, key: str) -> Optional[Any]:
        """
        从本地缓存获取值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或None
        """
        with self.local_cache_lock:
            if key in self.local_cache:
                # 检查是否过期
                if key in self.local_cache_ttl:
                    if time.time() > self.local_cache_ttl[key]:
                        # 已过期，删除
                        del self.local_cache[key]
                        del self.local_cache_ttl[key]
                        return None
                
                return self.local_cache[key]
            
            return None
    
    def _set_to_local_cache(self, key: str, value: Any, ttl: int):
        """
        设置到本地缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        with self.local_cache_lock:
            # 如果缓存已满，删除最旧的条目
            if len(self.local_cache) >= self.max_local_cache_size:
                oldest_key = next(iter(self.local_cache))
                del self.local_cache[oldest_key]
                if oldest_key in self.local_cache_ttl:
                    del self.local_cache_ttl[oldest_key]
            
            self.local_cache[key] = value
            self.local_cache_ttl[key] = time.time() + ttl
    
    def _delete_from_local_cache(self, key: str):
        """
        从本地缓存删除
        
        Args:
            key: 缓存键
        """
        with self.local_cache_lock:
            if key in self.local_cache:
                del self.local_cache[key]
            if key in self.local_cache_ttl:
                del self.local_cache_ttl[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        with self.stats_lock:
            stats = self.stats.copy()
        
        # 计算命中率
        total_requests = stats["total_requests"]
        if total_requests > 0:
            stats["hit_rate"] = stats["hits"] / total_requests
            stats["miss_rate"] = stats["misses"] / total_requests
        else:
            stats["hit_rate"] = 0.0
            stats["miss_rate"] = 0.0
        
        # 运行时间
        stats["uptime"] = time.time() - stats["start_time"]
        
        # 本地缓存统计
        with self.local_cache_lock:
            stats["local_cache_size"] = len(self.local_cache)
            stats["local_cache_max_size"] = self.max_local_cache_size
        
        return stats
    
    def reset_stats(self):
        """
        重置统计信息
        """
        with self.stats_lock:
            self.stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "errors": 0,
                "total_requests": 0,
                "start_time": time.time()
            }
    
    def clear_local_cache(self):
        """
        清空本地缓存
        """
        with self.local_cache_lock:
            self.local_cache.clear()
            self.local_cache_ttl.clear()
    
    def cleanup_expired_local_cache(self):
        """
        清理过期的本地缓存条目
        """
        current_time = time.time()
        expired_keys = []
        
        with self.local_cache_lock:
            for key, expire_time in self.local_cache_ttl.items():
                if current_time > expire_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                if key in self.local_cache:
                    del self.local_cache[key]
                if key in self.local_cache_ttl:
                    del self.local_cache_ttl[key]
        
        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 个过期的本地缓存条目")

    async def async_get(self, key: str) -> Optional[Any]:
        """异步获取缓存"""
        # 首先尝试本地缓存
        local_value = self._get_from_local_cache(key)
        if local_value is not None:
            with self.stats_lock:
                self.stats["hits"] += 1
            return local_value
        
        if not self.enabled or not self.async_redis_client:
            with self.stats_lock:
                self.stats["misses"] += 1
            return None
        
        try:
            cached_data = await self.async_redis_client.get(key)
            if cached_data is None:
                with self.stats_lock:
                    self.stats["misses"] += 1
                return None
            
            # 反序列化元数据
            cache_info = pickle.loads(cached_data)
            data_type = cache_info.get("type", "pickle")
            data = cache_info.get("data")
            
            # 反序列化数据
            if data_type == "json":
                deserialized_value = json.loads(data)
            else:
                deserialized_value = pickle.loads(data)
            
            # 存储到本地缓存
            self._set_to_local_cache(key, deserialized_value, 3600)
            
            with self.stats_lock:
                self.stats["hits"] += 1
            
            return deserialized_value
                
        except Exception as e:
            print(f"异步缓存获取失败: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1
            return None


# 全局缓存管理器实例
cache_manager = CacheManager()


def cache(expire: int = 3600, key_prefix: str = "default"):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_manager._generate_key(f"{key_prefix}:{func.__name__}", *args, **kwargs)
            
            # 尝试从缓存获取
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 缓存结果
            cache_manager.set(cache_key, result, expire)
            
            return result
        
        return wrapper
    return decorator


def async_cache(expire: int = 3600, key_prefix: str = "default"):
    """异步缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_manager._generate_key(f"{key_prefix}:{func.__name__}", *args, **kwargs)
            
            # 尝试从缓存获取
            cached_result = await cache_manager.async_get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 缓存结果
            await cache_manager.async_set(cache_key, result, expire)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """缓存失效装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            # 清除匹配模式的缓存
            cache_manager.clear_pattern(f"cache:{pattern}:*")
            return result
        
        return wrapper
    return decorator


def async_invalidate_cache(pattern: str):
    """异步缓存失效装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 清除匹配模式的缓存
            cache_manager.clear_pattern(f"cache:{pattern}:*")
            return result
        
        return wrapper
    return decorator