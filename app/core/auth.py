from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import redis_client
from app.models.user import User

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """验证JWT令牌"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # 检查令牌是否在黑名单中（如果Redis可用）
        try:
            is_blacklisted = await redis_client.exists(f"blacklist:{credentials.credentials}")
            if is_blacklisted:
                raise credentials_exception
        except Exception as e:
            print(f"Redis blacklist check error: {e}")
            # Redis不可用时跳过黑名单检查，继续验证token
            
        return payload
    except JWTError:
        raise credentials_exception

async def get_current_user(token_data: Dict[str, Any] = Depends(verify_token), db: AsyncSession = Depends(get_db)) -> User:
    """获取当前用户"""
    user_id = token_data.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    # 先从缓存中获取用户信息（如果Redis可用）
    try:
        cached_user = await redis_client.get(f"user:{user_id}")
        if cached_user:
            return User(**cached_user)
    except Exception as e:
        print(f"Redis cache get error: {e}")
        # Redis不可用时继续从数据库获取
    
    # 从数据库获取用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # 尝试缓存用户信息（如果Redis可用）
    try:
        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "status": user.status,
            "avatar": user.avatar,
            "department": user.department
        }
        await redis_client.set(f"user:{user_id}", user_dict, expire=1800)  # 30分钟缓存
    except Exception as e:
        print(f"Redis cache set error: {e}")
        # Redis不可用时忽略缓存，继续返回用户
    
    return user

def check_permission(required_permission: str):
    """权限检查装饰器"""
    def permission_checker(current_user: User = Depends(get_current_user)):
        # 管理员拥有所有权限
        if current_user.role == "admin":
            return current_user
        
        # 检查具体权限
        user_permissions = get_user_permissions(current_user.role)
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return current_user
    
    return permission_checker

def get_user_permissions(role: str) -> list:
    """根据角色获取权限列表"""
    permissions_map = {
        "admin": ["*"],  # 所有权限
        "manager": [
            "user:view", "user:create", "user:edit",
            "project:view", "project:create", "project:edit", "project:delete",
            "task:view", "task:create", "task:edit", "task:delete",
            "organization:view", "organization:create", "organization:edit"
        ],
        "project_manager": [
            "user:view",
            "project:view", "project:create", "project:edit",
            "task:view", "task:create", "task:edit", "task:delete",
            "organization:view"
        ],
        "member": [
            "user:view",
            "project:view",
            "task:view", "task:edit",
            "organization:view"
        ]
    }
    
    return permissions_map.get(role, [])

async def logout_user(token: str):
    """用户登出，将令牌加入黑名单"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if exp:
            # 计算令牌剩余有效时间
            remaining_time = exp - datetime.utcnow().timestamp()
            if remaining_time > 0:
                try:
                    await redis_client.set(
                        f"blacklist:{token}", 
                        "1", 
                        expire=int(remaining_time)
                    )
                except Exception as e:
                    print(f"Redis blacklist set error: {e}")
                    # Redis不可用时忽略黑名单设置
    except JWTError:
        pass  # 无效令牌，忽略