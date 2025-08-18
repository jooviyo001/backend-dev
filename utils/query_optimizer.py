"""查询优化工具模块

提供数据库查询性能优化功能
"""

import time
import hashlib
import json
from typing import Any, Optional, Callable, Dict, List, Tuple
from functools import wraps
from sqlalchemy.orm import Query, Session
from sqlalchemy import text, event
from datetime import datetime, timedelta
import logging

# 配置日志
logger = logging.getLogger(__name__)


class QueryPerformanceMonitor:
    """
    查询性能监控器
    """
    
    def __init__(self):
        self.slow_queries = []
        self.query_stats = {}
        self.slow_query_threshold = 1.0  # 慢查询阈值（秒）
    
    def log_query(self, sql: str, params: Any, duration: float):
        """
        记录查询日志
        """
        query_hash = hashlib.md5(sql.encode()).hexdigest()[:8]
        
        # 更新统计信息
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = {
                'sql': sql[:200] + '...' if len(sql) > 200 else sql,
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0,
                'min_time': float('inf')
            }
        
        stats = self.query_stats[query_hash]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['avg_time'] = stats['total_time'] / stats['count']
        stats['max_time'] = max(stats['max_time'], duration)
        stats['min_time'] = min(stats['min_time'], duration)
        
        # 记录慢查询
        if duration > self.slow_query_threshold:
            self.slow_queries.append({
                'sql': sql,
                'params': str(params)[:500],
                'duration': duration,
                'timestamp': datetime.now()
            })
            logger.warning(f"慢查询检测: {duration:.3f}s - {sql[:100]}...")
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """
        获取慢查询列表
        """
        return sorted(self.slow_queries, key=lambda x: x['duration'], reverse=True)[:limit]
    
    def get_query_stats(self) -> Dict:
        """
        获取查询统计信息
        """
        return self.query_stats
    
    def reset_stats(self):
        """
        重置统计信息
        """
        self.slow_queries.clear()
        self.query_stats.clear()


# 全局性能监控器实例
performance_monitor = QueryPerformanceMonitor()


def monitor_query_performance(func: Callable) -> Callable:
    """
    查询性能监控装饰器
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # 记录查询性能
            func_name = f"{func.__module__}.{func.__name__}"
            performance_monitor.log_query(func_name, str(kwargs), duration)
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"查询执行失败: {func.__name__} - {duration:.3f}s - {str(e)}")
            raise
    
    return wrapper


def cache_query_result(cache_key_prefix: str, ttl: int = 300):
    """
    查询结果缓存装饰器
    
    Args:
        cache_key_prefix: 缓存键前缀
        ttl: 缓存过期时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{cache_key_prefix}:{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            # 尝试从缓存获取
            try:
                from utils.cache_manager import CacheManager
                cache_manager = CacheManager()
                
                if cache_manager.enabled:
                    cached_result = cache_manager.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"缓存命中: {cache_key}")
                        return cached_result
            except Exception as e:
                logger.warning(f"缓存获取失败: {e}")
            
            # 执行查询
            result = func(*args, **kwargs)
            
            # 存储到缓存
            try:
                if 'cache_manager' in locals() and cache_manager.enabled:
                    cache_manager.set(cache_key, result, ttl)
                    logger.debug(f"结果已缓存: {cache_key}")
            except Exception as e:
                logger.warning(f"缓存存储失败: {e}")
            
            return result
        
        return wrapper
    return decorator


