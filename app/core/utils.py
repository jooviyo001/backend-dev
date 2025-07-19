import hashlib
import secrets
import string
import uuid
import re
import json
import base64
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union, Tuple, Type
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import asyncio
import aiofiles
import aiohttp
from PIL import Image
import io
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from app.core.config import settings

# 字符串工具函数
def generate_random_string(length: int = 32, include_symbols: bool = False) -> str:
    """生成随机字符串"""
    characters = string.ascii_letters + string.digits
    if include_symbols:
        characters += "!@#$%^&*"
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_uuid() -> str:
    """生成UUID"""
    return str(uuid.uuid4())

def generate_short_id(length: int = 8) -> str:
    """生成短ID"""
    characters = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def slugify(text: str, max_length: int = 50) -> str:
    """将文本转换为URL友好的slug"""
    # 转换为小写
    text = text.lower()
    
    # 替换空格和特殊字符为连字符
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', text)
    
    # 移除开头和结尾的连字符
    text = text.strip('-')
    
    # 限制长度
    if len(text) > max_length:
        text = text[:max_length].rstrip('-')
    
    return text

def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断字符串"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """掩码敏感数据"""
    if len(data) <= visible_chars * 2:
        return mask_char * len(data)
    
    start = data[:visible_chars]
    end = data[-visible_chars:]
    middle = mask_char * (len(data) - visible_chars * 2)
    
    return start + middle + end

# 验证工具函数
def is_valid_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone: str) -> bool:
    """验证手机号格式（中国）"""
    pattern = r'^1[3-9]\d{9}$'
    return re.match(pattern, phone) is not None

def is_valid_url(url: str) -> bool:
    """验证URL格式"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def is_valid_uuid(uuid_string: str) -> bool:
    """验证UUID格式"""
    try:
        uuid.UUID(uuid_string)
        return True
    except ValueError:
        return False

def validate_password_strength(password: str) -> Dict[str, Any]:
    """验证密码强度"""
    result = {
        "is_valid": True,
        "score": 0,
        "issues": []
    }
    
    # 长度检查
    if len(password) < 8:
        result["issues"].append("Password must be at least 8 characters long")
        result["is_valid"] = False
    else:
        result["score"] += 1
    
    # 包含小写字母
    if not re.search(r'[a-z]', password):
        result["issues"].append("Password must contain lowercase letters")
        result["is_valid"] = False
    else:
        result["score"] += 1
    
    # 包含大写字母
    if not re.search(r'[A-Z]', password):
        result["issues"].append("Password must contain uppercase letters")
        result["is_valid"] = False
    else:
        result["score"] += 1
    
    # 包含数字
    if not re.search(r'\d', password):
        result["issues"].append("Password must contain numbers")
        result["is_valid"] = False
    else:
        result["score"] += 1
    
    # 包含特殊字符
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        result["issues"].append("Password must contain special characters")
        result["is_valid"] = False
    else:
        result["score"] += 1
    
    return result

# 时间工具函数
def get_current_timestamp() -> int:
    """获取当前时间戳（秒）"""
    return int(datetime.now().timestamp())

def get_current_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(datetime.now().timestamp() * 1000)

def timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """时间戳转datetime"""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)

def datetime_to_timestamp(dt: datetime) -> int:
    """datetime转时间戳"""
    return int(dt.timestamp())

def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化datetime"""
    return dt.strftime(format_str)

def parse_datetime(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """解析datetime字符串"""
    return datetime.strptime(date_str, format_str)

def get_date_range(days: int = 7) -> Tuple[datetime, datetime]:
    """获取日期范围"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date

def is_business_day(date: datetime) -> bool:
    """判断是否为工作日"""
    return date.weekday() < 5  # 0-4 为周一到周五

def get_next_business_day(date: datetime) -> datetime:
    """获取下一个工作日"""
    next_day = date + timedelta(days=1)
    while not is_business_day(next_day):
        next_day += timedelta(days=1)
    return next_day

def calculate_business_days(start_date: datetime, end_date: datetime) -> int:
    """计算工作日天数"""
    days = 0
    current_date = start_date
    
    while current_date <= end_date:
        if is_business_day(current_date):
            days += 1
        current_date += timedelta(days=1)
    
    return days

