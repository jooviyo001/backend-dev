from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models.database import get_db
from models import User
import os
from dotenv import load_dotenv

load_dotenv()

# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 调试模式开关 - 设置为True时将跳过所有鉴权检查
# 使用方法：在.env文件中设置 DEBUG_SKIP_AUTH=true 或 DEBUG=true 即可启用
# 注意：此功能仅用于开发环境，生产环境必须设置为false
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"
DEBUG_SKIP_AUTH = os.getenv("DEBUG_SKIP_AUTH", "false").lower() == "true" or DEBUG_MODE

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 安全配置 - 在调试模式下使认证变为可选
if DEBUG_SKIP_AUTH:
    from fastapi.security import HTTPBearer
    security = HTTPBearer(auto_error=False)  # 不自动抛出错误
else:
    security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), db: Session = Depends(get_db)) -> User:
    """获取当前用户"""
    # 调试模式：跳过鉴权，返回默认管理员用户
    if DEBUG_SKIP_AUTH:
        admin_user = db.query(User).filter(User.role == "ADMIN").first()
        if admin_user:
            return admin_user
        # 如果没有管理员用户，返回第一个用户
        first_user = db.query(User).first()
        if first_user:
            return first_user
        # 如果没有任何用户，创建一个临时用户对象
        from models import UserRole
        temp_user = User()
        temp_user.id = 1
        temp_user.username = "debug_admin"  # 调试模式下的管理员用户名
        temp_user.email = "debug@admin.com"
        temp_user.role = UserRole.ADMIN
        temp_user.is_active = True
        return temp_user
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    username = payload.get("sub")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用"
        )
    
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    return current_user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """认证用户"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def check_permission(user: User, required_permission: str) -> bool:
    """检查用户权限"""
    # 简单的权限检查，可以根据需要扩展
    permission_map = {
        # 权限说明：
        # admin：管理员权限，拥有所有资源的读写权限
        # manager：项目管理权限，对项目、任务、缺陷有读写权限
        # member：项目成员权限，对项目、任务、缺陷有读写权限
        # user：普通用户权限，只能查看资源

        "admin": ["user:read", "user:write", "project:read", "project:write", 
                 "task:read", "task:write", "organization:read", "organization:write",
                 "defect:read", "defect:write", "upload:read", "upload:write", "upload:delete"],
        "manager": ["user:read", "project:read", "project:write", 
                   "task:read", "task:write", "organization:read",
                   "defect:read", "defect:write", "upload:read", "upload:write", "upload:delete"],
        "member": ["user:read", "project:read", "task:read", "task:write",
                  "defect:read", "defect:write", "upload:read", "upload:write"],
        "user": ["user:read", "project:read", "task:read", "defect:read", "upload:read"]
    }
    
    user_permissions = permission_map.get(user.role.value, [])
    return required_permission in user_permissions

def require_permission(permission: str):
    """权限装饰器"""
    def permission_checker(current_user: User = Depends(get_current_active_user)):
        # 调试模式：跳过权限检查
        if DEBUG_SKIP_AUTH:
            return current_user
            
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user
    return permission_checker