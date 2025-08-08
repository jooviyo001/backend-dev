from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional
from models.database import get_db
from models.user import UserRole, User
from models.position import Position
from schemas.base import BaseResponse
from schemas.user import (
    UserCreate, UserUpdate, UserResponse,
    NotificationSettings, NotificationSettingsResponse, NotificationSettingsUpdate,
    LanguageSettings, LanguageSettingsResponse, LanguageSettingsUpdate,
    UserStatusUpdate
)
from schemas.position import (
    PositionCreate, PositionUpdate, PositionResponse, PositionListResponse
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
    position: Optional[str] = Query(None, description="职位过滤"),
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
    # 职位过滤
    if position and position.strip():
        query = query.filter(User.position == position.strip())
    
    # 角色过滤
    if role and role.strip():
        query = query.filter(User.role == role.strip())
    
    # 状态过滤
    if status and status.strip():
        if status.strip().lower() == "active":
            query = query.filter(User.is_active == True)
        elif status.strip().lower() == "inactive":
            query = query.filter(User.is_active == False)
    
    # 部门组织过滤
    if organization_name and organization_name.strip():
        from models.organization import Organization
        org_name = organization_name.strip()
        # 同时支持直接字段和关联表查询
        query = query.filter(
            or_(
                User.organization_name == org_name,
                User.organization.has(Organization.name == org_name)
            )
        )
    
    # 分页
    total, users = paginate_query(query, page, size)
    
    return list_response(
        records=[UserResponse.model_validate(user, from_attributes=True) for user in users],
        total=total,
        page=page,
        size=size,
        message="获取用户列表成功"
    )

# 获取职位列表
@router.get("/positions", response_model=BaseResponse)
async def get_positions(
    include_inactive: bool = Query(False, description="是否包含已停用的职位"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取所有职位列表"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")
    
    # 查询职位，可选择是否包含已停用的职位
    query = db.query(Position)
    if not include_inactive:
        query = query.filter(Position.is_active == True)
    
    positions = query.order_by(Position.name).all()
    
    # 统计每个职位的用户数量
    position_list = []
    for position in positions:
        user_count = db.query(User).filter(User.position == position.name).count()
        position_data = PositionListResponse(
            id=position.id,
            name=position.name,
            is_active=position.is_active,
            user_count=user_count
        )
        position_list.append(position_data.dict())
    
    return BaseResponse(
        message="获取职位列表成功",
        data=position_list
    )

# 新增职位
@router.post("/positions", response_model=BaseResponse)
async def create_position(
    position_data: PositionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """新增职位"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")
    
    # 检查职位名称是否已存在
    existing_position = db.query(Position).filter(Position.name == position_data.name).first()
    if existing_position:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="职位名称已存在"
        )
    
    # 创建新职位
    new_position = Position(
        name=position_data.name,
        description=position_data.description,
        is_active=position_data.is_active
    )
    
    db.add(new_position)
    db.commit()
    db.refresh(new_position)
    
    return BaseResponse(
        message="职位创建成功",
        data=PositionResponse.model_validate(new_position, from_attributes=True).dict()
    )

# 获取职位详情
@router.get("/positions/{position_id}", response_model=BaseResponse)
async def get_position(
    position_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取职位详情"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")
    
    # 查询职位
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="职位不存在"
        )
    
    return BaseResponse(
        message="获取职位详情成功",
        data=PositionResponse.model_validate(position, from_attributes=True).dict()
    )

# 更新职位
@router.put("/positions/{position_id}", response_model=BaseResponse)
async def update_position(
    position_id: str,
    position_data: PositionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """更新职位信息"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")
    
    # 查询职位
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="职位不存在"
        )
    
    # 检查职位名称是否已被其他职位使用
    if position_data.name and position_data.name != position.name:
        existing_position = db.query(Position).filter(
            Position.name == position_data.name,
            Position.id != position_id
        ).first()
        if existing_position:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="职位名称已存在"
            )
    
    # 更新职位信息
    update_data = position_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(position, key, value)
    
    db.commit()
    db.refresh(position)
    
    return BaseResponse(
        message="职位更新成功",
        data=PositionResponse.model_validate(position, from_attributes=True).dict()
    )

# 删除职位
@router.delete("/positions/{position_id}", response_model=BaseResponse)
async def delete_position(
    position_id: str,
    force: bool = Query(False, description="是否强制删除（即使有用户使用该职位）"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """删除职位"""
    # 权限校验
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="没有权限访问")
    
    # 查询职位
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="职位不存在"
        )
    
    # 检查是否有用户使用该职位
    user_count = db.query(User).filter(User.position == position.name).count()
    if user_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该职位正在被 {user_count} 个用户使用，无法删除。如需强制删除，请设置 force=true"
        )
    
    # 如果强制删除，将使用该职位的用户的职位字段设为空
    if force and user_count > 0:
        db.query(User).filter(User.position == position.name).update({"position": None})
    
    # 删除职位
    db.delete(position)
    db.commit()
    
    return BaseResponse(
        message="职位删除成功",
        data={"deleted_position_id": position_id, "affected_users": user_count if force else 0}
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
        position=user_data.position,  # type: ignore
        department=user_data.department,  # type: ignore
        organization_id=user_data.organization_id,  # type: ignore
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
    
    # 检查用户是否存在
    user = db.query(User).filter(User.id == actual_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    update_data = user_data.dict(exclude_unset=True)

    # 手机号唯一性检查
    if "phone" in update_data:
        existing_user = db.query(User).filter(
            User.phone == update_data["phone"],
            User.id == actual_user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被使用"
            )


    # 检查邮箱唯一性
    if "email" in update_data:
        existing_user = db.query(User).filter(
            User.email == update_data["email"],
            User.id != actual_user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被使用"
            )

    # 检查用户名唯一性
    if "username" in update_data:
        existing_user = db.query(User).filter(
            User.username == update_data["username"],
            User.id != actual_user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该用户名已被使用"
            )

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