# 文件工具函数
def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return Path(filename).suffix.lower()

def get_file_mime_type(filename: str) -> str:
    """获取文件MIME类型"""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"

def is_image_file(filename: str) -> bool:
    """判断是否为图片文件"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    return get_file_extension(filename) in image_extensions

def is_document_file(filename: str) -> bool:
    """判断是否为文档文件"""
    doc_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'}
    return get_file_extension(filename) in doc_extensions

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    # 移除或替换不安全的字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 移除控制字符
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # 限制长度
    name, ext = Path(filename).stem, Path(filename).suffix
    if len(name) > 200:
        name = name[:200]
    
    return name + ext

async def save_uploaded_file(file_content: bytes, filename: str, upload_dir: str) -> str:
    """保存上传的文件"""
    # 创建上传目录
    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一文件名
    file_ext = get_file_extension(filename)
    unique_filename = f"{generate_uuid()}{file_ext}"
    file_path = upload_path / unique_filename
    
    # 保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(file_content)
    
    return str(file_path)

# 图片处理工具函数
def resize_image(image_data: bytes, max_width: int = 800, max_height: int = 600, quality: int = 85) -> bytes:
    """调整图片大小"""
    try:
        # 打开图片
        image = Image.open(io.BytesIO(image_data))
        
        # 计算新尺寸
        width, height = image.size
        ratio = min(max_width / width, max_height / height)
        
        if ratio < 1:
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 保存到字节流
        output = io.BytesIO()
        image_format = image.format or 'JPEG'
        
        if image_format == 'JPEG':
            image.save(output, format=image_format, quality=quality, optimize=True)
        else:
            image.save(output, format=image_format, optimize=True)
        
        return output.getvalue()
    
    except Exception:
        # 如果处理失败，返回原始数据
        return image_data

def create_thumbnail(image_data: bytes, size: Tuple[int, int] = (150, 150)) -> bytes:
    """创建缩略图"""
    try:
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        image_format = image.format or 'JPEG'
        
        if image_format == 'JPEG':
            image.save(output, format=image_format, quality=85, optimize=True)
        else:
            image.save(output, format=image_format, optimize=True)
        
        return output.getvalue()
    
    except Exception:
        return image_data

# 数据处理工具函数
def deep_merge_dict(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并字典"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result

def flatten_dict(data: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """扁平化字典"""
    items = []
    
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    
    return dict(items)

def remove_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """移除字典中的None值"""
    return {k: v for k, v in data.items() if v is not None}

def convert_to_dict(obj: Any, exclude_none: bool = True) -> Dict[str, Any]:
    """将对象转换为字典"""
    if isinstance(obj, BaseModel):
        data = obj.dict()
    elif hasattr(obj, '__dict__'):
        data = obj.__dict__.copy()
    else:
        return obj
    
    if exclude_none:
        data = remove_none_values(data)
    
    return data

def paginate_list(items: List[Any], page: int = 1, size: int = 20) -> Dict[str, Any]:
    """对列表进行分页"""
    total = len(items)
    start = (page - 1) * size
    end = start + size
    
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }

# 加密工具函数
def hash_string(text: str, algorithm: str = 'sha256') -> str:
    """哈希字符串"""
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode('utf-8'))
    return hash_obj.hexdigest()

def encode_base64(data: Union[str, bytes]) -> str:
    """Base64编码"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.b64encode(data).decode('utf-8')

def decode_base64(encoded_data: str) -> bytes:
    """Base64解码"""
    return base64.b64decode(encoded_data)

