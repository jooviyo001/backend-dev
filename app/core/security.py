from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from passlib.hash import bcrypt
import secrets
import string
import re
from app.core.config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(
    subject: Union[str, Any], 
    expires_delta: timedelta = None
) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, Any], 
    expires_delta: timedelta = None
) -> str:
    """创建刷新令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """验证令牌"""
    try:
        payload = jwt.decode(
            token, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        
        # 检查令牌类型
        if payload.get("type") != token_type:
            return None
        
        # 获取用户ID
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        return user_id
        
    except JWTError:
        return None

def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def generate_password_reset_token(email: str) -> str:
    """生成密码重置令牌"""
    delta = timedelta(hours=1)  # 1小时有效期
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "password_reset"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt

def verify_password_reset_token(token: str) -> Optional[str]:
    """验证密码重置令牌"""
    try:
        decoded_token = jwt.decode(
            token, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        
        # 检查令牌类型
        if decoded_token.get("type") != "password_reset":
            return None
        
        return decoded_token["sub"]
        
    except JWTError:
        return None

def generate_email_verification_token(email: str) -> str:
    """生成邮箱验证令牌"""
    delta = timedelta(hours=24)  # 24小时有效期
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "email_verification"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt

def verify_email_verification_token(token: str) -> Optional[str]:
    """验证邮箱验证令牌"""
    try:
        decoded_token = jwt.decode(
            token, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        
        # 检查令牌类型
        if decoded_token.get("type") != "email_verification":
            return None
        
        return decoded_token["sub"]
        
    except JWTError:
        return None

def generate_random_password(length: int = 12) -> str:
    """生成随机密码"""
    # 确保密码包含各种字符类型
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    # 确保至少包含一个每种类型的字符
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special_chars)
    ]
    
    # 填充剩余长度
    all_chars = lowercase + uppercase + digits + special_chars
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # 打乱顺序
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """验证密码强度"""
    errors = []
    
    # 检查长度
    if len(password) < settings.password_min_length:
        errors.append(f"密码长度至少需要 {settings.password_min_length} 个字符")
    
    # 检查大写字母
    if settings.password_require_uppercase and not re.search(r'[A-Z]', password):
        errors.append("密码必须包含至少一个大写字母")
    
    # 检查小写字母
    if settings.password_require_lowercase and not re.search(r'[a-z]', password):
        errors.append("密码必须包含至少一个小写字母")
    
    # 检查数字
    if settings.password_require_numbers and not re.search(r'\d', password):
        errors.append("密码必须包含至少一个数字")
    
    # 检查特殊字符
    if settings.password_require_special and not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        errors.append("密码必须包含至少一个特殊字符")
    
    # 检查常见弱密码
    weak_passwords = [
        "password", "123456", "123456789", "qwerty", "abc123",
        "password123", "admin", "root", "user", "test"
    ]
    if password.lower() in weak_passwords:
        errors.append("密码过于简单，请使用更复杂的密码")
    
    return len(errors) == 0, errors

def generate_api_key(length: int = 32) -> str:
    """生成API密钥"""
    return secrets.token_urlsafe(length)

def generate_csrf_token() -> str:
    """生成CSRF令牌"""
    return secrets.token_urlsafe(32)

def create_session_token(user_id: str, session_data: dict = None) -> str:
    """创建会话令牌"""
    now = datetime.utcnow()
    expires = now + timedelta(hours=24)  # 24小时有效期
    
    payload = {
        "exp": expires,
        "iat": now,
        "sub": user_id,
        "type": "session",
        "data": session_data or {}
    }
    
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm
    )

def verify_session_token(token: str) -> Optional[dict]:
    """验证会话令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        
        # 检查令牌类型
        if payload.get("type") != "session":
            return None
        
        return {
            "user_id": payload.get("sub"),
            "data": payload.get("data", {}),
            "issued_at": payload.get("iat"),
            "expires_at": payload.get("exp")
        }
        
    except JWTError:
        return None

def hash_api_key(api_key: str) -> str:
    """哈希API密钥"""
    return get_password_hash(api_key)

def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """验证API密钥"""
    return verify_password(plain_api_key, hashed_api_key)

def generate_otp_secret() -> str:
    """生成OTP密钥"""
    return secrets.token_urlsafe(32)

def generate_backup_codes(count: int = 10) -> list[str]:
    """生成备份代码"""
    codes = []
    for _ in range(count):
        # 生成8位数字代码
        code = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
        # 格式化为 XXXX-XXXX
        formatted_code = f"{code[:4]}-{code[4:]}"
        codes.append(formatted_code)
    return codes

def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """掩码敏感数据"""
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    visible_start = visible_chars // 2
    visible_end = visible_chars - visible_start
    
    masked_length = len(data) - visible_chars
    masked_part = mask_char * masked_length
    
    return data[:visible_start] + masked_part + data[-visible_end:] if visible_end > 0 else data[:visible_start] + masked_part

def is_password_compromised(password: str) -> bool:
    """检查密码是否已泄露（简单实现）"""
    # 这里可以集成 HaveIBeenPwned API 或其他密码泄露检查服务
    # 目前只是简单的本地检查
    common_passwords = [
        "123456", "password", "123456789", "12345678", "12345",
        "111111", "1234567", "sunshine", "qwerty", "iloveyou",
        "admin", "welcome", "monkey", "login", "abc123",
        "starwars", "123123", "dragon", "passw0rd", "master",
        "hello", "freedom", "whatever", "qazwsx", "trustno1"
    ]
    
    return password.lower() in common_passwords

def calculate_password_entropy(password: str) -> float:
    """计算密码熵值"""
    import math
    
    # 字符集大小
    charset_size = 0
    
    if re.search(r'[a-z]', password):
        charset_size += 26  # 小写字母
    if re.search(r'[A-Z]', password):
        charset_size += 26  # 大写字母
    if re.search(r'\d', password):
        charset_size += 10  # 数字
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        charset_size += 32  # 特殊字符（估算）
    
    # 计算熵值：log2(charset_size^length)
    if charset_size > 0:
        entropy = len(password) * math.log2(charset_size)
        return entropy
    
    return 0.0

def get_password_strength_score(password: str) -> tuple[int, str]:
    """获取密码强度评分"""
    score = 0
    
    # 长度评分
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1
    
    # 字符类型评分
    if re.search(r'[a-z]', password):
        score += 1
    if re.search(r'[A-Z]', password):
        score += 1
    if re.search(r'\d', password):
        score += 1
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        score += 1
    
    # 熵值评分
    entropy = calculate_password_entropy(password)
    if entropy >= 50:
        score += 1
    if entropy >= 75:
        score += 1
    
    # 检查是否为常见密码
    if is_password_compromised(password):
        score = max(0, score - 3)
    
    # 评级
    if score <= 2:
        return score, "弱"
    elif score <= 5:
        return score, "中等"
    elif score <= 7:
        return score, "强"
    else:
        return score, "非常强"

class SecurityUtils:
    """安全工具类"""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名"""
        # 移除危险字符
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # 限制长度
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_length] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """验证手机号格式"""
        # 简单的中国手机号验证
        pattern = r'^1[3-9]\d{9}$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def generate_secure_filename(original_filename: str) -> str:
        """生成安全的文件名"""
        # 获取文件扩展名
        if '.' in original_filename:
            name, ext = original_filename.rsplit('.', 1)
            ext = '.' + ext.lower()
        else:
            ext = ''
        
        # 生成随机文件名
        random_name = secrets.token_urlsafe(16)
        
        return random_name + ext