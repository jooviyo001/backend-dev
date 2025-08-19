from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from models.database import get_db
from models.position import Position
from models.user import User
from schemas.base import BaseResponse
from schemas.positions import (
    PositionCreate, PositionUpdate, PositionResponse
)
from utils.auth import require_permission
from utils.response_utils import success_response, error_response

router = APIRouter()


@router.get("/positionPage", response_model=BaseResponse)
async def get_positions(
    include_inactive: bool = Query(False, description="是否包含已停用的职位"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取职位列表"""
    try:
        # 构建查询
        query = db.query(Position)
        
        # 是否包含已停用的职位
        if not include_inactive:
            query = query.filter(Position.is_active == True)
        
        # 搜索过滤
        if search and search.strip():
            search_term = search.strip()
            query = query.filter(
                or_(
                    Position.name.contains(search_term),
                    Position.description.contains(search_term)
                )
            )
        
        # 计算总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * limit
        positions = query.offset(offset).limit(limit).all()
        
        # 转换为响应格式
        position_list = []
        for position in positions:
            # 统计使用该职位的用户数量
            user_count = db.query(User).filter(User.position_id == position.id).count()
            
            position_data = {
                "id": position.id,
                "code": position.code,
                "name": position.name,
                "department_id": position.department_id,
                "department": None,  # 可以后续添加组织名称查询
                "level": position.level,
                "description": position.description,
                "is_active": position.is_active,
                "created_at": position.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": position.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "user_count": user_count,
            }
            position_list.append(position_data)
        
        return success_response(
            data={
                "records": position_list,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": (total + limit - 1) // limit
            },
            message="获取职位列表成功"
        )
    
    except Exception as e:
        return error_response(message=f"获取职位列表失败: {str(e)}")


@router.post("/add", response_model=BaseResponse)
async def create_position(
    position_data: PositionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """创建职位"""
    try:
        # 检查职位名称是否已存在
        existing_position = db.query(Position).filter(Position.name == position_data.name).first()
        if existing_position:
            return success_response(
                message="职位名称已存在",
                code="200002"
            )
        
        # 创建新职位
        new_position = Position(
            code=position_data.code,
            name=position_data.name,
            description=position_data.description,
            department_id=position_data.department_id,
            is_active=position_data.is_active
        )
        
        db.add(new_position)
        db.commit()
        db.refresh(new_position)
        
        # 构建响应数据
        position_data = {
            "id": new_position.id,
            "name": new_position.name,
            "code": new_position.code,
            "department_id": new_position.department_id,
            "department": new_position.department,
            "level": new_position.level,
            "is_active": new_position.is_active,
            "description": new_position.description,
            "created_at": new_position.created_at,
            "updated_at": new_position.updated_at
        }
        
        return success_response(
            data=position_data,
            message="职位创建成功"
        )
    
    except Exception as e:
        db.rollback()
        return error_response(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"创建职位失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{position_id}", response_model=BaseResponse)
async def get_position(
    position_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取职位详情"""
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return error_response(
                code=status.HTTP_404_NOT_FOUND,
                message="职位不存在",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 统计使用该职位的用户数量
        user_count = db.query(User).filter(User.position_id == position.id).count()
        
        # 构建响应数据
        position_data = {
            "id": position.id,
            "name": position.name,
            "code": position.code,
            "department_id": position.department_id,
            "department": position.department,
            "level": position.level,
            "is_active": position.is_active,
            "description": position.description,
            "created_at": position.created_at,
            "updated_at": position.updated_at,
            "user_count": user_count,
            "created_by": position.created_by,
            "updated_by": position.updated_by,
        }
        
        return success_response(
            data=position_data,
            message="获取职位详情成功"
        )
    
    except Exception as e:
        return error_response(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"获取职位详情失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.put("/{position_id}", response_model=BaseResponse)
async def update_position(
    position_id: str,
    position_data: PositionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """更新职位"""
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return error_response(
                code=status.HTTP_404_NOT_FOUND,
                message="职位不存在",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 检查职位名称是否已被其他职位使用
        if position_data.name and position_data.name != position.name:
            existing_position = db.query(Position).filter(
                Position.name == position_data.name,
                Position.id != position_id
            ).first()
            if existing_position:
                return error_response(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="职位名称已存在",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # 更新职位信息
        update_data = position_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(position, field, value)
        
        db.commit()
        db.refresh(position)
        
        # 构建响应数据
        position_data = {
            "id": position.id,
            "name": position.name,
            "code": position.code,
            "department_id": position.department_id,
            "department": position.department,
            "level": position.level,
            "is_active": position.is_active,
            "description": position.description,
            "created_at": position.created_at,
            "updated_at": position.updated_at
        }
    
        return success_response(
            data=position_data,
            message="职位更新成功"
        )
    
    except Exception as e:
        db.rollback()
        return error_response(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"更新职位失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/{position_id}", response_model=BaseResponse)
async def delete_position(
    position_id: str,
    force: bool = Query(False, description="是否强制删除（即使有用户使用该职位）"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """删除职位"""
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return error_response(
                code=status.HTTP_404_NOT_FOUND,
                message="职位不存在",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 检查是否有用户使用该职位
        user_count = db.query(User).filter(User.position_id == position.id).count()
        if user_count > 0 and not force:
            return error_response(
                code=status.HTTP_400_BAD_REQUEST,
                message=f"该职位正在被 {user_count} 个用户使用，无法删除。如需强制删除，请使用 force=true 参数",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # 如果强制删除，先将使用该职位的用户的职位设为空
        if force and user_count > 0:
            db.query(User).filter(User.position_id == position.id).update({User.position_id: None})
        
        # 删除职位
        db.delete(position)
        db.commit()
        
        return success_response(
            message=f"职位删除成功{f'，已清除 {user_count} 个用户的职位关联' if force and user_count > 0 else ''}"
        )
    
    except Exception as e:
        db.rollback()
        return error_response(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"删除职位失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.patch("/{position_id}/status", response_model=BaseResponse)
async def toggle_position_status(
    position_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:write"))
):
    """切换职位启用/停用状态"""
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return error_response(
                code=status.HTTP_404_NOT_FOUND,
                message="职位不存在",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 检查是否有用户使用该职位
        user_count = db.query(User).filter(User.position_id == position.id).count()
        if user_count > 0:
            return error_response(
                code=status.HTTP_400_BAD_REQUEST,
                message=f"该职位正在被 {user_count} 个用户使用，无法停用。如需停用，请先删除关联用户",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # 切换状态
        position.is_active = not position.is_active
        db.commit()
        db.refresh(position)
        
        status_text = "启用" if position.is_active else "停用"
        return success_response(
            data=PositionResponse.model_validate(position),
            message=f"职位{status_text}成功"
        )
    
    except Exception as e:
        db.rollback()
        return error_response(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"切换职位状态失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/statistics/summary", response_model=BaseResponse)
async def get_position_statistics(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("user:read"))
):
    """获取职位统计信息"""
    try:
        # 总职位数
        total_positions = db.query(Position).count()
        
        # 启用的职位数
        active_positions = db.query(Position).filter(Position.is_active == True).count()
        
        # 停用的职位数
        inactive_positions = total_positions - active_positions
        
        # 有用户的职位数
        positions_with_users = db.query(Position).join(User, Position.id == User.position_id).distinct().count()
        
        # 无用户的职位数
        positions_without_users = total_positions - positions_with_users
        
        return success_response(
            data={
                "total_positions": total_positions,
                "active_positions": active_positions,
                "inactive_positions": inactive_positions,
                "positions_with_users": positions_with_users,
                "positions_without_users": positions_without_users
            },
            message="获取职位统计信息成功"
        )
    
    except Exception as e:
        return error_response(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"获取职位统计信息失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
