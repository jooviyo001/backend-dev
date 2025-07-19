from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    create_refresh_token,
    verify_token,
    get_current_user,
    logout_user,
    security
)
from app.core.redis_client import redis_client
from app.models.user import User
from app.schemas.user import UserLogin, UserLoginResponse, UserCreate, UserResponse, PasswordChange
from app.schemas.base import BaseResponse

router = APIRouter()

@router.post("/login", response_model=BaseResponse[UserLoginResponse])
async def login(
    user_credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    # 查找用户
    result = await db.execute(
        select(User).where(
            (User.username == user_credentials.username) | 
            (User.email == user_credentials.username)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账户已被禁用"
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # 创建刷新令牌
    refresh_token = create_refresh_token(
        data={"sub": user.id, "username": user.username}
    )
    
    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # 缓存用户信息
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
    await redis_client.set(f"user:{user.id}", user_dict, expire=1800)
    
    return BaseResponse(
        data=UserLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800,  # 30分钟
            user=UserResponse.from_orm(user)
        ),
        message="登录成功"
    )

@router.post("/register", response_model=BaseResponse[UserResponse])
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(
            (User.username == user_data.username) | 
            (User.email == user_data.email)
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在"
        )
    
    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        name=user_data.name,
        phone=user_data.phone,
        department=user_data.department,
        position=user_data.position,
        avatar=user_data.avatar,
        role=user_data.role,
        status="pending"  # 新注册用户需要审核
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return BaseResponse(
        data=UserResponse.from_orm(new_user),
        message="注册成功，等待管理员审核"
    )

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user)
):
    """用户登出"""
    # 将令牌加入黑名单
    await logout_user(credentials.credentials)
    
    # 清除用户缓存
    await redis_client.delete(f"user:{current_user.id}")
    
    return BaseResponse(message="登出成功")

@router.post("/refresh-token")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """刷新访问令牌"""
    try:
        token_data = await verify_token(credentials)
        
        # 检查是否为刷新令牌
        if token_data.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )
        
        user_id = token_data.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用"
            )
        
        # 创建新的访问令牌
        access_token_expires = timedelta(minutes=30)
        new_access_token = create_access_token(
            data={"sub": user.id, "username": user.username, "role": user.role},
            expires_delta=access_token_expires
        )
        
        return BaseResponse(
            data={
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": 1800
            },
            message="令牌刷新成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌失败"
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
    
    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    return BaseResponse(message="密码修改成功")

@router.get("/me", response_model=BaseResponse[UserResponse])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return BaseResponse(
        data=UserResponse.from_orm(current_user),
        message="获取成功"
    )