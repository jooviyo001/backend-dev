from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from models.database import get_db
from models.models import User
from schemas.schemas import (
    LoginRequest, LoginResponse, RegisterRequest, UserResponse, BaseResponse, UserProfileUpdateRequest
)
from utils.auth import (
    authenticate_user, create_access_token, get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES, get_current_active_user
)

router = APIRouter()

@router.post("/login", response_model=BaseResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # 更新最后登录时间
    from datetime import datetime
    user.last_login = datetime.now()
    db.commit()
    
    return BaseResponse(
        message="登录成功",
        data={
            "access_token": access_token,
            "token_type": "bearer"
        }
    )

@router.post("/register", response_model=BaseResponse)
async def register(register_data: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    if db.query(User).filter(User.username == register_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == register_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已存在"
        )
    
    # 创建新用户
    hashed_password = get_password_hash(register_data.password)
    db_user = User(
        username=register_data.username,
        email=register_data.email,
        password_hash=hashed_password,
        full_name=register_data.full_name,
        phone=register_data.phone,
        role=register_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return BaseResponse(
        message="注册成功",
        data=UserResponse.from_orm(db_user)
    )

@router.post("/logout", response_model=BaseResponse)
async def logout(current_user: User = Depends(get_current_active_user)):
    """用户登出"""
    # 在实际应用中，可以将token加入黑名单
    return BaseResponse(message="登出成功", data="success")

@router.get("/me", response_model=BaseResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    from models.models import organization_members, Organization
    from sqlalchemy import select
    
    # 查询用户的组织信息
    position = None
    department = None
    
    # 查询用户在组织中的职位和部门信息
    org_query = db.execute(
        select(
            organization_members.c.position,
            Organization.name
        ).select_from(
            organization_members.join(Organization, organization_members.c.organization_id == Organization.id)
        ).where(
            organization_members.c.user_id == current_user.id
        ).limit(1)  # 取第一个组织的信息
    ).first()
    
    if org_query:
        position = org_query.position
        department = org_query.name
    
    # 创建用户响应数据
    user_data = UserResponse.from_orm(current_user)
    user_data.position = position
    user_data.department = department
    
    return BaseResponse(
        message="获取用户信息成功",
        data=user_data
    )

@router.put("/profile", response_model=BaseResponse)
async def update_user_profile(
    profile_data: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新当前用户个人资料"""
    # 遍历请求体中的数据，更新用户模型
    for field, value in profile_data.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return BaseResponse(
        message="个人资料更新成功",
        data=UserResponse.from_orm(current_user)
    )

from fastapi import Body
from schemas.schemas import ChangePasswordRequest

@router.put("/change-password", response_model=BaseResponse)
async def change_password(
    password_data: ChangePasswordRequest = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    from utils.auth import verify_password
    
    # 校验密码是否为空
    if not password_data.currentPassword or not password_data.newPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码和新密码不能为空"
        )

    # 验证旧密码
    if not verify_password(password_data.currentPassword, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
    
    # 更新密码
    current_user.password_hash = get_password_hash(password_data.newPassword)
    db.commit()
    db.refresh(current_user)
    
    return BaseResponse(
        message="密码修改成功",
        data="success"
    )

@router.post("/refresh-token", response_model=BaseResponse)
async def refresh_token(current_user: User = Depends(get_current_active_user)):
    """刷新令牌"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.username}, expires_delta=access_token_expires
    )
    
    return BaseResponse(
        message="令牌刷新成功",
        data={"access_token": access_token, "token_type": "bearer"}
    )