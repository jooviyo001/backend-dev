from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional
from models.database import get_db
from models.user import UserRole, User
from schemas.base import BaseResponse
from schemas.user import (
    UserCreate, UserUpdate, UserResponse,
    NotificationSettings, NotificationSettingsResponse, NotificationSettingsUpdate,
    LanguageSettings, LanguageSettingsResponse, LanguageSettingsUpdate,
    UserStatusUpdate
)
from utils.auth import (
    get_current_active_user, require_permission, get_password_hash
)

router = APIRouter()

# 获取用户列表（简化版，用于列表展示）
@router.get("/list", response_model=BaseResponse)
async def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read")) # 用上该对象，确保用户有读取权限

):
    """获取用户列表（简化版，用于列表展示）"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")


    from utils.response_utils import list_response
    from sqlalchemy.orm import joinedload
    
    # 搜索关键词过滤
    if search and search.strip():
        search_term = search.strip()
        query = db.query(User).filter(
            or_(
                User.username.contains(search_term),
                User.name.contains(search_term),
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
        if oraganizition_name and oraganizition_name.strip():
            query = query.filter(User.oraganizition_name == oraganizition_name.strip())
        # 组织过滤
        if organization and organization.strip():
            query = query.filter(User.organization_name == organization.strip())

        # 岗位过滤
        if position and position.strip():
            query = query.filter(User.position == position.strip())
        # 组织过滤
        if organization and organization.strip():
            query = query.filter(User.organization_name == organization.strip())
        # 手机号过滤
        if phone and phone.strip():
            query = query.filter(User.phone == phone.strip())
        # 邮箱过滤
        if email and email.strip():
            query = query.filter(User.email == email.strip())

    # 预加载组织信息以获取组织名称
    users = db.query(User).options(joinedload(User.organization)).all()
    return list_response(
        items=[UserResponse.model_validate(user, from_attributes=True) for user in users],
        message="获取用户列表成功"
    )

# 获取用户列表接口（分页）
@router.get("/page", response_model=BaseResponse)
async def get_users(
    search: Optional[str] = Query(None, description="搜索关键词"),
    role: Optional[str] = Query(None, description="角色过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    organization_name: Optional[str] = Query(None, description="部门过滤"),
    page: int = Query(1, ge=1, description="页码"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="每页数量"),
    pageSize: Optional[int] = Query(None, ge=1, le=100, description="每页数量(兼容参数)"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取用户列表"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")

    from utils.response_utils import list_response, paginate_query
    
    # 处理分页参数，优先使用 limit，如果没有则使用 pageSize，默认为 10
    size = limit or pageSize or 10
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    query = db.query(User).options(joinedload(User.organization))
    
    # 搜索关键词过滤
    if search and search.strip():
        search_term = search.strip()
        query = query.filter(
            or_(
                User.username.contains(search_term),
                User.name.contains(search_term),
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
    if organization_name and organization_name.strip():
        query = query.filter(User.organization_name == organization_name.strip())
    
    # 分页
    total, users = paginate_query(query, page, size)
    
    return list_response(
        records=[UserResponse.model_validate(user, from_attributes=True) for user in users],
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
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")

    # 处理用户ID格式 - 如果是 "U" 开头的新格式，直接使用；如果是旧格式，保持兼容
    actual_user_id = user_id
    if user_id.startswith("USER_"):
        # 兼容旧的 "USER_xxx" 格式
        actual_user_id = user_id.replace("USER_", "")
    elif not user_id.startswith("U"):
        # 如果是纯数字，保持兼容
        actual_user_id = user_id
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user = db.query(User).options(joinedload(User.organization)).filter(User.id == actual_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return BaseResponse(
        message="获取用户详情成功",
        data=UserResponse.model_validate(user, from_attributes=True)
    )

# 创建用户
@router.post("/create", response_model=BaseResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """创建用户"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")

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
        name=user_data.name,  # type: ignore
        phone=user_data.phone,  # type: ignore
        role=user_data.role  # type: ignore
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user_with_org = db.query(User).options(joinedload(User.organization)).filter(User.id == db_user.id).first()
    
    return BaseResponse(
        message="创建用户成功",
        data=UserResponse.model_validate(user_with_org, from_attributes=True)
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
    # 权限校验，只能更新自己的或者只有管理员可以更新其他用户
    if current_user.role != UserRole.ADMIN and user_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有权限访问")

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
        elif key in ["avatar", "username", "email", "name", "phone", "position", "oraganizition_name", "role", "is_verified", "organization_id"]: 
            # 处理其他字段
            setattr(user, key, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user_with_org = db.query(User).options(joinedload(User.organization)).filter(User.id == user.id).first()

    return BaseResponse(
        message="用户信息更新成功",
        data=UserResponse.model_validate(user_with_org, from_attributes=True)
    )

# 删除用户
@router.delete("/{user_id}", response_model=BaseResponse)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """删除用户"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")

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

# 更新用户状态
@router.put("/{user_id}/status", response_model=BaseResponse)
async def update_user_status(
    user_id: str,
    status_data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:write"))
):
    """更新用户状态"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")

    # 处理用户ID格式 - 支持新的U前缀格式和旧格式兼容
    actual_user_id = user_id
    if user_id.startswith("USER_"):
        # 兼容旧的 "USER_xxx" 格式
        actual_user_id = user_id.replace("USER_", "")
    elif not user_id.startswith("U"):
        # 如果是纯数字，保持兼容
        actual_user_id = user_id
    
    # 安全检查：不能停用自己
    if actual_user_id == current_user.id and status_data.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己"
        )
    
    user = db.query(User).filter(User.id == actual_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新用户状态
    user.is_active = (status_data.status == "active")  # type: ignore
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 预加载组织信息以获取组织名称
    from sqlalchemy.orm import joinedload
    user_with_org = db.query(User).options(joinedload(User.organization)).filter(User.id == user.id).first()
    
    return BaseResponse(
        message=f"用户状态已更新为{'启用' if status_data.status == 'active' else '停用'}",
        data=UserResponse.model_validate(user_with_org, from_attributes=True)
    )

# 获取用户通知设置
@router.get("/notification-settings", response_model=BaseResponse)
async def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的通知设置"""
    from utils.response_utils import standard_response
    
    # 获取用户的通知设置
    settings_dict = current_user.get_notification_settings()
    settings = NotificationSettings(**settings_dict)
    
    response_data = NotificationSettingsResponse(
        user_id=current_user.id,
        settings=settings,
        updated_at=current_user.updated_at
    )
    
    return standard_response(
        data=response_data,
        message="获取通知设置成功"
    )

# 更新用户通知设置
@router.put("/notification-settings", response_model=BaseResponse)
async def update_notification_settings(
    settings_update: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新当前用户的通知设置"""
    from utils.response_utils import standard_response
    
    # 获取当前设置
    current_settings = current_user.get_notification_settings()
    
    # 更新设置
    update_data = settings_update.model_dump(exclude_unset=True)
    current_settings.update(update_data)
    
    # 保存设置
    current_user.set_notification_settings(current_settings)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # 构造响应数据
    settings = NotificationSettings(**current_settings)
    response_data = NotificationSettingsResponse(
        user_id=current_user.id,
        settings=settings,
        updated_at=current_user.updated_at
    )
    
    return standard_response(
        data=response_data,
        message="通知设置更新成功"
    )

# /language-settings
@router.get("/language-settings", response_model=BaseResponse)
async def get_language_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的语言设置"""
    from utils.response_utils import standard_response
    
    # 获取用户的语言设置
    settings_dict = current_user.get_language_settings()
    settings = LanguageSettings(**settings_dict)
    
    response_data = LanguageSettingsResponse(
        user_id=current_user.id,
        settings=settings,
        updated_at=current_user.updated_at
    )
    
    return standard_response(
        data=response_data,
        message="获取语言设置成功"
    )

# 更新用户语言设置
@router.put("/language-settings", response_model=BaseResponse)
async def update_language_settings(
    settings_update: LanguageSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新当前用户的语言设置"""
    from utils.response_utils import standard_response
    
    # 获取当前设置
    current_settings = current_user.get_language_settings()
    
    # 更新设置
    update_data = settings_update.model_dump(exclude_unset=True)
    current_settings.update(update_data)

    # 保存设置
    current_user.set_language_settings(current_settings)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # 构造响应数据
    settings = LanguageSettings(**current_settings)
    response_data = LanguageSettingsResponse(
        user_id=current_user.id,
        settings=settings,
        updated_at=current_user.updated_at
    )
    return standard_response(
        data=response_data,
        message="语言设置更新成功"
    )


