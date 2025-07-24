from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from math import ceil

from models.database import get_db
from models.models import User
from schemas.schemas import (
    UserCreate, UserUpdate, UserResponse, BaseResponse, PaginationResponse, UserStatusToggle, UserProfile
)
from utils.auth import (
    get_current_active_user, require_permission, get_password_hash
)

router = APIRouter()

@router.get("/list", response_model=BaseResponse)
async def get_users(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    role: Optional[str] = Query(None, description="角色过滤"),
    is_active: Optional[bool] = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取用户列表"""
    from utils.response_utils import list_response, paginate_query
    
    query = db.query(User)
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                User.username.contains(keyword),
                User.full_name.contains(keyword),
                User.email.contains(keyword)
            )
        )
    
    # 角色过滤
    if role:
        query = query.filter(User.role == role)
    
    # 状态过滤
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # 分页
    total, users = paginate_query(query, page, size)
    
    return list_response(
        items=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        size=size,
        message="获取用户列表成功"
    )

@router.get("/page", response_model=BaseResponse)
async def get_users_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    role: Optional[str] = Query(None, description="角色过滤"),
    is_active: Optional[bool] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:read"))
):
    """获取用户分页数据"""
    return await get_users(keyword, role, is_active, page, size, db, current_user)

# 用户档案接口 - 必须放在 /{user_id} 之前避免路由冲突
@router.put("/profile", response_model=BaseResponse)
async def create_user_profile(
    profile_data: UserProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """创建/更新用户档案"""
    from datetime import datetime
    import re
    
    # 处理用户ID - 支持字符串ID，提取数字部分
    user_id = None
    if profile_data.id:
        if profile_data.id.isdigit():
            user_id = int(profile_data.id)
        else:
            # 从字符串ID中提取数字部分，如 "USER_206386416517648384" -> 206386416517648384
            match = re.search(r'(\d+)', profile_data.id)
            if match:
                user_id = int(match.group(1))
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的用户ID格式"
        )
    
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新用户信息
    if profile_data.username:
        user.username = profile_data.username
    if profile_data.name:  # 支持name字段
        user.full_name = profile_data.name
    if profile_data.email:
        user.email = profile_data.email
    if profile_data.phone:
        user.phone = profile_data.phone
    if profile_data.full_name:
        user.full_name = profile_data.full_name
    if profile_data.avatar:
        user.avatar = profile_data.avatar
    if profile_data.role:
        user.role = profile_data.role
    if profile_data.is_active is not None:
        user.is_active = profile_data.is_active
    if profile_data.is_verified is not None:
        user.is_verified = profile_data.is_verified
    
    # 处理时间字段 - 支持ISO格式和y-m-d h:m:s格式
    def parse_datetime(date_str):
        if not date_str:
            return None
        try:
            # 尝试解析ISO格式 (2025-07-25T00:47:28.040233)
            if 'T' in date_str:
                # 移除微秒部分
                if '.' in date_str:
                    date_str = date_str.split('.')[0]
                return datetime.fromisoformat(date_str)
            # 尝试解析y-m-d h:m:s格式
            else:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    
    if profile_data.last_login:
        parsed_time = parse_datetime(profile_data.last_login)
        if parsed_time:
            user.last_login = parsed_time
    
    if profile_data.created_at:
        parsed_time = parse_datetime(profile_data.created_at)
        if parsed_time:
            user.created_at = parsed_time
    
    if profile_data.updated_at:
        parsed_time = parse_datetime(profile_data.updated_at)
        if parsed_time:
            user.updated_at = parsed_time
    
    db.commit()
    db.refresh(user)
    
    # 格式化返回数据
    response_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "full_name": user.full_name,
        "avatar": user.avatar,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "position": profile_data.position or "",  # 扩展字段
        "department": profile_data.department or "",  # 扩展字段
        "last_login": user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else "",
        "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
        "updated_at": user.updated_at.strftime("%Y-%m-%d %H:%M:%S") if user.updated_at else ""
    }
    
    return BaseResponse(
        message="更新用户档案成功",
        data=response_data
    )

# 替换为当前用户
@router.get("/{user_id}", response_model=BaseResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return BaseResponse(
        message="获取用户详情成功",
        data=UserResponse.from_orm(user)
    )

# 创建用户
@router.post("/create", response_model=BaseResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """创建用户"""
    # 检查用户名是否已存在
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已存在"
        )
    
    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        phone=user_data.phone,
        role=user_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return BaseResponse(
        message="创建用户成功",
        data=UserResponse.from_orm(db_user)
    )

# 更新用户
@router.put("/{user_id}", response_model=BaseResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """更新用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户名是否已被其他用户使用
    if user_data.username and user_data.username != user.username:
        existing_user = db.query(User).filter(
            and_(User.username == user_data.username, User.id != user_id)
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在"
            )
    
    # 检查邮箱是否已被其他用户使用
    if user_data.email and user_data.email != user.email:
        existing_user = db.query(User).filter(
            and_(User.email == user_data.email, User.id != user_id)
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已存在"
            )
    
    # 更新用户信息
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return BaseResponse(
        message="更新用户信息成功",
        data=UserResponse.from_orm(user)
    )

@router.delete("/{user_id}", response_model=BaseResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """删除用户"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    db.delete(user)
    db.commit()
    
    return BaseResponse(message="删除用户成功")

@router.put("/{user_id}/activate", response_model=BaseResponse)
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """激活用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.is_active = True
    db.commit()
    
    return BaseResponse(message="激活用户成功")

@router.put("/{user_id}/deactivate", response_model=BaseResponse)
async def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """停用用户"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.is_active = False
    db.commit()
    
    return BaseResponse(message="停用用户成功")

@router.put("/{user_id}/toggle-status", response_model=BaseResponse)
async def toggle_user_status(
    user_id: int,
    status_data: UserStatusToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """切换用户状态"""
    # 检查是否尝试修改自己的状态为inactive
    if user_id == current_user.id and status_data.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 根据传入的状态设置用户状态
    new_status = status_data.status == "active"
    user.is_active = new_status
    db.commit()
    db.refresh(user)
    
    status_text = "激活" if new_status else "停用"
    return BaseResponse(
        message=f"{status_text}用户成功",
        data=UserResponse.from_orm(user)
    )