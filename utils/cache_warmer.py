from typing import Dict, List, Any, Optional, Callable, Tuple
import asyncio
import logging
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .cache_manager import CacheManager
from .query_optimizer import QueryOptimizer

logger = logging.getLogger(__name__)

class CacheWarmer:
    """
    缓存预热器
    
    用于预热常用缓存，提升系统性能
    """
    
    def __init__(self, cache_manager: CacheManager, max_workers: int = 5):
        self.cache_manager = cache_manager
        self.max_workers = max_workers
        self.warming_tasks = {}
        self.warming_stats = {
            "total_warmed": 0,
            "successful_warmed": 0,
            "failed_warmed": 0,
            "last_warm_time": None,
            "warming_duration": 0
        }
    
    def register_warming_task(self, 
                            task_name: str, 
                            data_loader: Callable[[], Any],
                            cache_key_generator: Callable[[Any], str],
                            ttl: int = 3600,
                            priority: int = 1):
        """
        注册缓存预热任务
        
        Args:
            task_name: 任务名称
            data_loader: 数据加载函数
            cache_key_generator: 缓存键生成函数
            ttl: 缓存过期时间
            priority: 优先级（数字越小优先级越高）
        """
        self.warming_tasks[task_name] = {
            "data_loader": data_loader,
            "cache_key_generator": cache_key_generator,
            "ttl": ttl,
            "priority": priority,
            "last_executed": None,
            "execution_count": 0,
            "success_count": 0,
            "error_count": 0
        }
        
        logger.info(f"注册缓存预热任务: {task_name}")
    
    def warm_cache(self, task_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        执行缓存预热
        
        Args:
            task_names: 要执行的任务名称列表，如果为None则执行所有任务
            
        Returns:
            预热结果统计
        """
        start_time = time.time()
        
        if task_names is None:
            tasks_to_execute = self.warming_tasks
        else:
            tasks_to_execute = {name: task for name, task in self.warming_tasks.items() 
                              if name in task_names}
        
        # 按优先级排序
        sorted_tasks = sorted(tasks_to_execute.items(), 
                            key=lambda x: x[1]["priority"])
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            
            for task_name, task_config in sorted_tasks:
                future = executor.submit(self._execute_warming_task, task_name, task_config)
                future_to_task[future] = task_name
            
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result = future.result()
                    results[task_name] = result
                    
                    if result["success"]:
                        self.warming_stats["successful_warmed"] += result["cached_count"]
                    else:
                        self.warming_stats["failed_warmed"] += 1
                        
                except Exception as e:
                    logger.error(f"预热任务 {task_name} 执行失败: {e}")
                    results[task_name] = {
                        "success": False,
                        "error": str(e),
                        "cached_count": 0,
                        "duration": 0
                    }
                    self.warming_stats["failed_warmed"] += 1
        
        end_time = time.time()
        self.warming_stats["total_warmed"] += len(results)
        self.warming_stats["last_warm_time"] = datetime.now()
        self.warming_stats["warming_duration"] = end_time - start_time
        
        logger.info(f"缓存预热完成，耗时 {end_time - start_time:.2f} 秒，成功 {len([r for r in results.values() if r['success']])} 个任务")
        
        return {
            "total_tasks": len(results),
            "successful_tasks": len([r for r in results.values() if r["success"]]),
            "failed_tasks": len([r for r in results.values() if not r["success"]]),
            "total_cached_items": sum(r["cached_count"] for r in results.values()),
            "duration": end_time - start_time,
            "task_results": results
        }
    
    def _execute_warming_task(self, task_name: str, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个预热任务
        
        Args:
            task_name: 任务名称
            task_config: 任务配置
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            # 加载数据
            data = task_config["data_loader"]()
            
            if not data:
                return {
                    "success": True,
                    "cached_count": 0,
                    "duration": time.time() - start_time,
                    "message": "没有数据需要缓存"
                }
            
            cached_count = 0
            
            # 如果数据是列表，逐个缓存
            if isinstance(data, list):
                for item in data:
                    cache_key = task_config["cache_key_generator"](item)
                    if self.cache_manager.set(cache_key, item, task_config["ttl"]):
                        cached_count += 1
            else:
                # 单个数据项
                cache_key = task_config["cache_key_generator"](data)
                if self.cache_manager.set(cache_key, data, task_config["ttl"]):
                    cached_count = 1
            
            # 更新任务统计
            task_config["last_executed"] = datetime.now()
            task_config["execution_count"] += 1
            task_config["success_count"] += 1
            
            return {
                "success": True,
                "cached_count": cached_count,
                "duration": time.time() - start_time,
                "message": f"成功缓存 {cached_count} 个项目"
            }
            
        except Exception as e:
            task_config["error_count"] += 1
            logger.error(f"预热任务 {task_name} 执行失败: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "cached_count": 0,
                "duration": time.time() - start_time
            }
    
    def get_warming_stats(self) -> Dict[str, Any]:
        """
        获取预热统计信息
        
        Returns:
            统计信息
        """
        return {
            "global_stats": self.warming_stats.copy(),
            "task_stats": {
                name: {
                    "last_executed": config["last_executed"],
                    "execution_count": config["execution_count"],
                    "success_count": config["success_count"],
                    "error_count": config["error_count"],
                    "success_rate": config["success_count"] / max(config["execution_count"], 1)
                }
                for name, config in self.warming_tasks.items()
            }
        }
    
    def schedule_warming(self, interval_minutes: int = 60):
        """
        定期执行缓存预热
        
        Args:
            interval_minutes: 预热间隔（分钟）
        """
        def _schedule_task():
            while True:
                try:
                    self.warm_cache()
                    time.sleep(interval_minutes * 60)
                except Exception as e:
                    logger.error(f"定期缓存预热失败: {e}")
                    time.sleep(60)  # 出错时等待1分钟后重试
        
        import threading
        thread = threading.Thread(target=_schedule_task, daemon=True)
        thread.start()
        logger.info(f"启动定期缓存预热，间隔 {interval_minutes} 分钟")

class BatchCacheOperator:
    """
    批量缓存操作器
    
    用于批量设置、获取、删除缓存
    """
    
    def __init__(self, cache_manager: CacheManager, batch_size: int = 100):
        self.cache_manager = cache_manager
        self.batch_size = batch_size
    
    def batch_set(self, items: List[Tuple[str, Any, Optional[int]]]) -> Dict[str, Any]:
        """
        批量设置缓存
        
        Args:
            items: 缓存项列表，每个项目是 (key, value, ttl) 的元组
            
        Returns:
            操作结果统计
        """
        start_time = time.time()
        successful = 0
        failed = 0
        
        # 分批处理
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            for key, value, ttl in batch:
                try:
                    if self.cache_manager.set(key, value, ttl):
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"批量设置缓存失败 {key}: {e}")
                    failed += 1
        
        return {
            "total": len(items),
            "successful": successful,
            "failed": failed,
            "duration": time.time() - start_time
        }
    
    def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        批量获取缓存
        
        Args:
            keys: 缓存键列表
            
        Returns:
            缓存值字典和统计信息
        """
        start_time = time.time()
        results = {}
        hits = 0
        misses = 0
        
        # 分批处理
        for i in range(0, len(keys), self.batch_size):
            batch = keys[i:i + self.batch_size]
            
            for key in batch:
                try:
                    value = self.cache_manager.get(key)
                    if value is not None:
                        results[key] = value
                        hits += 1
                    else:
                        misses += 1
                except Exception as e:
                    logger.error(f"批量获取缓存失败 {key}: {e}")
                    misses += 1
        
        return {
            "results": results,
            "stats": {
                "total": len(keys),
                "hits": hits,
                "misses": misses,
                "hit_rate": hits / len(keys) if keys else 0,
                "duration": time.time() - start_time
            }
        }
    
    def batch_delete(self, keys: List[str]) -> Dict[str, Any]:
        """
        批量删除缓存
        
        Args:
            keys: 要删除的缓存键列表
            
        Returns:
            操作结果统计
        """
        start_time = time.time()
        successful = 0
        failed = 0
        
        # 分批处理
        for i in range(0, len(keys), self.batch_size):
            batch = keys[i:i + self.batch_size]
            
            for key in batch:
                try:
                    if self.cache_manager.delete(key):
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"批量删除缓存失败 {key}: {e}")
                    failed += 1
        
        return {
            "total": len(keys),
            "successful": successful,
            "failed": failed,
            "duration": time.time() - start_time
        }
    
    def batch_refresh(self, 
                     keys: List[str], 
                     data_loader: Callable[[str], Any],
                     ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        批量刷新缓存
        
        Args:
            keys: 要刷新的缓存键列表
            data_loader: 数据加载函数，接收key参数返回新数据
            ttl: 新的过期时间
            
        Returns:
            操作结果统计
        """
        start_time = time.time()
        successful = 0
        failed = 0
        
        for key in keys:
            try:
                # 加载新数据
                new_data = data_loader(key)
                
                if new_data is not None:
                    # 设置新缓存
                    if self.cache_manager.set(key, new_data, ttl):
                        successful += 1
                    else:
                        failed += 1
                else:
                    # 删除过期缓存
                    self.cache_manager.delete(key)
                    successful += 1
                    
            except Exception as e:
                logger.error(f"批量刷新缓存失败 {key}: {e}")
                failed += 1
        
        return {
            "total": len(keys),
            "successful": successful,
            "failed": failed,
            "duration": time.time() - start_time
        }

class CacheHealthMonitor:
    """
    缓存健康监控器
    
    监控缓存系统的健康状态和性能指标
    """
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.health_history = []
        self.alert_thresholds = {
            "hit_rate_min": 0.7,  # 最低命中率
            "error_rate_max": 0.05,  # 最高错误率
            "response_time_max": 100,  # 最大响应时间（毫秒）
            "memory_usage_max": 0.8  # 最大内存使用率
        }
    
    def check_health(self) -> Dict[str, Any]:
        """
        检查缓存健康状态
        
        Returns:
            健康检查结果
        """
        start_time = time.time()
        
        # 获取缓存统计
        stats = self.cache_manager.get_stats()
        
        # 测试缓存响应时间
        test_key = f"health_check_{int(time.time())}"
        test_value = {"timestamp": time.time(), "test": True}
        
        set_start = time.time()
        set_success = self.cache_manager.set(test_key, test_value, 60)
        set_time = (time.time() - set_start) * 1000
        
        get_start = time.time()
        get_value = self.cache_manager.get(test_key)
        get_time = (time.time() - get_start) * 1000
        
        # 清理测试数据
        self.cache_manager.delete(test_key)
        
        # 计算健康指标
        hit_rate = stats.get("hit_rate", 0)
        error_rate = stats.get("errors", 0) / max(stats.get("total_requests", 1), 1)
        avg_response_time = (set_time + get_time) / 2
        
        # 判断健康状态
        health_issues = []
        
        if hit_rate < self.alert_thresholds["hit_rate_min"]:
            health_issues.append(f"命中率过低: {hit_rate:.2%}")
        
        if error_rate > self.alert_thresholds["error_rate_max"]:
            health_issues.append(f"错误率过高: {error_rate:.2%}")
        
        if avg_response_time > self.alert_thresholds["response_time_max"]:
            health_issues.append(f"响应时间过长: {avg_response_time:.2f}ms")
        
        if not set_success or get_value != test_value:
            health_issues.append("缓存读写测试失败")
        
        health_status = "healthy" if not health_issues else "unhealthy"
        
        health_result = {
            "status": health_status,
            "timestamp": datetime.now(),
            "metrics": {
                "hit_rate": hit_rate,
                "error_rate": error_rate,
                "avg_response_time_ms": avg_response_time,
                "set_time_ms": set_time,
                "get_time_ms": get_time,
                "cache_enabled": self.cache_manager.enabled
            },
            "issues": health_issues,
            "stats": stats,
            "check_duration": time.time() - start_time
        }
        
        # 记录健康历史
        self.health_history.append(health_result)
        
        # 保持最近100次检查记录
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return health_result
    
    def get_health_trend(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取健康趋势
        
        Args:
            hours: 查看最近多少小时的趋势
            
        Returns:
            健康趋势分析
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_checks = [
            check for check in self.health_history 
            if check["timestamp"] > cutoff_time
        ]
        
        if not recent_checks:
            return {"message": "没有足够的历史数据"}
        
        # 计算趋势指标
        hit_rates = [check["metrics"]["hit_rate"] for check in recent_checks]
        response_times = [check["metrics"]["avg_response_time_ms"] for check in recent_checks]
        error_rates = [check["metrics"]["error_rate"] for check in recent_checks]
        
        healthy_count = len([check for check in recent_checks if check["status"] == "healthy"])
        
        return {
            "period_hours": hours,
            "total_checks": len(recent_checks),
            "healthy_checks": healthy_count,
            "health_rate": healthy_count / len(recent_checks),
            "metrics_trend": {
                "hit_rate": {
                    "avg": sum(hit_rates) / len(hit_rates),
                    "min": min(hit_rates),
                    "max": max(hit_rates)
                },
                "response_time_ms": {
                    "avg": sum(response_times) / len(response_times),
                    "min": min(response_times),
                    "max": max(response_times)
                },
                "error_rate": {
                    "avg": sum(error_rates) / len(error_rates),
                    "min": min(error_rates),
                    "max": max(error_rates)
                }
            },
            "recent_issues": [
                {
                    "timestamp": check["timestamp"],
                    "issues": check["issues"]
                }
                for check in recent_checks[-10:] if check["issues"]
            ]
        }
    
    def set_alert_thresholds(self, thresholds: Dict[str, float]):
        """
        设置告警阈值
        
        Args:
            thresholds: 阈值配置
        """
        self.alert_thresholds.update(thresholds)
        logger.info(f"更新缓存健康监控阈值: {thresholds}")

# 全局缓存管理器实例
cache_manager = CacheManager()
cache_warmer = CacheWarmer(cache_manager)
batch_cache_operator = BatchCacheOperator(cache_manager)
cache_health_monitor = CacheHealthMonitor(cache_manager)

# 缓存装饰器
def cache_result(key_prefix: str = "", ttl: int = 3600, use_args: bool = True):
    """
    缓存结果装饰器
    
    Args:
        key_prefix: 缓存键前缀
        ttl: 过期时间
        use_args: 是否使用函数参数生成缓存键
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if use_args:
                import hashlib
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}{func.__name__}_{args_hash}"
            else:
                cache_key = f"{key_prefix}{func.__name__}"
            
            # 尝试从缓存获取
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

# 异步缓存装饰器
def async_cache_result(key_prefix: str = "", ttl: int = 3600, use_args: bool = True):
    """
    异步缓存结果装饰器
    
    Args:
        key_prefix: 缓存键前缀
        ttl: 过期时间
        use_args: 是否使用函数参数生成缓存键
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if use_args:
                import hashlib
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}{func.__name__}_{args_hash}"
            else:
                cache_key = f"{key_prefix}{func.__name__}"
            
            # 尝试从缓存获取
            cached_result = await cache_manager.async_get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            await cache_manager.async_set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator