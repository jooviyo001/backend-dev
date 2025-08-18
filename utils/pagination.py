"""分页工具模块

提供数据库查询分页功能和性能优化
"""

from typing import Tuple, List, Any, Optional
from sqlalchemy.orm import Query
from sqlalchemy import func, text
from math import ceil


def paginate_query(query: Query, page: int = 1, size: int = 10) -> Tuple[int, List[Any]]:
    """
    对SQLAlchemy查询进行分页处理
    
    Args:
        query: SQLAlchemy查询对象
        page: 页码，从1开始
        size: 每页大小
        
    Returns:
        Tuple[总数, 当前页数据列表]
    """
    # 参数验证
    if page < 1:
        page = 1
    if size < 1:
        size = 10
    if size > 100:
        size = 100
    
    # 计算偏移量
    offset = (page - 1) * size
    
    # 获取总数（优化：使用子查询避免复杂的JOIN影响COUNT性能）
    try:
        # 尝试使用优化的计数查询
        count_query = query.statement.with_only_columns([func.count()]).order_by(None)
        total = query.session.execute(count_query).scalar()
    except Exception:
        # 回退到标准计数方法
        total = query.count()
    
    # 获取分页数据
    items = query.offset(offset).limit(size).all()
    
    return total, items


def paginate_query_optimized(query: Query, page: int = 1, size: int = 10, 
                            use_cursor: bool = False, cursor_column: str = 'id') -> Tuple[int, List[Any]]:
    """
    优化的分页查询，支持游标分页
    
    Args:
        query: SQLAlchemy查询对象
        page: 页码，从1开始
        size: 每页大小
        use_cursor: 是否使用游标分页（适合大数据量）
        cursor_column: 游标列名
        
    Returns:
        Tuple[总数, 当前页数据列表]
    """
    # 参数验证
    if page < 1:
        page = 1
    if size < 1:
        size = 10
    if size > 100:
        size = 100
    
    if use_cursor and page > 1:
        # 游标分页：适合大数据量，性能更好但不支持跳页
        # 这里简化实现，实际使用时需要传入cursor值
        offset = (page - 1) * size
        items = query.offset(offset).limit(size).all()
        # 对于游标分页，通常不需要精确的总数
        total = -1  # 表示未知总数
    else:
        # 标准分页
        offset = (page - 1) * size
        
        # 优化的计数查询
        try:
            # 移除ORDER BY子句以提高COUNT性能
            count_query = query.statement.with_only_columns([func.count()]).order_by(None)
            total = query.session.execute(count_query).scalar()
        except Exception:
            total = query.count()
        
        # 获取分页数据
        items = query.offset(offset).limit(size).all()
    
    return total, items


def calculate_pagination_info(total: int, page: int, size: int) -> dict:
    """
    计算分页信息
    
    Args:
        total: 总记录数
        page: 当前页码
        size: 每页大小
        
    Returns:
        包含分页信息的字典
    """
    if total <= 0:
        return {
            'total': 0,
            'page': 1,
            'size': size,
            'totalPages': 0,
            'has_prev': False,
            'has_next': False,
            'prev_page': None,
            'next_page': None
        }
    
    totalPages = ceil(total / size)
    has_prev = page > 1
    has_next = page < totalPages
    
    return {
        'total': total,
        'page': page,
        'size': size,
        'totalPages': totalPages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': page - 1 if has_prev else None,
        'next_page': page + 1 if has_next else None
    }


class PaginationHelper:
    """
    分页助手类，提供更高级的分页功能
    """
    
    @staticmethod
    def paginate_with_cache(query: Query, page: int, size: int, 
                          cache_key: Optional[str] = None, 
                          cache_ttl: int = 300) -> Tuple[int, List[Any]]:
        """
        带缓存的分页查询
        
        Args:
            query: SQLAlchemy查询对象
            page: 页码
            size: 每页大小
            cache_key: 缓存键
            cache_ttl: 缓存过期时间（秒）
            
        Returns:
            Tuple[总数, 当前页数据列表]
        """
        # 这里可以集成缓存逻辑
        # 暂时直接调用标准分页
        return paginate_query(query, page, size)
    
    @staticmethod
    def get_page_range(current_page: int, total_pages: int, window: int = 5) -> List[int]:
        """
        获取分页导航的页码范围
        
        Args:
            current_page: 当前页码
            total_pages: 总页数
            window: 显示窗口大小
            
        Returns:
            页码列表
        """
        if total_pages <= window:
            return list(range(1, total_pages + 1))
        
        # 计算窗口的开始和结束
        half_window = window // 2
        start = max(1, current_page - half_window)
        end = min(total_pages, start + window - 1)
        
        # 调整开始位置以确保窗口大小
        if end - start + 1 < window:
            start = max(1, end - window + 1)
        
        return list(range(start, end + 1))