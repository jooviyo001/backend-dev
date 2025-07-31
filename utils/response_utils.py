from datetime import datetime
from typing import Any, Optional, List, Dict, Union
from fastapi.responses import JSONResponse
from math import ceil
from datetime import datetime
from .status_codes import SUCCESS, get_message

def format_timestamp(dt: datetime = None) -> str:
    """
    格式化时间戳为标准格式
    
    参数:
        dt: datetime对象，如果为None则使用当前时间
    
    返回:
        格式化后的时间字符串，格式为 "YYYY-MM-DD HH:MM:SS"
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# 定义ID前缀映射
ID_PREFIX_MAP = {
    "users": "USER",
    "projects": "PROJ",
    "tasks": "TASK",
    "organizations": "ORG",
    "task_attachments": "ATT",
    "task_comments": "COMM",
    # 可以根据需要添加其他模型的映射
}

def _add_id_prefix(data: Any) -> Any:
    """
    处理响应数据（已移除ID前缀添加逻辑，直接返回原始雪花ID）
    """
    if isinstance(data, dict):
        # 递归处理字典中的值
        for key, value in data.items():
            data[key] = _add_id_prefix(value)
    elif isinstance(data, list):
        # 递归处理列表中的每个元素
        data = [_add_id_prefix(item) for item in data]
    
    return data


def standard_response(data: Any = None, code: str = SUCCESS, message: Optional[str] = None, status_code: int = 200):
    """
    生成标准响应格式
    
    参数:
        data: 响应数据
        code: 业务状态码
        message: 响应消息，如果为None则使用状态码对应的默认消息
        status_code: HTTP状态码
    
    返回:
        标准格式的响应字典
    """
    if message is None:
        message = get_message(code)
    
    processed_data = _add_id_prefix(data)
    
    return {
        "code": code,
        "message": message,
        "data": processed_data,
        "timestamp": format_timestamp()
    }

def success_response(data: Any = None, message: str = None, code: str = SUCCESS):
    """
    生成成功响应
    
    参数:
        data: 响应数据
        message: 响应消息
        code: 业务状态码
    
    返回:
        标准格式的成功响应
    """
    return standard_response(data=data, code=code, message=message)

def error_response(code: str, message: Optional[str] = None, data: Any = None, status_code: int = 400):
    """
    生成错误响应
    
    参数:
        code: 业务状态码
        message: 错误消息
        data: 错误详情数据
        status_code: HTTP状态码
    
    返回:
        标准格式的错误响应JSONResponse
    """
    return JSONResponse(
        status_code=status_code,
        content=standard_response(data=data, code=code, message=message)
    )

def list_response(items: List[Any], total: int = None, page: int = 1, size: int = 10, message: str = None, code: str = SUCCESS):
    """
    生成列表数据的标准响应
    
    参数:
        items: 列表数据项
        total: 总记录数，如果为None则使用items的长度
        page: 当前页码
        size: 每页大小
        message: 响应消息
        code: 业务状态码
    
    返回:
        包含分页信息的标准格式响应
    """
    if total is None:
        total = len(items)
    
    data = {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": ceil(total / size) if size > 0 else 0
    }
    
    return standard_response(data=data, code=code, message=message)

def paginate_query(query, page: int = 1, size: int = 10):
    """
    对查询进行分页处理
    
    参数:
        query: SQLAlchemy查询对象
        page: 当前页码
        size: 每页大小
    
    返回:
        (总记录数, 分页后的记录列表)
    """
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    
    return total, items