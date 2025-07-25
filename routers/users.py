from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from math import ceil

from models.database import get_db
from models.models import User
from schemas.schemas import (
    UserCreate, UserUpdate, UserResponse, BaseResponse, PaginationResponse, UserStatusToggle
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

# 替换为当前用户
@router.get("/{user_id}", response_model=BaseResponse)
async def get_user(
    user_id: str,
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
    user_id: str,
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

    update_data = user_data.dict(exclude_unset=True)

    for key, value in update_data.items():
        if key == "password" and value:
            user.password_hash = get_password_hash(value)
        elif key == "avatar":
            setattr(user, key, value)
        else:
            setattr(user, key, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    return BaseResponse(
        message="用户信息更新成功",
        data=UserResponse.from_orm(user)
    )

# 删除用户
@router.delete("/{user_id}", response_model=BaseResponse)
async def delete_user(
    user_id: str,
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
    user_id: str,
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
    user_id: str,
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
    user_id: str,
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
    user_id: str,
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