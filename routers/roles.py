"""角色相关接口"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db
from models.user import User
from schemas.role import RoleCreate, RoleUpdate, RoleResponse, RoleListResponse
from schemas.base import BaseResponse
from services.role_service import get_role_service, RoleService
from utils.auth import require_permission
from utils.response_utils import standard_response, list_response
from utils.exceptions import BusinessException, ResourceNotFoundException, ValidationException

router = APIRouter()

# 创建角色
@router.post("/CreateRole", response_model=BaseResponse)
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:write"))
):
    """创建新角色"""
    try:
        role_service = get_role_service(db)
        new_role = role_service.create_role(role_data)
        
        return standard_response(
            message="角色创建成功",
            data=RoleResponse.model_validate(new_role).model_dump()
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建角色失败"
        )


# 获取所有角色
@router.get("/AllRoles", response_model=BaseResponse)
async def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色列表"""
    try:
        role_service = get_role_service(db)
        role_list = role_service.get_all_roles()
        
        return list_response(
            message="获取角色列表成功",
            records=role_list,
            total=len(role_list)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取角色列表失败"
        )


# 获取角色统计信息
@router.get("/stats", response_model=BaseResponse)
async def get_role_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色统计信息"""
    try:
        role_service = get_role_service(db)
        stats_data = role_service.get_role_stats()
        
        return standard_response(
            message="获取角色统计信息成功",
            data=stats_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取角色统计信息失败"
        )


# 获取角色详情
@router.get("/{role_id}", response_model=BaseResponse)
async def get_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色详情"""
    try:
        role_service = get_role_service(db)
        role = role_service.get_role_by_id(role_id)
        
        return standard_response(
            message="获取角色详情成功",
            data=RoleResponse.model_validate(role).model_dump()
        )
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取角色详情失败"
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
    try:
        role_service = get_role_service(db)
        updated_role = role_service.update_role(role_id, role_data)
        
        return standard_response(
            message="角色更新成功",
            data=RoleResponse.model_validate(updated_role).model_dump()
        )
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新角色失败"
        )


# 删除角色
@router.delete("/{role_id}", response_model=BaseResponse)
async def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete"))
):
    """删除角色"""
    try:
        role_service = get_role_service(db)
        role_service.delete_role(role_id)
        
        return standard_response(
            message="角色删除成功"
        )
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除角色失败"
        )

