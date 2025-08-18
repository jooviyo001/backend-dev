from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, and_, func
from typing import List, Optional
from datetime import datetime
import json

from models.database import get_db
from models.defect import Defect, DefectStatusHistory
from models.user import User
from models.project import Project
from models.enums import DefectStatus, DefectPriority, DefectType, DefectSeverity, UserRole
from schemas.base import BaseResponse
from schemas.defect import (
    DefectResponse, DefectCreate, DefectUpdate, DefectPageQuery,
    DefectStatusHistory as DefectStatusHistorySchema, DefectAssign
)
from services.defect_service import DefectService
from utils.auth import require_permission
from utils.response_utils import list_response, paginate_query, standard_response

router = APIRouter()

# 依赖注入：获取缺陷服务实例
def get_defect_service(db: Session = Depends(get_db)) -> DefectService:
    """获取缺陷服务实例"""
    return DefectService(db)

# 获取个人相关缺陷列表，不分页
@router.get("/list", response_model=BaseResponse)
async def get_my_defects(
    limit: int = Query(10, ge=1, le=100, description="返回数量限制"),
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:read"))
):
    """获取当前用户相关的缺陷列表"""
    defects = defect_service.get_my_defects(current_user, limit)
    
    return standard_response(
        data=[DefectResponse.model_validate(defect, from_attributes=True) for defect in defects],
        message="获取个人缺陷列表成功"
    )

# 新增看板
@router.get("/page", response_model=BaseResponse)
async def get_defects_page(
    query: DefectPageQuery = Depends(),
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:read"))
):
    """获取缺陷分页数据
    
    该接口专门用于查询缺陷表（Defect），支持多种筛选条件：
    - 关键词搜索（标题和描述）
    - 状态筛选
    - 组织、项目、执行人、报告人筛选
    - 优先级筛选
    - 类型和严重程度筛选
    - 日期范围筛选
    """ 
    # 使用服务层获取分页数据
    total, defects = defect_service.get_defects_page(query, current_user)

    return list_response(
        records=[DefectResponse.model_validate(defect, from_attributes=True) for defect in defects],
        total=total,
        page=query.page,
        size=query.size,
        message="获取缺陷列表成功"
    )

# 新增缺陷
@router.post("/create", response_model=BaseResponse)
async def create_defect(
    defect: DefectCreate,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:write"))
):
    """创建新的缺陷"""
    # 使用服务层创建缺陷
    created_defect = defect_service.create_defect(defect, current_user)
    
    # 重新查询缺陷以包含关联对象
    defect_with_relations = defect_service.get_defect_with_relations(created_defect.id)
    
    return standard_response(
        data=DefectResponse.model_validate(defect_with_relations, from_attributes=True),
        message="缺陷创建成功"
    )

# 缺陷统计接口
@router.get("/statistics", response_model=BaseResponse)
async def get_defects_statistics(
    project_id: Optional[str] = None,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:read"))
):
    """
    获取缺陷统计信息
    包括：总体统计、状态分布、优先级分布、类型分布、严重程度分布、趋势数据
    """
    # 使用服务层获取统计信息
    statistics = defect_service.get_defect_statistics(project_id, current_user)
    
    return standard_response(
        data=statistics,
        message="缺陷统计数据获取成功"
    )


# ==================== 基础CRUD接口 ====================

# 获取缺陷详情
@router.get("/{defect_id}", response_model=BaseResponse)
async def get_defect_detail(
    defect_id: str,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:read"))
):
    """获取缺陷详情"""
    defect = defect_service.get_defect_with_relations(defect_id)
    
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    
    # 权限检查
    if not defect_service.check_defect_permission(defect, current_user, "read"):
        raise HTTPException(status_code=403, detail="无权限查看此缺陷")
    
    return standard_response(
        data=DefectResponse.model_validate(defect, from_attributes=True),
        message="获取缺陷详情成功"
    )


# 更新缺陷
@router.put("/update/{defect_id}", response_model=BaseResponse)
async def update_defect(
    defect_id: str,
    defect_update: DefectUpdate,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:write"))
):
    """更新缺陷信息"""
    updated_defect = defect_service.update_defect(defect_id, defect_update, current_user)
    
    # 重新查询缺陷以包含关联对象
    defect_with_relations = defect_service.get_defect_with_relations(defect_id)
    
    return standard_response(
        data=DefectResponse.model_validate(defect_with_relations, from_attributes=True),
        message="缺陷更新成功"
    )


# 删除缺陷
@router.delete("/{defect_id}", response_model=BaseResponse)
async def delete_defect(
    defect_id: str,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:write"))
):
    """删除缺陷（软删除）"""
    defect_service.delete_defect(defect_id, current_user)
    
    return standard_response(
        data={"id": defect_id, "deleted": True},
        message="缺陷删除成功"
    )


# ==================== 状态管理和工作流接口 ====================

# 变更缺陷状态
@router.put("/{defect_id}/status", response_model=BaseResponse)
async def change_defect_status(
    defect_id: str,
    new_status: DefectStatus,
    comment: Optional[str] = None,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:write"))
):
    """变更缺陷状态"""
    # 使用服务层变更状态
    defect_service.change_defect_status(defect_id, new_status, current_user, comment)
    
    # 重新查询缺陷以包含关联对象
    updated_defect = defect_service.get_defect_with_relations(defect_id)
    
    return standard_response(
        data=DefectResponse.model_validate(updated_defect, from_attributes=True),
        message=f"缺陷状态已变更为 {new_status.value}"
    )


# 获取缺陷状态历史
@router.get("/{defect_id}/history", response_model=BaseResponse)
async def get_defect_status_history(
    defect_id: str,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:read"))
):
    """获取缺陷状态变更历史"""
    # 使用服务层获取状态历史
    history_records = defect_service.get_defect_status_history(defect_id, current_user)
    
    return standard_response(
        data=[DefectStatusHistorySchema.model_validate(record, from_attributes=True) for record in history_records],
        message="获取缺陷状态历史成功"
    )


# 分配缺陷
@router.put("/{defect_id}/assign", response_model=BaseResponse)
async def assign_defect(
    defect_id: str,
    assign_data: DefectAssign,
    defect_service: DefectService = Depends(get_defect_service),
    current_user: User = Depends(require_permission("defect:assign"))
):
    """分配缺陷给执行人"""
    # 使用服务层分配缺陷
    defect_service.assign_defect(defect_id, assign_data, current_user)
    
    # 重新查询缺陷以包含关联对象
    updated_defect = defect_service.get_defect_with_relations(defect_id)
    
    return standard_response(
        data=DefectResponse.model_validate(updated_defect, from_attributes=True),
        message="缺陷分配成功"
    )