"""
SQLAlchemy雪花算法ID字段类型
"""

from sqlalchemy import TypeDecorator, BigInteger
from sqlalchemy.sql import func
from .snowflake import generate_snowflake_id


class SnowflakeId(TypeDecorator):
    """雪花算法ID字段类型"""
    
    impl = BigInteger
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """处理绑定参数"""
        if value is None:
            return generate_snowflake_id()
        return value
    
    def process_result_value(self, value, dialect):
        """处理结果值"""
        return value


def snowflake_id_column(**kwargs):
    """
    创建雪花算法ID列的便捷函数
    
    Args:
        **kwargs: 传递给Column的其他参数
        
    Returns:
        Column: 配置好的雪花算法ID列
    """
    from sqlalchemy import Column
    
    # 设置默认参数
    kwargs.setdefault('primary_key', True)
    kwargs.setdefault('index', True)
    kwargs.setdefault('default', generate_snowflake_id)
    
    return Column(SnowflakeId, **kwargs)