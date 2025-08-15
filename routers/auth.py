from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, query
from datetime import timedelta, datetime


from models.database import get_db
from models import User
from schemas import (
    LoginRequest, RegisterRequest, UserResponse, BaseResponse, UserProfileUpdateRequest
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
    setattr(user, 'last_login', datetime.utcnow())
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
        name=register_data.name,
        phone=register_data.phone,
        role=register_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user_with_org = db.query(User).options(joinedload(User.organization)).filter(User.id == db_user.id).first()
    
    return BaseResponse(
        message="注册成功",
        data=UserResponse.model_validate(user_with_org, from_attributes=True)
    )

@router.post("/logout", response_model=BaseResponse)
async def logout(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """用户登出"""
    query = db.query(User).filter(User.id == current_user.id)
    query.update({User.last_logout: datetime.now()})
    db.commit()
    return BaseResponse(message="登出成功", data="success")

@router.post("/refresh-token", response_model=BaseResponse)
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """刷新访问令牌"""
    # 检查用户是否已登出
    if current_user.last_logout is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已登出",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 检查用户是否已登录
    if current_user.last_login is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.username}, expires_delta=access_token_expires
    )
    return BaseResponse(
        message="刷新成功",
        data={
            "access_token": access_token,
            "token_type": "bearer"
        }
    )

@router.get("/me", response_model=BaseResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    from models import organization_members, Organization
    from sqlalchemy import select
    
    # 查询用户的组织信息
    position = None
    org_name = None
    
    # 查询用户在组织中的职位和部门信息
    org_query = db.execute(
        select(
            organization_members.c.position,
            Organization.name
        ).select_from(
            organization_members.join(Organization, organization_members.c.department_id == Organization.id)
        ).where(
            organization_members.c.user_id == current_user.id
        ).limit(1)  # 取第一个组织的信息
    ).first()
    
    if org_query:
        position = org_query.position
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user_with_org = db.query(User).options(joinedload(User.organization)).filter(User.id == current_user.id).first()
    
    # 创建用户响应数据
    user_data = UserResponse.model_validate(user_with_org, from_attributes=True)
    if position:
        user_data.position = position
    
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
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user_with_org = db.query(User).options(joinedload(User.organization)).filter(User.id == current_user.id).first()
    
    return BaseResponse(
        message="个人资料更新成功",
        data=UserResponse.model_validate(user_with_org, from_attributes=True)
    )

from fastapi import Body
from schemas import ChangePasswordRequest

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
    if not verify_password(password_data.currentPassword, str(current_user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
