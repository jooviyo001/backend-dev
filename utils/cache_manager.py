"""缓存管理器模块

提供Redis缓存功能和缓存装饰器
"""

import json
import pickle
import hashlib
from typing import Any, Optional, Union, Callable
from functools import wraps
import asyncio
from datetime import datetime, timedelta

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
    """缓存管理器"""
    
    def __init__(self):
        self.redis_client = None
        self.async_redis_client = None
        self.enabled = False
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
        if not self.enabled:
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
            
            self.redis_client.setex(
                key,
                expire,
                pickle.dumps(cache_data)
            )
            return True
        except Exception as e:
            print(f"缓存设置失败: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled:
            return None
        
        try:
            cached_data = self.redis_client.get(key)
            if cached_data is None:
                return None
            
            # 反序列化元数据
            cache_info = pickle.loads(cached_data)
            data_type = cache_info.get("type", "pickle")
            data = cache_info.get("data")
            
            # 反序列化数据
            if data_type == "json":
                return json.loads(data)
            else:
                return pickle.loads(data)
                
        except Exception as e:
            print(f"缓存获取失败: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.enabled:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            print(f"缓存删除失败: {e}")
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
    
    async def async_get(self, key: str) -> Optional[Any]:
        """异步获取缓存"""
        if not self.enabled or not self.async_redis_client:
            return None
        
        try:
            cached_data = await self.async_redis_client.get(key)
            if cached_data is None:
                return None
            
            # 反序列化元数据
            cache_info = pickle.loads(cached_data)
            data_type = cache_info.get("type", "pickle")
            data = cache_info.get("data")
            
            # 反序列化数据
            if data_type == "json":
                return json.loads(data)
            else:
                return pickle.loads(data)
                
        except Exception as e:
            print(f"异步缓存获取失败: {e}")
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