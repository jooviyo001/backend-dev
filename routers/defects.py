from fastapi import APIRouter, Depends, Query, HTTPException, File, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, and_
from typing import  List
from datetime import datetime

import pandas as pd
import io

from models.database import get_db
from models.defect import Defect, DefectStatusHistory, DefectStatus, DefectType
from models.user import User
from models.project import Project
from models.associations import MemberRole
from models.enums import UserRole
from schemas.base import BaseResponse
from schemas.defect import DefectResponse, DefectCreate, DefectUpdate, DefectAssign, DefectStatusHistory as DefectStatusHistorySchema, DefectPageQuery

from utils.auth import require_permission
from utils.response_utils import list_response, paginate_query, standard_response

router = APIRouter()

# 新增根据用户ID查看个人缺陷列表，不分页
@router.get("/list", response_model=BaseResponse)
async def get_defects_by_user_id(
    user_id: str,
    limit: int = Query(5, ge=1, le=100, description="返回数量限制"),
    db: Session = Depends(get_db)):
    """获取缺陷列表限制100个"""
    defects = Query(db).filter(Defect.user_id == user_id).limit(limit).all()
    return BaseResponse(data=defects)

# 新增看板
@router.get("/page", response_model=BaseResponse)
async def get_defects_page(
    query: DefectPageQuery = Depends(),
    db: Session = Depends(get_db),
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
    # 查询缺陷表
    db_query = db.query(Defect)
    
    # 根据用户角色进行数据过滤
    # 如果不是管理员，只能查看自己相关的缺陷（创建的、分配给自己的、报告的、验证的）
    if current_user.role != MemberRole.ADMIN: # type: ignore
        db_query = db_query.filter(
            or_(
                Defect.created_by == current_user.id,
                Defect.assignee_id == current_user.id,
                Defect.reporter_id == current_user.id,
                Defect.verified_by_id == current_user.id
            )
        )

    # 关键词搜索
    if query.keyword:
        db_query = db_query.filter(
            or_(
                Defect.title.contains(query.keyword),
                Defect.description.contains(query.keyword)
            )
        )
    
    # 状态筛选,支持多个状态
    if query.status:
        db_query = db_query.filter(Defect.status.in_(query.status))
    
    # 项目筛选
    if query.project_id:
        db_query = db_query.filter(Defect.project_id == query.project_id)
    
    # 当前责任人筛选
    if query.assignee_id:
        db_query = db_query.filter(Defect.assignee_id == query.assignee_id)
    
    # 报告人筛选
    if query.reporter_id:
        db_query = db_query.filter(Defect.reporter_id == query.reporter_id)
    
    # 验证人筛选
    if query.verified_by_id:
        db_query = db_query.filter(Defect.verified_by_id == query.verified_by_id)
    
    # 优先级筛选
    if query.priority:
        db_query = db_query.filter(Defect.priority == query.priority)
    
    # 类型筛选
    if query.type:
        db_query = db_query.filter(Defect.type == query.type)
    
    # 严重程度筛选
    if query.severity:
        db_query = db_query.filter(Defect.severity == query.severity)
    
    # 父缺陷筛选
    if query.parent_id:
        db_query = db_query.filter(Defect.parent_id == query.parent_id)
    
    # 日期范围筛选
    if query.start_date:
        db_query = db_query.filter(Defect.created_at >= query.start_date)
    if query.end_date:
        db_query = db_query.filter(Defect.created_at <= query.end_date)
    
    # 只显示我的缺陷
    if query.only_my_defects:
        db_query = db_query.filter(
            or_(
                Defect.created_by == current_user.id,
                Defect.assignee_id == current_user.id,
                Defect.reporter_id == current_user.id,
                Defect.verified_by_id == current_user.id
            )
        )
    
    # 只显示逾期缺陷
    if query.only_overdue:
        from datetime import datetime
        current_time = datetime.now()
        db_query = db_query.filter(
            and_(
                Defect.due_date.isnot(None),
                Defect.due_date < current_time,
                Defect.status.notin_([DefectStatus.CLOSED, DefectStatus.RESOLVED])
            )
        )
    
    # 只显示未分配缺陷
    if query.only_unassigned:
        db_query = db_query.filter(Defect.assignee_id.is_(None))

    # 按创建时间倒序排列
    db_query = db_query.order_by(desc(Defect.created_at))

    # 分页查询
    total, defects = paginate_query(db_query, query.page, query.size)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """创建新的缺陷"""
    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == defect.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查执行人是否存在（如果提供了执行人ID）
    if defect.assignee_id:
        assignee = db.query(User).filter(User.id == defect.assignee_id).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="执行人不存在")
    
    # 检查报告人是否存在（如果提供了报告人ID）
    if defect.reporter_id:
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
        if parent_defect.type == DefectType.BUG:
            raise HTTPException(status_code=400, detail="父缺陷不能为子缺陷")
        # 检查子缺陷是否为父缺陷
        if defect.type == DefectType.BUG:
            raise HTTPException(status_code=400, detail="子缺陷不能为父缺陷")
        # 检查子缺陷是否为子缺陷
        if parent_defect.type == DefectType.BUG:
            raise HTTPException(status_code=400, detail="子缺陷不能为子缺陷")
        # 检查子缺陷是否为缺陷
        if defect.type == DefectType.BUG:
            raise HTTPException(status_code=400, detail="子缺陷不能为缺陷")
    
    # 创建缺陷对象
    defect_data = defect.model_dump()
    # 将tags列表转换为JSON字符串
    if defect_data.get('tags'):
        import json
        defect_data['tags'] = json.dumps(defect_data['tags'], ensure_ascii=False)
    
    db_defect = Defect(**defect_data)
    # 设置创建人为当前用户
    db_defect.created_by = current_user.id
    db_defect.updated_by = current_user.id
    
    # 保存到数据库
    db.add(db_defect)
    db.commit()
    db.refresh(db_defect)
    
    # 创建初始状态历史记录
    initial_status_history = DefectStatusHistory(
        defect_id=db_defect.id,
        old_status=None,  # 创建时没有旧状态
        new_status=db_defect.status,
        changed_by=current_user.id,
        comment=f"缺陷创建，初始状态为 {db_defect.status.value}"
    )
    db.add(initial_status_history)
    db.commit()
    
    return standard_response(
        data=DefectResponse.model_validate(db_defect, from_attributes=True),
        message="缺陷创建成功"
    )



