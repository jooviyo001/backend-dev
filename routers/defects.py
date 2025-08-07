from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc, or_
from typing import Optional, List
from datetime import date, datetime

from models.database import get_db
from models.models import Defect, User, Project, DefectStatus, DefectPriority, DefectType, DefectSeverity
from schemas import BaseResponse, PaginationResponse, DefectResponse, DefectCreate, DefectUpdate
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
    verified_by_id: Optional[str] = Query(None, description="验证人ID"),
    priority: Optional[DefectPriority] = Query(None, description="缺陷优先级"),
    type: Optional[DefectType] = Query(None, description="缺陷类型"),
    severity: Optional[DefectSeverity] = Query(None, description="缺陷严重程度"),
    parent_id: Optional[str] = Query(None, description="父缺陷ID"),
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
    
    # 验证人筛选
    if verified_by_id:
        query = query.filter(Defect.verified_by_id == verified_by_id)
    
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

# 新增缺陷
@router.post("/create", response_model=BaseResponse)
async def create_defect(
    defect: DefectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """创建新的缺陷"""
    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == defect.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查执行人是否存在
    assignee = db.query(User).filter(User.id == defect.assignee_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="执行人不存在")
    
    # 检查报告人是否存在
    reporter = db.query(User).filter(User.id == defect.reporter_id).first()
    if not reporter:
        raise HTTPException(status_code=404, detail="报告人不存在")
    
    # 检查验证人是否存在
    if defect.verified_by_id:
        verified_by = db.query(User).filter(User.id == defect.verified_by_id).first()
        if not verified_by:
            raise HTTPException(status_code=404, detail="验证人不存在")
    
    # 检查父缺陷是否存在
    if defect.parent_id:
        parent_defect = db.query(Defect).filter(Defect.id == defect.parent_id).first()
        if not parent_defect:
            raise HTTPException(status_code=404, detail="父缺陷不存在")
        # 检查父缺陷是否为子缺陷
        if parent_defect.type == DefectType.subdefect:
            raise HTTPException(status_code=400, detail="父缺陷不能为子缺陷")
        # 检查子缺陷是否为父缺陷
        if defect.type == DefectType.subdefect:
            raise HTTPException(status_code=400, detail="子缺陷不能为父缺陷")
        # 检查子缺陷是否为子缺陷
        if parent_defect.type == DefectType.subdefect:
            raise HTTPException(status_code=400, detail="子缺陷不能为子缺陷")
        # 检查子缺陷是否为缺陷
        if defect.type == DefectType.defect:
            raise HTTPException(status_code=400, detail="子缺陷不能为缺陷")
    return standard_response(
        data=DefectResponse.model_validate(defect, from_attributes=True),
        message="缺陷创建成功"
    )

# 获取单个缺陷详情
@router.get("/{defect_id}", response_model=BaseResponse)
async def get_defect_by_id(
    defect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:read"))
):
    """根据ID获取单个缺陷详情"""
    defect = db.query(Defect).options(
        joinedload(Defect.project),
        joinedload(Defect.assignee),
        joinedload(Defect.reporter)
    ).filter(Defect.id == defect_id).first()
    
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    
    return standard_response(
        data=DefectResponse.model_validate(defect, from_attributes=True),
        message="获取缺陷详情成功"
    )

# 更新缺陷
@router.put("/update/{defect_id}", response_model=BaseResponse)
async def update_defect(
    defect_id: str,
    defect: DefectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """更新缺陷"""
    # 检查缺陷是否存在
    existing_defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not existing_defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    
    # 更新缺陷字段
    for key, value in defect.model_dump(exclude_unset=True).items():
        setattr(existing_defect, key, value)
    
    # 记录更新人
    existing_defect.updated_by = current_user.id
    db.commit()
    db.refresh(existing_defect)
    return standard_response(
        data=DefectResponse.model_validate(existing_defect, from_attributes=True),
        message="缺陷更新成功"
    )

# 删除缺陷
@router.delete("/delete/{defect_id}", response_model=BaseResponse)
async def delete_defect(
    defect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """删除缺陷"""
    # 检查缺陷是否存在
    existing_defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not existing_defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    
    # 删除缺陷
    db.delete(existing_defect)
    db.commit()
    return standard_response(
        message="缺陷删除成功"
    )

# 批量更新缺陷
@router.put("/update/batch", response_model=BaseResponse)
async def batch_update_defects(
    defects: List[DefectUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """批量更新缺陷"""
    # 检查缺陷是否存在
    existing_defects = db.query(Defect).filter(Defect.id.in_([d.id for d in defects])).all()
    if len(existing_defects) != len(defects):
        raise HTTPException(status_code=400, detail="有缺陷不存在")
    # 检查父缺陷是否存在
    parent_ids = [d.parent_id for d in defects if d.parent_id]
    if parent_ids:
        parent_defects = db.query(Defect).filter(Defect.id.in_(parent_ids)).all()
        if len(parent_defects) != len(parent_ids):
            raise HTTPException(status_code=400, detail="有父缺陷不存在")
        # 检查父缺陷是否为子缺陷
        if any(d.type == DefectType.subdefect for d in parent_defects):
            raise HTTPException(status_code=400, detail="父缺陷不能为子缺陷")
        # 检查子缺陷是否为父缺陷
        if any(d.type == DefectType.defect for d in parent_defects):
            raise HTTPException(status_code=400, detail="子缺陷不能为父缺陷")
        # 检查子缺陷是否为子缺陷
        if any(d.type == DefectType.subdefect for d in parent_defects):
            raise HTTPException(status_code=400, detail="子缺陷不能为子缺陷")
        # 检查子缺陷是否为缺陷
        if any(d.type == DefectType.defect for d in parent_defects):
            raise HTTPException(status_code=400, detail="子缺陷不能为缺陷")
    # 更新缺陷
    for defect in existing_defects:
        for key, value in defect.model_dump(exclude_unset=True).items():
            setattr(defect, key, value)
        defect.updated_by = current_user.id
    db.commit()
    return standard_response(
        message="缺陷更新成功",
        data={
            "updated_count": len(existing_defects)
        }
    )   

# 批量删除
@router.delete("/delete/batch", response_model=BaseResponse)
async def batch_delete_defects(
    defect_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """批量删除缺陷"""
    # 检查缺陷是否存在
    existing_defects = db.query(Defect).filter(Defect.id.in_(defect_ids)).all()
    if len(existing_defects) != len(defect_ids):
        raise HTTPException(status_code=400, detail="有缺陷不存在")
    # 检查缺陷是否为子缺陷
    if any(d.type == DefectType.subdefect for d in existing_defects):
        raise HTTPException(status_code=400, detail="子缺陷不能删除")
    # 删除缺陷
    db.delete(existing_defects)
    db.commit()
    return standard_response(
        message="缺陷删除成功",
        data={
            "deleted_count": len(existing_defects)
        }
    )

# 导出缺陷
@router.get("/export", response_model=BaseResponse)
async def export_defects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:read"))
):
    """导出缺陷"""
    # 导出缺陷
    defects = db.query(Defect).all()
    return standard_response(
        message="缺陷导出成功",
        data={
            "defects": [DefectResponse.model_validate(d, from_attributes=True) for d in defects]
        }
    )
