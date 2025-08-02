from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from math import ceil

from models.database import get_db
from models.models import User
from routers import dashboard
from schemas.schemas import (
    UserCreate, UserUpdate, UserResponse, BaseResponse, PaginationResponse
)
from utils.auth import (
    get_current_active_user, require_permission, get_password_hash
)

router = APIRouter()

# 获取用户列表（简化版，用于列表展示）
@router.get("/list", response_model=BaseResponse)
async def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取用户列表（简化版，用于列表展示）"""
    from utils.response_utils import list_response
    users = db.query(User).all()
    return list_response(
        items=[UserResponse.from_orm(user) for user in users],
        message="获取用户列表成功"
    )

# 获取用户列表接口（分页）
@router.get("/page", response_model=BaseResponse)
async def get_users(
    search: Optional[str] = Query(None, description="搜索关键词"),
    role: Optional[str] = Query(None, description="角色过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    department: Optional[str] = Query(None, description="部门过滤"),
    page: int = Query(1, ge=1, description="页码"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="每页数量"),
    pageSize: Optional[int] = Query(None, ge=1, le=100, description="每页数量(兼容参数)"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取用户列表"""
    from utils.response_utils import list_response, paginate_query
    
    # 处理分页参数，优先使用 limit，如果没有则使用 pageSize，默认为 10
    size = limit or pageSize or 10
    
    query = db.query(User)
    
    # 搜索关键词过滤
    if search and search.strip():
        search_term = search.strip()
        query = query.filter(
            or_(
                User.username.contains(search_term),
                User.full_name.contains(search_term),
                User.email.contains(search_term)
            )
        )
    
    # 角色过滤
    if role and role.strip():
        query = query.filter(User.role == role.strip())
    
    # 状态过滤
    if status and status.strip():
        if status.strip().lower() == "active":
            query = query.filter(User.is_active == True)
        elif status.strip().lower() == "inactive":
            query = query.filter(User.is_active == False)
    
    # 部门过滤
    if department and department.strip():
        query = query.filter(User.department == department.strip())
    
    # 分页
    total, users = paginate_query(query, page, size)
    
    return list_response(
        records=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        size=size,
        message="获取用户列表成功"
    )


# 获取用户详情接口
@router.get("/{user_id}", response_model=BaseResponse)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取用户详情"""
    # 处理用户ID格式 - 如果是 "U" 开头的新格式，直接使用；如果是旧格式，保持兼容
    actual_user_id = user_id
    if user_id.startswith("USER_"):
        # 兼容旧的 "USER_xxx" 格式
        actual_user_id = user_id.replace("USER_", "")
    elif not user_id.startswith("U"):
        # 如果是纯数字，保持兼容
        actual_user_id = user_id
    
    user = db.query(User).filter(User.id == actual_user_id).first()
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
        username=user_data.username,  # type: ignore
        email=user_data.email,  # type: ignore
        password_hash=hashed_password,  # type: ignore
        full_name=user_data.full_name,  # type: ignore
        phone=user_data.phone,  # type: ignore
        role=user_data.role  # type: ignore
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
    # 处理用户ID格式 - 支持新的U前缀格式和旧格式兼容
    actual_user_id = user_id
    if user_id.startswith("USER_"):
        # 兼容旧的 "USER_xxx" 格式
        actual_user_id = user_id.replace("USER_", "")
    elif not user_id.startswith("U"):
        # 如果是纯数字，保持兼容
        actual_user_id = user_id
    
    user = db.query(User).filter(User.id == actual_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    update_data = user_data.dict(exclude_unset=True)

    for key, value in update_data.items():
        if key == "password" and value:
            # 处理密码更新
            user.password_hash = get_password_hash(value)  # type: ignore
        elif key == "status" and value:
            # 处理状态更新 - 添加安全检查
            if actual_user_id == current_user.id and value == "inactive":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能停用自己"
                )
            user.is_active = (value == "active")  # type: ignore
        elif key == "is_active" and value is not None:
            # 处理直接的is_active字段更新 - 添加安全检查
            if actual_user_id == current_user.id and not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能停用自己"
                )
            user.is_active = value  # type: ignore
        elif key in ["avatar", "username", "email", "full_name", "phone", "position", "department", "role", "is_verified", "organization_id"]:
            # 处理其他字段
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
    # 处理用户ID格式 - 支持新的U前缀格式和旧格式兼容
    actual_user_id = user_id
    if user_id.startswith("USER_"):
        # 兼容旧的 "USER_xxx" 格式
        actual_user_id = user_id.replace("USER_", "")
    elif not user_id.startswith("U"):
        # 如果是纯数字，保持兼容
        actual_user_id = user_id
    
    if actual_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )
    
    user = db.query(User).filter(User.id == actual_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    db.delete(user)
    db.commit()
    
    return BaseResponse(message="删除用户成功")