from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission, get_password_hash
from app.core.redis_client import redis_client
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserStatistics, 
    BatchUserCreate, UserSearchParams, UserRole, UserStatus
)
from app.schemas.base import BaseResponse, PaginationParams, PaginationResponse, BatchOperationResponse
from app.core.config import settings

router = APIRouter()

@router.get("/", response_model=BaseResponse[PaginationResponse[UserResponse]])
async def get_users(
    pagination: PaginationParams = Depends(),
    search: UserSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:view"))
):
    """获取用户列表"""
    # 构建查询条件
    query = select(User)
    
    # 搜索条件
    if search.keyword:
        query = query.where(
            or_(
                User.username.contains(search.keyword),
                User.name.contains(search.keyword),
                User.email.contains(search.keyword)
            )
        )
    
    if search.role:
        query = query.where(User.role == search.role)
    
    if search.status:
        query = query.where(User.status == search.status)
    
    if search.department:
        query = query.where(User.department == search.department)
    
    # 总数查询
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页和排序
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    # 排序
    if pagination.sort:
        # 解析排序参数: field1:asc,field2:desc
        for sort_item in pagination.sort.split(','):
            if ':' in sort_item:
                field, direction = sort_item.split(':')
                if hasattr(User, field):
                    if direction.lower() == 'desc':
                        query = query.order_by(getattr(User, field).desc())
                    else:
                        query = query.order_by(getattr(User, field).asc())
    else:
        query = query.order_by(User.created_at.desc())
    
    # 执行查询
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 计算分页信息
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_prev = pagination.page > 1
    
    return BaseResponse(
        data=PaginationResponse(
            items=[UserResponse.from_orm(user) for user in users],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        ),
        message="获取成功"
    )

@router.post("/", response_model=BaseResponse[UserResponse])
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:create"))
):
    """创建用户"""
    # 检查用户名和邮箱是否已存在
    result = await db.execute(
        select(User).where(
            or_(User.username == user_data.username, User.email == user_data.email)
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
        status=user_data.status
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return BaseResponse(
        data=UserResponse.from_orm(new_user),
        message="用户创建成功"
    )

@router.get("/{user_id}", response_model=BaseResponse[UserResponse])
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:view"))
):
    """获取用户详情"""
    # 先从缓存获取
    cached_user = await redis_client.get(f"user:{user_id}")
    if cached_user:
        return BaseResponse(
            data=UserResponse(**cached_user),
            message="获取成功"
        )
    
    # 从数据库获取
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 缓存用户信息
    user_dict = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "avatar": user.avatar,
        "department": user.department,
        "position": user.position,
        "phone": user.phone,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat()
    }
    await redis_client.set(f"user:{user_id}", user_dict, expire=1800)
    
    return BaseResponse(
        data=UserResponse.from_orm(user),
        message="获取成功"
    )

@router.put("/{user_id}", response_model=BaseResponse[UserResponse])
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:edit"))
):
    """更新用户信息"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户名和邮箱唯一性
    if user_data.username and user_data.username != user.username:
        result = await db.execute(
            select(User).where(and_(User.username == user_data.username, User.id != user_id))
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
    
    if user_data.email and user_data.email != user.email:
        result = await db.execute(
            select(User).where(and_(User.email == user_data.email, User.id != user_id))
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )
    
    # 更新用户信息
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    # 清除缓存
    await redis_client.delete(f"user:{user_id}")
    
    return BaseResponse(
        data=UserResponse.from_orm(user),
        message="用户更新成功"
    )

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:delete"))
):
    """删除用户"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    await db.delete(user)
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"user:{user_id}")
    
    return BaseResponse(message="用户删除成功")

@router.get("/statistics", response_model=BaseResponse[UserStatistics])
async def get_user_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:view"))
):
    """获取用户统计信息"""
    # 检查缓存
    cached_stats = await redis_client.get("user_statistics")
    if cached_stats:
        return BaseResponse(
            data=UserStatistics(**cached_stats),
            message="获取成功"
        )
    
    # 总用户数
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar()
    
    # 按角色统计
    role_result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    by_role = {role: count for role, count in role_result.all()}
    
    # 按状态统计
    status_result = await db.execute(
        select(User.status, func.count(User.id)).group_by(User.status)
    )
    by_status = {status: count for status, count in status_result.all()}
    
    # 按部门统计
    dept_result = await db.execute(
        select(User.department, func.count(User.id))
        .where(User.department.isnot(None))
        .group_by(User.department)
    )
    by_department = {dept: count for dept, count in dept_result.all()}
    
    # 活跃用户数
    active_result = await db.execute(
        select(func.count(User.id)).where(User.status == "active")
    )
    active_users = active_result.scalar()
    
    # 本月新用户
    this_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_users_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= this_month)
    )
    new_users_this_month = new_users_result.scalar()
    
    # 最近登录用户（7天内）
    week_ago = datetime.now() - timedelta(days=7)
    last_login_result = await db.execute(
        select(func.count(User.id)).where(User.last_login >= week_ago)
    )
    last_login_users = last_login_result.scalar()
    
    stats = UserStatistics(
        total=total,
        by_role=by_role,
        by_status=by_status,
        by_department=by_department,
        active_users=active_users,
        new_users_this_month=new_users_this_month,
        last_login_users=last_login_users
    )
    
    # 缓存统计数据
    await redis_client.set("user_statistics", stats.dict(), expire=3600)
    
    return BaseResponse(
        data=stats,
        message="获取成功"
    )

@router.post("/batch", response_model=BaseResponse[BatchOperationResponse])
async def batch_create_users(
    batch_data: BatchUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("user:create"))
):
    """批量创建用户"""
    success_count = 0
    failed_count = 0
    success_ids = []
    failed_items = []
    
    for user_data in batch_data.users:
        try:
            # 检查用户名和邮箱是否已存在
            result = await db.execute(
                select(User).where(
                    or_(User.username == user_data.username, User.email == user_data.email)
                )
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                failed_count += 1
                failed_items.append({
                    "username": user_data.username,
                    "error": "用户名或邮箱已存在"
                })
                continue
            
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
                status=user_data.status
            )
            
            db.add(new_user)
            await db.flush()  # 获取ID但不提交
            
            success_count += 1
            success_ids.append(new_user.id)
            
        except Exception as e:
            failed_count += 1
            failed_items.append({
                "username": user_data.username,
                "error": str(e)
            })
    
    await db.commit()
    
    return BaseResponse(
        data=BatchOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            success_ids=success_ids,
            failed_items=failed_items,
            total=len(batch_data.users)
        ),
        message=f"批量创建完成，成功{success_count}个，失败{failed_count}个"
    )