from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
import json

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.organization import Organization
from app.schemas.base import BaseResponse, PaginationParams, PaginationResponse

router = APIRouter()

# 组织相关的 Pydantic 模式
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class OrganizationType(str, Enum):
    COMPANY = "company"
    DEPARTMENT = "department"
    TEAM = "team"
    GROUP = "group"

class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="组织名称")
    description: Optional[str] = Field(None, max_length=500, description="组织描述")
    type: OrganizationType = Field(..., description="组织类型")
    parent_id: Optional[str] = Field(None, description="父组织ID")
    email: Optional[str] = Field(None, description="联系邮箱")
    phone: Optional[str] = Field(None, description="联系电话")
    address: Optional[str] = Field(None, description="地址")

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="组织名称")
    description: Optional[str] = Field(None, max_length=500, description="组织描述")
    type: Optional[OrganizationType] = Field(None, description="组织类型")
    parent_id: Optional[str] = Field(None, description="父组织ID")
    email: Optional[str] = Field(None, description="联系邮箱")
    phone: Optional[str] = Field(None, description="联系电话")
    address: Optional[str] = Field(None, description="地址")

class OrganizationResponse(OrganizationBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class OrganizationDetailResponse(OrganizationResponse):
    parent: Optional[dict] = None
    children: List[dict] = []
    members: List[dict] = []
    projects_count: int = 0

class OrganizationMemberAdd(BaseModel):
    user_ids: List[str] = Field(..., description="用户ID列表")

class OrganizationMemberRemove(BaseModel):
    user_ids: List[str] = Field(..., description="用户ID列表")

class OrganizationSearchParams(BaseModel):
    keyword: Optional[str] = Field(None, description="搜索关键词")
    type: Optional[OrganizationType] = Field(None, description="组织类型")
    parent_id: Optional[str] = Field(None, description="父组织ID")

@router.get("/", response_model=BaseResponse[PaginationResponse[OrganizationResponse]])
async def get_organizations(
    pagination: PaginationParams = Depends(),
    search: OrganizationSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:view"))
):
    """获取组织列表"""
    query = select(Organization)
    
    # 搜索条件
    if search.keyword:
        query = query.where(
            or_(
                Organization.name.contains(search.keyword),
                Organization.description.contains(search.keyword)
            )
        )
    
    if search.type:
        query = query.where(Organization.type == search.type)
    
    if search.parent_id:
        query = query.where(Organization.parent_id == search.parent_id)
    
    # 权限过滤：非管理员只能看到自己所在的组织
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Organization.members.any(User.id == current_user.id))
    
    # 总数查询
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页和排序
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    # 排序
    if pagination.sort:
        for sort_item in pagination.sort.split(','):
            if ':' in sort_item:
                field, direction = sort_item.split(':')
                if hasattr(Organization, field):
                    if direction.lower() == 'desc':
                        query = query.order_by(getattr(Organization, field).desc())
                    else:
                        query = query.order_by(getattr(Organization, field).asc())
    else:
        query = query.order_by(Organization.created_at.desc())
    
    # 执行查询
    result = await db.execute(query)
    organizations = result.scalars().all()
    
    # 计算分页信息
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_prev = pagination.page > 1
    
    return BaseResponse(
        data=PaginationResponse(
            items=[OrganizationResponse.from_orm(org) for org in organizations],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        ),
        message="获取成功"
    )

@router.post("/", response_model=BaseResponse[OrganizationResponse])
async def create_organization(
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:create"))
):
    """创建组织"""
    # 检查组织名称是否已存在
    existing_result = await db.execute(
        select(Organization).where(Organization.name == org_data.name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="组织名称已存在"
        )
    
    # 验证父组织是否存在
    if org_data.parent_id:
        parent_result = await db.execute(
            select(Organization).where(Organization.id == org_data.parent_id)
        )
        parent_org = parent_result.scalar_one_or_none()
        if not parent_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父组织不存在"
            )
    
    # 创建组织
    new_org = Organization(
        name=org_data.name,
        description=org_data.description,
        type=org_data.type,
        parent_id=org_data.parent_id,
        email=org_data.email,
        phone=org_data.phone,
        address=org_data.address
    )
    
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    
    return BaseResponse(
        data=OrganizationResponse.from_orm(new_org),
        message="组织创建成功"
    )