class QueryOptimizer:
    """
    查询优化器
    """
    
    @staticmethod
    def optimize_count_query(query: Query) -> int:
        """
        优化COUNT查询
        
        对于复杂的JOIN查询，使用子查询来优化COUNT性能
        """
        try:
            # 尝试使用优化的计数查询
            from sqlalchemy import func
            count_query = query.statement.with_only_columns([func.count()]).order_by(None)
            return query.session.execute(count_query).scalar()
        except Exception:
            # 回退到标准计数方法
            return query.count()
    
    @staticmethod
    def add_query_hints(query: Query, hints: List[str]) -> Query:
        """
        添加查询提示
        
        Args:
            query: SQLAlchemy查询对象
            hints: 查询提示列表
        """
        for hint in hints:
            query = query.execution_options(compiled_cache={})
        return query
    
    @staticmethod
    def optimize_join_query(query: Query, eager_load_relations: List[str] = None) -> Query:
        """
        优化JOIN查询
        
        Args:
            query: SQLAlchemy查询对象
            eager_load_relations: 需要预加载的关联关系
        """
        if eager_load_relations:
            from sqlalchemy.orm import joinedload
            for relation in eager_load_relations:
                query = query.options(joinedload(relation))
        
        return query
    
    @staticmethod
    def build_search_query(base_query: Query, search_fields: List[str], 
                          keyword: str, use_fulltext: bool = False) -> Query:
        """
        构建搜索查询
        
        Args:
            base_query: 基础查询
            search_fields: 搜索字段列表
            keyword: 搜索关键词
            use_fulltext: 是否使用全文搜索
        """
        if not keyword or not search_fields:
            return base_query
        
        from sqlalchemy import or_
        
        if use_fulltext:
            # 全文搜索（需要数据库支持）
            search_conditions = []
            for field in search_fields:
                # 这里可以根据数据库类型使用不同的全文搜索语法
                search_conditions.append(field.match(keyword))
            
            if search_conditions:
                base_query = base_query.filter(or_(*search_conditions))
        else:
            # 普通LIKE搜索
            search_conditions = []
            for field in search_fields:
                search_conditions.append(field.contains(keyword))
            
            if search_conditions:
                base_query = base_query.filter(or_(*search_conditions))
        
        return base_query


class BatchQueryProcessor:
    """
    批量查询处理器
    """
    
    def __init__(self, session: Session, batch_size: int = 1000):
        self.session = session
        self.batch_size = batch_size
    
    def batch_insert(self, model_class, data_list: List[Dict]) -> int:
        """
        批量插入数据
        
        Args:
            model_class: 模型类
            data_list: 数据列表
            
        Returns:
            插入的记录数
        """
        if not data_list:
            return 0
        
        inserted_count = 0
        
        for i in range(0, len(data_list), self.batch_size):
            batch = data_list[i:i + self.batch_size]
            
            try:
                # 使用bulk_insert_mappings进行批量插入
                self.session.bulk_insert_mappings(model_class, batch)
                self.session.commit()
                inserted_count += len(batch)
                
                logger.info(f"批量插入 {len(batch)} 条记录到 {model_class.__name__}")
                
            except Exception as e:
                self.session.rollback()
                logger.error(f"批量插入失败: {e}")
                raise
        
        return inserted_count
    
    def batch_update(self, model_class, data_list: List[Dict], 
                    key_field: str = 'id') -> int:
        """
        批量更新数据
        
        Args:
            model_class: 模型类
            data_list: 数据列表
            key_field: 主键字段名
            
        Returns:
            更新的记录数
        """
        if not data_list:
            return 0
        
        updated_count = 0
        
        for i in range(0, len(data_list), self.batch_size):
            batch = data_list[i:i + self.batch_size]
            
            try:
                # 使用bulk_update_mappings进行批量更新
                self.session.bulk_update_mappings(model_class, batch)
                self.session.commit()
                updated_count += len(batch)
                
                logger.info(f"批量更新 {len(batch)} 条记录到 {model_class.__name__}")
                
            except Exception as e:
                self.session.rollback()
                logger.error(f"批量更新失败: {e}")
                raise
        
        return updated_count


def setup_query_monitoring(engine):
    """
    设置查询监控
    
    Args:
        engine: SQLAlchemy引擎
    """
    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = time.time()
    
    @event.listens_for(engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - context._query_start_time
        performance_monitor.log_query(statement, parameters, total)


# 查询优化建议
QUERY_OPTIMIZATION_TIPS = {
    'use_indexes': '确保查询字段有适当的索引',
    'limit_results': '使用LIMIT限制结果集大小',
    'avoid_n_plus_1': '使用joinedload避免N+1查询问题',
    'optimize_joins': '优化JOIN查询，避免不必要的关联',
    'use_pagination': '对大结果集使用分页',
    'cache_results': '对频繁查询的结果进行缓存',
    'avoid_select_star': '避免使用SELECT *，只查询需要的字段',
    'use_bulk_operations': '对批量操作使用bulk_insert/bulk_update',
}