# 缺陷统计接口
@router.get("/statistics", response_model=BaseResponse)
async def get_defect_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:read"))
):
    """获取缺陷统计数据"""
    # 构建查询
    query = db.query(Defect)
    # 权限过滤：非管理员只能查看自己相关的缺陷
    if current_user.role != UserRole.ADMIN:
        query = query.filter(
            or_(
                Defect.created_by == current_user.id,
                Defect.assignee_id == current_user.id,
                Defect.reporter_id == current_user.id,
                Defect.verified_by_id == current_user.id
            )
        )
    # 统计数据，全部缺陷
    total_count = query.count()

    # 未解决缺陷统计
    unresolved_count = query.filter(Defect.status.in_([
        DefectStatus.NEW, DefectStatus.ASSIGNED, DefectStatus.IN_PROGRESS, DefectStatus.REOPENED
        ])).count()
    # 已解决缺陷统计
    resolved_count = query.filter(
        Defect.status.in_(
            [DefectStatus.RESOLVED, DefectStatus.VERIFIED, DefectStatus.CLOSED]
            )
    ).count()
    # 所有逾期缺陷统计
    overdue_count = query.filter(
        Defect.status.in_([
            DefectStatus.NEW, DefectStatus.ASSIGNED, DefectStatus.IN_PROGRESS, DefectStatus.REOPENED
            ]),
        Defect.due_date < datetime.now()
    ).count()
    # 高优先级缺陷统计只包括（high、critical）
    high_priority_count = query.filter(
        Defect.priority.in_([DefectPriority.HIGH, DefectPriority.CRITICAL])
    ).count()

    # 我的缺陷统计
    my_count = query.filter(
        Defect.assignee_id == current_user.id
    ).count()

    # 未分配缺陷统计
    unassigned_count = query.filter(
        Defect.assignee_id == None
    ).count()


    return standard_response(
        message="缺陷统计数据获取成功",
        data={
            "total_count": total_count,  # 全部缺陷
            "unresolved_count": unresolved_count,  # 未解决缺陷
            "resolved_count": resolved_count,  # 已解决缺陷
            "overdue_count": overdue_count,  # 所有逾期缺陷
            "unassigned_count": unassigned_count,  # 未分配缺陷
            "high_priority_count": high_priority_count,  # 高优先级缺陷
            "my_count": my_count,  # 我的缺陷
        }
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
    
    # 权限检查：非管理员只能查看自己相关的缺陷
    if current_user.role != UserRole.ADMIN:
        if not (
            defect.created_by == current_user.id or
            defect.assignee_id == current_user.id or
            defect.reporter_id == current_user.id or
            defect.verified_by_id == current_user.id
        ):
            raise HTTPException(status_code=403, detail="权限不足，无法查看此缺陷")
    
    return standard_response(
        data=DefectResponse.model_validate(defect, from_attributes=True),
        message="获取缺陷详情成功"
    )

# 获取缺陷状态历史
@router.get("/{defect_id}/status-history", response_model=BaseResponse)
async def get_defect_status_history(
    defect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:read"))
):
    """获取缺陷状态历史记录"""
    # 检查缺陷是否存在
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    
    # 权限检查：非管理员只能查看自己相关的缺陷
    if current_user.role != UserRole.ADMIN:
        if not (
            defect.created_by == current_user.id or
            defect.assignee_id == current_user.id or
            defect.reporter_id == current_user.id or
            defect.verified_by_id == current_user.id
        ):
            raise HTTPException(status_code=403, detail="权限不足，无法查看此缺陷的状态历史")
    
    # 从状态历史表中查询真实的状态变更记录
    history_records = db.query(DefectStatusHistory).options(
        joinedload(DefectStatusHistory.changed_by_user)
    ).filter(
        DefectStatusHistory.defect_id == defect_id
    ).order_by(DefectStatusHistory.changed_at.asc()).all()
    
    # 转换为响应格式
    history_data = []
    for record in history_records:
        history_data.append(DefectStatusHistorySchema(
            status=record.new_status,
            changed_at=record.changed_at,
            changed_by=record.changed_by,
            changed_by_name=record.changed_by_user.name if record.changed_by_user else None,
            comment=record.comment
        ))
    
    return standard_response(
        data=history_data,
        message="获取缺陷状态历史成功"
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
    
    # 权限检查：非管理员只能更新自己相关的缺陷
    if current_user.role != UserRole.ADMIN:
        if not (
            existing_defect.created_by == current_user.id or
            existing_defect.assignee_id == current_user.id or
            existing_defect.reporter_id == current_user.id
        ):
            raise HTTPException(status_code=403, detail="权限不足，无法更新此缺陷")
    
    # 记录原始状态，用于状态历史记录
    old_status = existing_defect.status
    
    # 更新缺陷字段
    update_data = defect.model_dump(exclude_unset=True)
    
    # 处理tags字段，转换为JSON字符串
    if 'tags' in update_data and update_data['tags'] is not None:
        import json
        update_data['tags'] = json.dumps(update_data['tags'], ensure_ascii=False)
    
    for key, value in update_data.items():
        setattr(existing_defect, key, value)
    
    # 如果更新了handler_id，需要同时更新handler_name
    if 'handler_id' in update_data and update_data['handler_id'] is not None:
        handler = db.query(User).filter(User.id == update_data['handler_id']).first()
        if handler:
            existing_defect.handler_name = handler.name
        else:
            raise HTTPException(status_code=404, detail="处理人不存在")
    
    # 如果状态发生变化，记录状态历史
    if 'status' in update_data and update_data['status'] != old_status:
        status_history = DefectStatusHistory(
            defect_id=defect_id,
            old_status=old_status,
            new_status=update_data['status'],
            changed_by=current_user.id,
            comment=f"状态从 {old_status.value} 变更为 {update_data['status'].value}"
        )
        db.add(status_history)
    
    # 设置更新者
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
    
    # 权限检查：只有创建人或管理员才能删除
    if current_user.role != MemberRole.ADMIN and current_user.id != existing_defect.created_by:
        raise HTTPException(status_code=403, detail="权限不足，只有创建人或管理员才能删除缺陷")
    
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
    defect_ids = []
    for d in defects:
        if hasattr(d, 'id') and getattr(d, 'id'):
            defect_ids.append(getattr(d, 'id'))
    if not defect_ids:
        raise HTTPException(status_code=400, detail="缺陷ID不能为空")
    
    existing_defects = db.query(Defect).filter(Defect.id.in_(defect_ids)).all()
    if len(existing_defects) != len(defect_ids):
        raise HTTPException(status_code=400, detail="有缺陷不存在")
    
    # 权限检查：非管理员只能更新自己相关的缺陷
    if current_user.role != MemberRole.admin:
        for defect in existing_defects:
            if not (defect.created_by == current_user.id or 
                    defect.assignee_id == current_user.id or 
                    defect.reporter_id == current_user.id):
                raise HTTPException(status_code=403, detail=f"权限不足，无法更新缺陷 {defect.id}")
    # 检查父缺陷是否存在
    parent_ids = [d.parent_id for d in defects if d.parent_id]
    if parent_ids:
        parent_defects = db.query(Defect).filter(Defect.id.in_(parent_ids)).all()
        if len(parent_defects) != len(parent_ids):
            raise HTTPException(status_code=400, detail="有父缺陷不存在")
        # 检查父缺陷是否为子缺陷
        if any(d.type == DefectType.BUG for d in parent_defects):
            raise HTTPException(status_code=400, detail="父缺陷不能为子缺陷")
        # 检查子缺陷是否为父缺陷
        if any(d.type == DefectType.BUG for d in parent_defects):
            raise HTTPException(status_code=400, detail="子缺陷不能为父缺陷")
        # 检查子缺陷是否为子缺陷
        if any(d.type == DefectType.BUG for d in parent_defects):
            raise HTTPException(status_code=400, detail="子缺陷不能为子缺陷")
        # 检查子缺陷是否为缺陷
        if any(d.type == DefectType.BUG for d in parent_defects):
            raise HTTPException(status_code=400, detail="子缺陷不能为缺陷")
    # 更新缺陷
    for i, defect_data in enumerate(defects):
        # 记录原始状态，用于状态历史记录
        old_status = existing_defects[i].status
        
        update_data = defect_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing_defects[i], key, value)
        
        # 如果状态发生变化，记录状态历史
        if 'status' in update_data and update_data['status'] != old_status:
            status_history = DefectStatusHistory(
                defect_id=existing_defects[i].id,
                old_status=old_status,
                new_status=update_data['status'],
                changed_by=current_user.id,
                comment=f"批量更新：状态从 {old_status.value} 变更为 {update_data['status'].value}"
            )
            db.add(status_history)
        
        # 设置更新者
        existing_defects[i].updated_by = current_user.id
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
    
    # 权限检查：非管理员只能删除自己创建的缺陷
    if current_user.role != MemberRole.ADMIN:  # type: ignore
        for defect in existing_defects:
            if defect.created_by != current_user.id:
                raise HTTPException(status_code=403, detail=f"权限不足，无法删除缺陷 {defect.id}，只能删除自己创建的缺陷")
    # 检查缺陷是否为子缺陷
    if any(d.type == DefectType.BUG for d in existing_defects):
        raise HTTPException(status_code=400, detail="子缺陷不能删除")
    # 删除缺陷
    for defect in existing_defects:
        db.delete(defect)
    db.commit()
    return standard_response(
        message="缺陷删除成功",
        data={
            "deleted_count": len(existing_defects)
        }
    )

# 单个缺陷分配负责人
@router.put("/{defect_id}/assign", response_model=BaseResponse) 
async def update_defect_assignee(
    defect_id: str,
    assign_data: DefectAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """分配缺陷负责人"""
    if not defect_id:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    # 检查缺陷是否存在
    existing_defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not existing_defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    # 检查负责人是否存在
    assignee = db.query(User).filter(User.id == assign_data.assignee_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="负责人不存在")
    # 分配负责人
    existing_defect.assignee_id = assign_data.assignee_id
    
    db.commit()
    return BaseResponse(
        message="缺陷分配成功",
        data={
            "defect_id": defect_id,
            "assignee_id": assign_data.assignee_id
        }
    )

# 导出缺陷
@router.get("/export", response_model=BaseResponse)
async def export_defects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:read"))
):
    """导出缺陷数据"""
    # 构建查询
    query = db.query(Defect).options(
        joinedload(Defect.project),
        joinedload(Defect.assignee),
        joinedload(Defect.reporter)
    )
    
    # 权限过滤：非管理员只能导出自己相关的缺陷
    if current_user.role != UserRole.ADMIN:
        query = query.filter(
            or_(
                Defect.created_by == current_user.id,
                Defect.assignee_id == current_user.id,
                Defect.reporter_id == current_user.id,
                Defect.verified_by_id == current_user.id
            )
        )
    
    # 导出缺陷
    defects = query.all()
    return standard_response(
        message="缺陷导出成功",
        data={
            "defects": [DefectResponse.model_validate(d, from_attributes=True) for d in defects]
        }
    )

# 导入缺陷
@router.post("/import", response_model=BaseResponse)
async def import_defects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("defect:write"))
):
    """导入缺陷数据"""
    # 权限检查：非管理员只能导入自己相关的缺陷
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，只能管理员导入缺陷")
    # 读取文件内容
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    # 转换为字典列表
    defect_data = df.to_dict(orient='records')
    # 导入缺陷
    for data in defect_data:
        defect = Defect(**data)
        db.add(defect)
    db.commit()
    return standard_response(
        message="缺陷导入成功",
        data={
            "imported_count": len(defect_data)
        }
    )