@router.get("/{org_id}", response_model=BaseResponse[OrganizationDetailResponse])
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:view"))
):
    """获取组织详情"""
    # 尝试从缓存获取
    cache_key = f"organization:{org_id}"
    cached_org = await redis_client.get(cache_key)
    if cached_org:
        return BaseResponse(
            data=OrganizationDetailResponse(**cached_org),
            message="获取成功"
        )
    
    # 从数据库获取
    query = select(Organization).options(
        selectinload(Organization.parent),
        selectinload(Organization.children),
        selectinload(Organization.members),
        selectinload(Organization.projects)
    ).where(Organization.id == org_id)
    
    result = await db.execute(query)
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        # 检查是否是组织成员
        is_member = any(member.id == current_user.id for member in org.members)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问此组织"
            )
    
    # 构建响应数据
    org_detail = OrganizationDetailResponse(
        **OrganizationResponse.from_orm(org).dict(),
        parent={
            "id": org.parent.id,
            "name": org.parent.name,
            "type": org.parent.type
        } if org.parent else None,
        children=[
            {
                "id": child.id,
                "name": child.name,
                "type": child.type
            } for child in org.children
        ],
        members=[
            {
                "id": member.id,
                "username": member.username,
                "name": member.name,
                "email": member.email,
                "role": member.role,
                "avatar": member.avatar
            } for member in org.members
        ],
        projects_count=len(org.projects)
    )
    
    # 缓存结果
    await redis_client.set(cache_key, org_detail.dict(), expire=3600)
    
    return BaseResponse(
        data=org_detail,
        message="获取成功"
    )

@router.put("/{org_id}", response_model=BaseResponse[OrganizationResponse])
async def update_organization(
    org_id: str,
    org_data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:edit"))
):
    """更新组织"""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 检查组织名称是否已存在（排除当前组织）
    if org_data.name and org_data.name != org.name:
        existing_result = await db.execute(
            select(Organization).where(
                and_(
                    Organization.name == org_data.name,
                    Organization.id != org_id
                )
            )
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="组织名称已存在"
            )
    
    # 验证新的父组织
    if org_data.parent_id and org_data.parent_id != org.parent_id:
        if org_data.parent_id == org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="组织不能设置自己为父组织"
            )
        
        parent_result = await db.execute(
            select(Organization).where(Organization.id == org_data.parent_id)
        )
        parent_org = parent_result.scalar_one_or_none()
        if not parent_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父组织不存在"
            )
    
    # 更新组织信息
    update_data = org_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)
    
    await db.commit()
    await db.refresh(org)
    
    # 清除缓存
    await redis_client.delete(f"organization:{org_id}")
    
    return BaseResponse(
        data=OrganizationResponse.from_orm(org),
        message="组织更新成功"
    )

@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:delete"))
):
    """删除组织"""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 检查是否有子组织
    children_result = await db.execute(
        select(func.count(Organization.id)).where(Organization.parent_id == org_id)
    )
    children_count = children_result.scalar()
    if children_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="存在子组织，无法删除"
        )
    
    # 检查是否有关联的项目
    from app.models.project import Project
    projects_result = await db.execute(
        select(func.count(Project.id)).where(Project.organization_id == org_id)
    )
    projects_count = projects_result.scalar()
    if projects_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="存在关联的项目，无法删除"
        )
    
    await db.delete(org)
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"organization:{org_id}")
    
    return BaseResponse(message="组织删除成功")

@router.post("/{org_id}/members", response_model=BaseResponse)
async def add_organization_members(
    org_id: str,
    member_data: OrganizationMemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:edit"))
):
    """添加组织成员"""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 验证用户是否存在
    users_result = await db.execute(
        select(User).where(User.id.in_(member_data.user_ids))
    )
    users = users_result.scalars().all()
    
    if len(users) != len(member_data.user_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部分用户不存在"
        )
    
    # 添加成员
    for user in users:
        if user not in org.members:
            org.members.append(user)
    
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"organization:{org_id}")
    
    return BaseResponse(message="成员添加成功")

@router.delete("/{org_id}/members", response_model=BaseResponse)
async def remove_organization_members(
    org_id: str,
    member_data: OrganizationMemberRemove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:edit"))
):
    """移除组织成员"""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 验证用户是否存在
    users_result = await db.execute(
        select(User).where(User.id.in_(member_data.user_ids))
    )
    users = users_result.scalars().all()
    
    # 移除成员
    for user in users:
        if user in org.members:
            org.members.remove(user)
    
    await db.commit()
    
    # 清除缓存
    await redis_client.delete(f"organization:{org_id}")
    
    return BaseResponse(message="成员移除成功")

@router.get("/tree", response_model=BaseResponse[List[dict]])
async def get_organization_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("organization:view"))
):
    """获取组织树结构"""
    # 检查缓存
    cache_key = f"organization_tree:{current_user.id}"
    cached_tree = await redis_client.get(cache_key)
    if cached_tree:
        return BaseResponse(
            data=cached_tree,
            message="获取成功"
        )
    
    # 获取所有组织
    query = select(Organization)
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Organization.members.any(User.id == current_user.id))
    
    result = await db.execute(query)
    organizations = result.scalars().all()
    
    # 构建树结构
    def build_tree(parent_id=None):
        tree = []
        for org in organizations:
            if org.parent_id == parent_id:
                node = {
                    "id": org.id,
                    "name": org.name,
                    "type": org.type,
                    "children": build_tree(org.id)
                }
                tree.append(node)
        return tree
    
    tree = build_tree()
    
    # 缓存结果
    await redis_client.set(cache_key, tree, expire=3600)
    
    return BaseResponse(
        data=tree,
        message="获取成功"
    )