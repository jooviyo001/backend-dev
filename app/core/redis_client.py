import redis.asyncio as redis
from typing import Optional, Any
import json
import pickle
from app.core.config import settings

class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """连接Redis"""
        self.redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # 为了支持pickle序列化
            socket_connect_timeout=5,
            socket_timeout=5
        )
        return self.redis
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis:
            await self.redis.close()
    
    async def ping(self) -> bool:
        """测试连接"""
        if not self.redis:
            await self.connect()
        return await self.redis.ping()
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """设置缓存"""
        if not self.redis:
            await self.connect()
        
        # 序列化数据
        if isinstance(value, (dict, list)):
            serialized_value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, str):
            serialized_value = value
        else:
            serialized_value = pickle.dumps(value)
        
        return await self.redis.set(
            key, 
            serialized_value, 
            ex=expire or settings.CACHE_EXPIRE_SECONDS
        )
    
    async def get(self, key: str) -> Any:
        """获取缓存"""
        if not self.redis:
            await self.connect()
        
        value = await self.redis.get(key)
        if value is None:
            return None
        
        # 尝试反序列化
        try:
            # 先尝试JSON
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            try:
                # 再尝试pickle
                return pickle.loads(value)
            except:
                # 最后返回原始字符串
                return value.decode('utf-8') if isinstance(value, bytes) else value
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.redis:
            await self.connect()
        return bool(await self.redis.delete(key))
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self.redis:
            await self.connect()
        return bool(await self.redis.exists(key))
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        if not self.redis:
            await self.connect()
        return bool(await self.redis.expire(key, seconds))
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """递增"""
        if not self.redis:
            await self.connect()
        return await self.redis.incr(key, amount)
    
    async def close(self):
        """关闭连接"""
        await self.disconnect()

# 创建全局Redis客户端实例
redis_client = RedisClient()