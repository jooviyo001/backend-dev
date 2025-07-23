from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from math import ceil

from models.database import get_db
from models.models import Organization, User
from schemas.schemas import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse, 
    BaseResponse, PaginationResponse, UserResponse
)
from utils.auth import (
    get_current_active_user, require_permission
)

router = APIRouter()

# 组织列表
@router.get("/list", response_model=BaseResponse)
async def get_organizations(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    is_active: Optional[bool] = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:read"))
):
    """获取组织列表"""
    from utils.response_utils import list_response, paginate_query
    
    query = db.query(Organization)
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Organization.name.contains(keyword),
                Organization.description.contains(keyword)
            )
        )
    
    # 状态过滤
    if is_active is not None:
        query = query.filter(Organization.is_active == is_active)
    
    # 分页
    total, organizations = paginate_query(query, page, size)
    
    return list_response(
        items=[OrganizationResponse.from_orm(org) for org in organizations],
        total=total,
        page=page,
        size=size,
        message="获取组织列表成功"
    )

# 组织分页列表
@router.get("/page", response_model=BaseResponse)
async def get_organizations_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    is_active: Optional[bool] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:read"))
):
    """获取组织分页数据"""
    return await get_organizations(keyword, is_active, page, size, db, current_user)

@router.get("/{organization_id}", response_model=BaseResponse)
async def get_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:read"))
):
    """获取组织详情"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    return BaseResponse(
        message="获取组织详情成功",
        data=OrganizationResponse.from_orm(organization)
    )

# 组织创建
@router.post("/create", response_model=BaseResponse)
async def create_organization(
    organization_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """创建组织"""
    # 检查组织名是否已存在
    if db.query(Organization).filter(Organization.name == organization_data.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="组织名已存在"
        )
    
    # 创建新组织
    db_organization = Organization(
        name=organization_data.name,
        description=organization_data.description,
        website=organization_data.website
    )
    
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    
    # 将创建者添加为组织成员
    db_organization.members.append(current_user)
    db.commit()
    
    return BaseResponse(
        message="创建组织成功",
        data=OrganizationResponse.from_orm(db_organization)
    )

# 组织更新
@router.put("/{organization_id}", response_model=BaseResponse)
async def update_organization(
    organization_id: int,
    organization_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """更新组织信息"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 检查组织名是否已被其他组织使用
    if organization_data.name and organization_data.name != organization.name:
        existing_organization = db.query(Organization).filter(
            and_(Organization.name == organization_data.name, Organization.id != organization_id)
        ).first()
        if existing_organization:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="组织名已存在"
            )
    
    # 更新组织信息
    update_data = organization_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(organization, field, value)
    
    db.commit()
    db.refresh(organization)
    
    return BaseResponse(
        message="更新组织信息成功",
        data=OrganizationResponse.from_orm(organization)
    )

# 组织删除
@router.delete("/{organization_id}", response_model=BaseResponse)
async def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """删除组织"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    # 检查组织是否有关联的项目
    if organization.projects:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="组织下还有项目，无法删除"
        )
    
    db.delete(organization)
    db.commit()
    
    return BaseResponse(message="删除组织成功")

# 组织激活
@router.put("/{organization_id}/activate", response_model=BaseResponse)
async def activate_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """激活组织"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    organization.is_active = True
    db.commit()
    
    return BaseResponse(message="激活组织成功")

# 组织停用
@router.put("/{organization_id}/deactivate", response_model=BaseResponse)
async def deactivate_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """停用组织"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    organization.is_active = False
    db.commit()
    
    return BaseResponse(message="停用组织成功")

# 组织添加成员
@router.post("/{organization_id}/members/{user_id}", response_model=BaseResponse)
async def add_organization_member(
    organization_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """添加组织成员"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户是否已是组织成员
    if user in organization.members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户已是组织成员"
        )
    
    organization.members.append(user)
    db.commit()
    
    return BaseResponse(message="添加组织成员成功", data=UserResponse.from_orm(user))

# 组织移除成员
@router.delete("/{organization_id}/members/{user_id}", response_model=BaseResponse)
async def remove_organization_member(
    organization_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write"))
):
    """移除组织成员"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户是否是组织成员
    if user not in organization.members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不是组织成员"
        )
    
    organization.members.remove(user)
    db.commit()
    
    return BaseResponse(message="移除组织成员成功", data=UserResponse.from_orm(user))

# 组织获取成员列表
@router.get("/{organization_id}/members", response_model=BaseResponse)
async def get_organization_members(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:read"))
):
    """获取组织成员列表"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    return BaseResponse(
        message="获取组织成员成功",
        data=[UserResponse.from_orm(member) for member in organization.members]
    )

@router.get("/{organization_id}/projects", response_model=BaseResponse)
async def get_organization_projects(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:read"))
):
    """获取组织项目列表"""
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织不存在"
        )
    
    from schemas.schemas import ProjectResponse
    return BaseResponse(
        message="获取组织项目成功",
        data=[ProjectResponse.from_orm(project) for project in organization.projects]
    )