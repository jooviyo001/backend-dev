"""数据安全和权限验证工具模块

提供数据脱敏、权限检查、安全审计、输入过滤等安全功能
"""
import re
import hashlib
import secrets
import base64
import json
from typing import Any, Dict, List, Optional, Union, Set
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.exceptions import AuthException, PermissionException, ValidationException
from utils.logging_middleware import logger


class SensitiveDataType(Enum):
    """敏感数据类型"""
    PHONE = "phone"
    EMAIL = "email"
    ID_CARD = "id_card"
    BANK_CARD = "bank_card"
    PASSWORD = "password"
    ADDRESS = "address"
    NAME = "name"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


class PermissionLevel(Enum):
    """权限级别"""
    NONE = 0
    READ = 1
    WRITE = 2
    DELETE = 3
    ADMIN = 4
    SUPER_ADMIN = 5


class DataMasker:
    """数据脱敏器"""
    
    def __init__(self):
        self.masking_rules = {
            SensitiveDataType.PHONE: self._mask_phone,
            SensitiveDataType.EMAIL: self._mask_email,
            SensitiveDataType.ID_CARD: self._mask_id_card,
            SensitiveDataType.BANK_CARD: self._mask_bank_card,
            SensitiveDataType.PASSWORD: self._mask_password,
            SensitiveDataType.ADDRESS: self._mask_address,
            SensitiveDataType.NAME: self._mask_name,
            SensitiveDataType.IP_ADDRESS: self._mask_ip_address
        }
    
    def mask_data(self, data: str, data_type: SensitiveDataType, 
                  mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏数据"""
        if not data or not isinstance(data, str):
            return data
        
        masking_func = self.masking_rules.get(data_type)
        if masking_func:
            return masking_func(data, mask_char, preserve_length)
        else:
            return self._mask_custom(data, mask_char, preserve_length)
    
    def _mask_phone(self, phone: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏手机号"""
        if len(phone) == 11:
            return phone[:3] + mask_char * 4 + phone[7:]
        elif len(phone) >= 7:
            return phone[:3] + mask_char * (len(phone) - 6) + phone[-3:]
        else:
            return mask_char * len(phone) if preserve_length else mask_char * 3
    
    def _mask_email(self, email: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏邮箱"""
        if '@' in email:
            local, domain = email.split('@', 1)
            if len(local) <= 2:
                masked_local = mask_char * len(local)
            else:
                masked_local = local[0] + mask_char * (len(local) - 2) + local[-1]
            return f"{masked_local}@{domain}"
        else:
            return mask_char * len(email) if preserve_length else mask_char * 6
    
    def _mask_id_card(self, id_card: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏身份证号"""
        if len(id_card) == 18:
            return id_card[:6] + mask_char * 8 + id_card[14:]
        elif len(id_card) == 15:
            return id_card[:6] + mask_char * 6 + id_card[12:]
        else:
            return mask_char * len(id_card) if preserve_length else mask_char * 6
    
    def _mask_bank_card(self, bank_card: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏银行卡号"""
        if len(bank_card) >= 8:
            return bank_card[:4] + mask_char * (len(bank_card) - 8) + bank_card[-4:]
        else:
            return mask_char * len(bank_card) if preserve_length else mask_char * 4
    
    def _mask_password(self, password: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏密码"""
        return mask_char * len(password) if preserve_length else mask_char * 8
    
    def _mask_address(self, address: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏地址"""
        if len(address) <= 6:
            return mask_char * len(address) if preserve_length else mask_char * 4
        else:
            return address[:3] + mask_char * (len(address) - 6) + address[-3:]
    
    def _mask_name(self, name: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏姓名"""
        if len(name) <= 1:
            return name
        elif len(name) == 2:
            return name[0] + mask_char
        else:
            return name[0] + mask_char * (len(name) - 2) + name[-1]
    
    def _mask_ip_address(self, ip: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """脱敏IP地址"""
        if '.' in ip:  # IPv4
            parts = ip.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{mask_char * len(parts[2])}.{mask_char * len(parts[3])}"
        elif ':' in ip:  # IPv6
            parts = ip.split(':')
            if len(parts) >= 4:
                return ':'.join(parts[:2] + [mask_char * len(part) for part in parts[2:]])
        
        return mask_char * len(ip) if preserve_length else mask_char * 8
    
    def _mask_custom(self, data: str, mask_char: str = '*', preserve_length: bool = True) -> str:
        """自定义脱敏"""
        if len(data) <= 2:
            return mask_char * len(data) if preserve_length else mask_char * 2
        else:
            return data[0] + mask_char * (len(data) - 2) + data[-1]
    
    def mask_dict(self, data: Dict[str, Any], field_rules: Dict[str, SensitiveDataType]) -> Dict[str, Any]:
        """脱敏字典数据"""
        masked_data = data.copy()
        
        for field, data_type in field_rules.items():
            if field in masked_data and masked_data[field]:
                masked_data[field] = self.mask_data(str(masked_data[field]), data_type)
        
        return masked_data
    
    def mask_list(self, data_list: List[Dict[str, Any]], 
                  field_rules: Dict[str, SensitiveDataType]) -> List[Dict[str, Any]]:
        """脱敏列表数据"""
        return [self.mask_dict(item, field_rules) for item in data_list]


class DataEncryption:
    """数据加密器"""
    
    def __init__(self, password: str = None):
        if password:
            self.key = self._derive_key(password)
            self.cipher = Fernet(self.key)
        else:
            self.key = Fernet.generate_key()
            self.cipher = Fernet(self.key)
    
    def _derive_key(self, password: str, salt: bytes = None) -> bytes:
        """从密码派生密钥"""
        if salt is None:
            salt = b'stable_salt_for_consistency'  # 在生产环境中应该使用随机盐
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """加密数据"""
        if not data:
            return data
        
        encrypted_data = self.cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"数据解密失败: {str(e)}")
            raise ValidationException("数据解密失败")
    
    def encrypt_dict(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """加密字典中的指定字段"""
        encrypted_data = data.copy()
        
        for field in fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt(str(encrypted_data[field]))
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """解密字典中的指定字段"""
        decrypted_data = data.copy()
        
        for field in fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt(str(decrypted_data[field]))
        
        return decrypted_data


class InputSanitizer:
    """输入过滤器"""
    
    def __init__(self):
        # SQL注入关键词
        self.sql_keywords = [
            'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter',
            'exec', 'execute', 'union', 'script', 'javascript', 'vbscript',
            'onload', 'onerror', 'onclick', 'onmouseover', 'onfocus', 'onblur'
        ]
        
        # XSS攻击模式
        self.xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            r'onclick\s*=',
            r'onmouseover\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>'
        ]
        
        # 路径遍历模式
        self.path_traversal_patterns = [
            r'\.\./+',
            r'\\\.\.\\+',
            r'/etc/passwd',
            r'/etc/shadow',
            r'c:\\windows\\system32'
        ]
    
    def sanitize_sql(self, input_str: str) -> str:
        """过滤SQL注入"""
        if not input_str:
            return input_str
        
        # 转换为小写进行检查
        lower_input = input_str.lower()
        
        # 检查SQL关键词
        for keyword in self.sql_keywords:
            if keyword in lower_input:
                logger.warning(f"检测到潜在SQL注入: {input_str}")
                # 可以选择抛出异常或者清理输入
                input_str = input_str.replace(keyword, f"[{keyword}]")
        
        return input_str
    
    def sanitize_xss(self, input_str: str) -> str:
        """过滤XSS攻击"""
        if not input_str:
            return input_str
        
        sanitized = input_str
        
        # 移除危险的HTML标签和JavaScript
        for pattern in self.xss_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # HTML实体编码
        sanitized = sanitized.replace('<', '&lt;')
        sanitized = sanitized.replace('>', '&gt;')
        sanitized = sanitized.replace('"', '&quot;')
        sanitized = sanitized.replace("'", '&#x27;')
        sanitized = sanitized.replace('&', '&amp;')
        
        return sanitized
    
    def sanitize_path_traversal(self, input_str: str) -> str:
        """过滤路径遍历攻击"""
        if not input_str:
            return input_str
        
        sanitized = input_str
        
        # 移除路径遍历模式
        for pattern in self.path_traversal_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def sanitize_input(self, input_str: str, enable_sql: bool = True, 
                       enable_xss: bool = True, enable_path: bool = True) -> str:
        """综合输入过滤"""
        if not input_str:
            return input_str
        
        sanitized = input_str
        
        if enable_sql:
            sanitized = self.sanitize_sql(sanitized)
        
        if enable_xss:
            sanitized = self.sanitize_xss(sanitized)
        
        if enable_path:
            sanitized = self.sanitize_path_traversal(sanitized)
        
        return sanitized
    
    def validate_input_length(self, input_str: str, max_length: int = 1000) -> bool:
        """验证输入长度"""
        return len(input_str) <= max_length if input_str else True
    
    def validate_input_charset(self, input_str: str, allowed_chars: str = None) -> bool:
        """验证输入字符集"""
        if not input_str:
            return True
        
        if allowed_chars:
            return all(c in allowed_chars for c in input_str)
        
        # 默认允许字母、数字、常用标点符号和中文
        allowed_pattern = r'^[a-zA-Z0-9\u4e00-\u9fa5\s\.,;:!?()\[\]{}"\'-_@#$%^&*+=|\\/<>~`]*$'
        return bool(re.match(allowed_pattern, input_str))


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self):
        self.permission_cache = {}
        self.cache_ttl = 300  # 5分钟缓存
    
    def check_permission(self, user_id: str, resource: str, action: str, 
                         required_level: PermissionLevel = PermissionLevel.READ) -> bool:
        """检查用户权限"""
        cache_key = f"{user_id}:{resource}:{action}"
        
        # 检查缓存
        if cache_key in self.permission_cache:
            cached_result, cached_time = self.permission_cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=self.cache_ttl):
                return cached_result
        
        # 实际权限检查逻辑（这里需要根据实际的权限系统实现）
        has_permission = self._check_user_permission(user_id, resource, action, required_level)
        
        # 缓存结果
        self.permission_cache[cache_key] = (has_permission, datetime.now())
        
        return has_permission
    
    def _check_user_permission(self, user_id: str, resource: str, action: str, 
                               required_level: PermissionLevel) -> bool:
        """实际的权限检查逻辑"""
        # 这里应该连接到实际的权限系统
        # 暂时返回True，实际使用时需要实现具体的权限检查逻辑
        return True
    
    def require_permission(self, resource: str, action: str, 
                           required_level: PermissionLevel = PermissionLevel.READ):
        """权限检查装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 从参数中获取用户ID（需要根据实际情况调整）
                user_id = kwargs.get('current_user_id') or getattr(args[0], 'user_id', None)
                
                if not user_id:
                    raise AuthException("用户未认证")
                
                if not self.check_permission(user_id, resource, action, required_level):
                    raise PermissionException(f"权限不足，无法执行{action}操作")
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def clear_permission_cache(self, user_id: str = None):
        """清除权限缓存"""
        if user_id:
            # 清除特定用户的缓存
            keys_to_remove = [key for key in self.permission_cache.keys() 
                              if key.startswith(f"{user_id}:")]
            for key in keys_to_remove:
                del self.permission_cache[key]
        else:
            # 清除所有缓存
            self.permission_cache.clear()


class SecurityAuditor:
    """安全审计器"""
    
    def __init__(self):
        self.audit_logs = []
        self.max_logs = 10000
    
    def log_security_event(self, event_type: str, user_id: str = None, 
                           resource: str = None, action: str = None, 
                           ip_address: str = None, user_agent: str = None, 
                           success: bool = True, details: Dict[str, Any] = None):
        """记录安全事件"""
        audit_log = {
            'timestamp': datetime.now(),
            'event_type': event_type,
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'details': details or {}
        }
        
        self.audit_logs.append(audit_log)
        
        # 限制日志数量
        if len(self.audit_logs) > self.max_logs:
            self.audit_logs = self.audit_logs[-self.max_logs:]
        
        # 记录到系统日志
        log_message = f"安全事件: {event_type} - 用户: {user_id} - 资源: {resource} - 操作: {action} - 成功: {success}"
        if success:
            logger.info(log_message)
        else:
            logger.warning(log_message)
    
    def get_audit_logs(self, user_id: str = None, event_type: str = None, 
                       start_time: datetime = None, end_time: datetime = None, 
                       limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志"""
        filtered_logs = self.audit_logs
        
        # 过滤条件
        if user_id:
            filtered_logs = [log for log in filtered_logs if log['user_id'] == user_id]
        
        if event_type:
            filtered_logs = [log for log in filtered_logs if log['event_type'] == event_type]
        
        if start_time:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] >= start_time]
        
        if end_time:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] <= end_time]
        
        # 按时间倒序排列并限制数量
        filtered_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return filtered_logs[:limit]
    
    def get_security_statistics(self) -> Dict[str, Any]:
        """获取安全统计信息"""
        total_events = len(self.audit_logs)
        
        if total_events == 0:
            return {
                'total_events': 0,
                'success_rate': 0,
                'event_types': {},
                'top_users': {},
                'recent_failures': []
            }
        
        success_count = sum(1 for log in self.audit_logs if log['success'])
        success_rate = success_count / total_events * 100
        
        # 事件类型统计
        event_types = {}
        for log in self.audit_logs:
            event_type = log['event_type']
            if event_type not in event_types:
                event_types[event_type] = 0
            event_types[event_type] += 1
        
        # 用户活动统计
        user_activities = {}
        for log in self.audit_logs:
            user_id = log['user_id']
            if user_id and user_id not in user_activities:
                user_activities[user_id] = 0
            if user_id:
                user_activities[user_id] += 1
        
        # 最近的失败事件
        recent_failures = [log for log in self.audit_logs[-100:] if not log['success']]
        recent_failures.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'total_events': total_events,
            'success_rate': round(success_rate, 2),
            'event_types': event_types,
            'top_users': dict(sorted(user_activities.items(), key=lambda x: x[1], reverse=True)[:10]),
            'recent_failures': recent_failures[:10]
        }


class TokenManager:
    """令牌管理器"""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.tokens = {}  # 在生产环境中应该使用Redis等外部存储
    
    def generate_token(self, user_id: str, expires_in: int = 3600, 
                       token_type: str = 'access') -> str:
        """生成令牌"""
        token_data = {
            'user_id': user_id,
            'token_type': token_type,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(seconds=expires_in)
        }
        
        # 生成令牌
        token = secrets.token_urlsafe(32)
        
        # 存储令牌信息
        self.tokens[token] = token_data
        
        return token
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证令牌"""
        if token not in self.tokens:
            return None
        
        token_data = self.tokens[token]
        
        # 检查是否过期
        if datetime.now() > token_data['expires_at']:
            del self.tokens[token]
            return None
        
        return token_data
    
    def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        if token in self.tokens:
            del self.tokens[token]
            return True
        return False
    
    def revoke_user_tokens(self, user_id: str) -> int:
        """撤销用户的所有令牌"""
        tokens_to_remove = []
        for token, token_data in self.tokens.items():
            if token_data['user_id'] == user_id:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self.tokens[token]
        
        return len(tokens_to_remove)
    
    def cleanup_expired_tokens(self) -> int:
        """清理过期令牌"""
        expired_tokens = []
        current_time = datetime.now()
        
        for token, token_data in self.tokens.items():
            if current_time > token_data['expires_at']:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.tokens[token]
        
        return len(expired_tokens)


# 全局实例
data_masker = DataMasker()
input_sanitizer = InputSanitizer()
permission_checker = PermissionChecker()
security_auditor = SecurityAuditor()
token_manager = TokenManager()


# 装饰器
def require_permission(resource: str, action: str, 
                       required_level: PermissionLevel = PermissionLevel.READ):
    """权限检查装饰器"""
    return permission_checker.require_permission(resource, action, required_level)


def audit_security_event(event_type: str, resource: str = None, action: str = None):
    """安全审计装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('current_user_id')
            success = True
            error = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                security_auditor.log_security_event(
                    event_type=event_type,
                    user_id=user_id,
                    resource=resource,
                    action=action,
                    success=success,
                    details={'error': error} if error else None
                )
        
        return wrapper
    return decorator


def sanitize_input(enable_sql: bool = True, enable_xss: bool = True, 
                   enable_path: bool = True, max_length: int = 1000):
    """输入过滤装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 过滤字符串参数
            sanitized_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str):
                    # 验证长度
                    if not input_sanitizer.validate_input_length(value, max_length):
                        raise ValidationException(f"参数{key}长度超过限制")
                    
                    # 过滤输入
                    sanitized_value = input_sanitizer.sanitize_input(
                        value, enable_sql, enable_xss, enable_path
                    )
                    sanitized_kwargs[key] = sanitized_value
                else:
                    sanitized_kwargs[key] = value
            
            return func(*args, **sanitized_kwargs)
        
        return wrapper
    return decorator


# 常用的安全检查函数
def is_safe_filename(filename: str) -> bool:
    """检查文件名是否安全"""
    if not filename:
        return False
    
    # 检查危险字符
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        if char in filename:
            return False
    
    # 检查保留名称（Windows）
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                      'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    
    if filename.upper() in reserved_names:
        return False
    
    return True


def generate_secure_random_string(length: int = 32) -> str:
    """生成安全的随机字符串"""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: str = None) -> tuple:
    """哈希密码"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    # 使用PBKDF2进行密码哈希
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return base64.b64encode(password_hash).decode(), salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """验证密码"""
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return base64.b64encode(password_hash).decode() == hashed_password