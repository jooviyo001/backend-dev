from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc, or_
from typing import Optional, List
from datetime import date, datetime

from models.database import get_db
from models.models import Defect, User, Project, DefectStatus, DefectPriority, DefectType, DefectSeverity
from schemas.schemas import BaseResponse, PaginationResponse, DefectResponse
from utils.auth import get_current_active_user, require_permission
from utils.response_utils import list_response, paginate_query, standard_response

router = APIRouter()

@router.get("/page", response_model=BaseResponse)
async def get_defects_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[DefectStatus] = Query(None, description="缺陷状态"),
    organization_id: Optional[str] = Query(None, description="组织ID"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    assignee_id: Optional[str] = Query(None, description="执行人ID"),
    reporter_id: Optional[str] = Query(None, description="报告人ID"),
    priority: Optional[DefectPriority] = Query(None, description="缺陷优先级"),
    type: Optional[DefectType] = Query(None, description="缺陷类型"),
    severity: Optional[DefectSeverity] = Query(None, description="缺陷严重程度"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("task:read"))
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
    # 查询缺陷表
    query = db.query(Defect)

    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Defect.title.contains(keyword),
                Defect.description.contains(keyword)
            )
        )
    
    # 状态筛选
    if status:
        query = query.filter(Defect.status == status)
    
    # 项目筛选
    if project_id:
        query = query.filter(Defect.project_id == project_id)
    
    # 执行人筛选
    if assignee_id:
        query = query.filter(Defect.assignee_id == assignee_id)
    
    # 报告人筛选
    if reporter_id:
        query = query.filter(Defect.reporter_id == reporter_id)
    
    # 优先级筛选
    if priority:
        query = query.filter(Defect.priority == priority)
    
    # 类型筛选
    if type:
        query = query.filter(Defect.type == type)
    
    # 严重程度筛选
    if severity:
        query = query.filter(Defect.severity == severity)
    
    # 日期范围筛选
    if start_date:
        query = query.filter(Defect.created_at >= start_date)
    if end_date:
        query = query.filter(Defect.created_at <= end_date)

    # 按创建时间倒序排列
    query = query.order_by(desc(Defect.created_at))

    # 分页查询
    total, defects = paginate_query(query, page, size)

    return list_response(
        records=[DefectResponse.model_validate(defect, from_attributes=True) for defect in defects],
        total=total,
        page=page,
        size=size,
        message="获取缺陷列表成功"
    )

#