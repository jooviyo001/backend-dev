"""角色相关接口"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.role import Role
from models.user import User
from schemas.role import RoleCreate, RoleUpdate, RoleResponse, RoleListResponse
from schemas.base import BaseResponse
from utils.auth import require_permission
from utils.response_utils import standard_response, list_response
from sqlalchemy import func

router = APIRouter()

# 创建角色
@router.post("/CreateRole", response_model=BaseResponse)

async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:write"))
):
    """创建新角色"""
    # 检查角色编码是否已存在
    existing_role = db.query(Role).filter(Role.code == role_data.code).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="角色编码已存在"
        )
    
    # 检查角色名称是否已存在
    existing_name = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="角色名称已存在"
        )
    
    # 创建新角色
    new_role = Role(
        code=role_data.code,
        name=role_data.name,
        description=role_data.description,
        is_active=role_data.is_active
    )
    
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    
    return standard_response(
        message="角色创建成功",
        data=RoleResponse.model_validate(new_role).model_dump()
    )


# 获取所有角色
@router.get("/AllRoles", response_model=BaseResponse)
async def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色列表"""
    roles = db.query(Role).all()
    
    # 统计每个角色的用户数量
    role_list = []
    for role in roles:
        user_count = db.query(User).filter(User.role_id == role.id).count()
        role_data = RoleListResponse.model_validate(role).model_dump()
        role_data["user_count"] = user_count
        role_list.append(role_data)
    
    return list_response(
        message="获取角色列表成功",
        records=role_list,
        total=len(role_list)
    )


# 获取角色统计信息
@router.get("/stats", response_model=BaseResponse)
async def get_role_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色统计信息"""
    # 总角色数
    total_roles = db.query(Role).count()
    
    # 启用角色数
    active_roles = db.query(Role).filter(Role.is_active == True).count()
    
    # 系统角色数（通过角色编码判断，系统角色通常有固定编码如ADMIN、USER、MANAGER等）
    system_role_codes = ['ADMIN', 'USER', 'MANAGER', 'VIEWER', 'EDITOR']
    system_roles = db.query(Role).filter(Role.code.in_(system_role_codes)).count()
    
    # 自定义角色数
    custom_roles = total_roles - system_roles
    
    stats_data = {
        "total_roles": total_roles,
        "active_roles": active_roles,
        "system_roles": system_roles,
        "custom_roles": custom_roles
    }
    
    return standard_response(
        message="获取角色统计信息成功",
        data=stats_data
    )


# 获取角色详情
@router.get("/{role_id}", response_model=BaseResponse)
async def get_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色详情"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    return standard_response(
        message="获取角色详情成功",
        data=RoleResponse.model_validate(role).model_dump()
    )


# 更新角色
@router.put("/{role_id}", response_model=BaseResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:write"))
):
    """更新角色信息"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 检查角色编码是否已被其他角色使用
    if role_data.code and role_data.code != role.code:
        existing_role = db.query(Role).filter(
            Role.code == role_data.code,
            Role.id != role_id
        ).first()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="角色编码已存在"
            )
    
    # 检查角色名称是否已被其他角色使用
    if role_data.name and role_data.name != role.name:
        existing_name = db.query(Role).filter(
            Role.name == role_data.name,
            Role.id != role_id
        ).first()
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="角色名称已存在"
            )
    
    # 更新角色信息
    update_data = role_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(role, field):
            setattr(role, field, value)
    
    db.commit()
    db.refresh(role)
    
    return standard_response(
        message="角色更新成功",
        data=RoleResponse.model_validate(role).model_dump()
    )


# 删除角色
@router.delete("/{role_id}", response_model=BaseResponse)
async def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete"))
):
    """删除角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 检查是否有用户正在使用该角色
    user_count = db.query(User).filter(User.role_id == role_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"无法删除角色，还有 {user_count} 个用户正在使用该角色"
        )
    
    db.delete(role)
    db.commit()
    
    return standard_response(message="角色删除成功")