# 网络工具函数
async def make_http_request(
    url: str,
    method: str = 'GET',
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """发起HTTP请求"""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.request(method, url, headers=headers, json=data) as response:
            return {
                "status_code": response.status,
                "headers": dict(response.headers),
                "data": await response.json() if response.content_type == 'application/json' else await response.text()
            }

def extract_domain(url: str) -> str:
    """提取URL的域名"""
    parsed = urlparse(url)
    return parsed.netloc

def build_query_string(params: Dict[str, Any]) -> str:
    """构建查询字符串"""
    from urllib.parse import urlencode
    return urlencode(params)

# 数据库工具函数
def execute_raw_sql(db: Session, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """执行原始SQL查询"""
    result = db.execute(text(sql), params or {})
    return [dict(row) for row in result.fetchall()]

def bulk_insert_or_update(db: Session, model: Type, data: List[Dict[str, Any]], update_on_conflict: bool = True):
    """批量插入或更新数据"""
    # 这里需要根据具体的数据库实现
    # SQLAlchemy的bulk操作
    if update_on_conflict:
        # 使用upsert逻辑
        pass
    else:
        db.bulk_insert_mappings(model, data)
    
    db.commit()

# 缓存工具函数
def generate_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_parts = []
    
    # 添加位置参数
    for arg in args:
        key_parts.append(str(arg))
    
    # 添加关键字参数
    for key, value in sorted(kwargs.items()):
        key_parts.append(f"{key}:{value}")
    
    # 生成哈希
    key_string = ":".join(key_parts)
    return hash_string(key_string, 'md5')

# 配置工具函数
def load_config_from_env(prefix: str = "APP_") -> Dict[str, str]:
    """从环境变量加载配置"""
    import os
    config = {}
    
    for key, value in os.environ.items():
        if key.startswith(prefix):
            config_key = key[len(prefix):].lower()
            config[config_key] = value
    
    return config

def parse_config_value(value: str) -> Any:
    """解析配置值"""
    # 尝试解析为JSON
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        pass
    
    # 尝试解析为布尔值
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    
    # 尝试解析为数字
    try:
        if '.' in value:
            return float(value)
        else:
            return int(value)
    except ValueError:
        pass
    
    # 返回字符串
    return value

# 日志工具函数
def format_log_message(message: str, **kwargs) -> str:
    """格式化日志消息"""
    if kwargs:
        context = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{message} [{context}]"
    return message

def log_execution_time(func_name: str, start_time: float, end_time: float, threshold: float = 1.0):
    """记录执行时间"""
    execution_time = end_time - start_time
    
    if execution_time > threshold:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Slow execution: {func_name} took {execution_time:.3f}s")

# 异步工具函数
async def run_in_threadpool(func, *args, **kwargs):
    """在线程池中运行同步函数"""
    import asyncio
    import concurrent.futures
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, func, *args, **kwargs)

async def gather_with_concurrency(n: int, *tasks):
    """限制并发数的gather"""
    semaphore = asyncio.Semaphore(n)
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*(sem_task(task) for task in tasks))

# 数学工具函数
def calculate_percentage(part: Union[int, float], total: Union[int, float]) -> float:
    """计算百分比"""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)

def round_decimal(value: Union[int, float, Decimal], places: int = 2) -> Decimal:
    """四舍五入到指定小数位"""
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'))
    return Decimal(str(value)).quantize(Decimal('0.01'))

def clamp(value: Union[int, float], min_value: Union[int, float], max_value: Union[int, float]) -> Union[int, float]:
    """将值限制在指定范围内"""
    return max(min_value, min(value, max_value))

# 文本处理工具函数
def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """提取关键词（简单实现）"""
    # 移除标点符号和特殊字符
    cleaned_text = re.sub(r'[^\w\s]', '', text.lower())
    
    # 分割单词
    words = cleaned_text.split()
    
    # 移除常见停用词（简化版）
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    # 统计词频
    from collections import Counter
    word_counts = Counter(keywords)
    
    # 返回最常见的关键词
    return [word for word, count in word_counts.most_common(max_keywords)]

def highlight_text(text: str, keywords: List[str], highlight_tag: str = "<mark>") -> str:
    """高亮文本中的关键词"""
    close_tag = highlight_tag.replace('<', '</')
    
    for keyword in keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(f"{highlight_tag}{keyword}{close_tag}", text)
    
    return text

# 性能监控工具函数
class Timer:
    """计时器上下文管理器"""
    
    def __init__(self, name: str = "Timer"):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        print(f"{self.name}: {duration:.3f}s")
    
    @property
    def elapsed(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

# 重试装饰器
def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """重试装饰器"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay * (backoff ** attempt))
                    else:
                        raise last_exception
        
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        import time
                        time.sleep(delay * (backoff ** attempt))
                    else:
                        raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# 单例装饰器
def singleton(cls):
    """单例装饰器"""
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance