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
from schemas.defect import DefectResponse, DefectCreate, DefectUpdate, DefectPriority,\
    DefectAssign, DefectStatusHistory as DefectStatusHistorySchema, DefectPageQuery

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
    # 查询缺陷表，预加载关联对象
    db_query = db.query(Defect).options(
        joinedload(Defect.reporter),
        joinedload(Defect.assignee),
        joinedload(Defect.handler),
        joinedload(Defect.project)
    )
    
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
    
    # 状态筛选
    if query.status:
        db_query = db_query.filter(Defect.status == query.status)
    
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
        if str(parent_defect.type) == DefectType.BUG.value:
            raise HTTPException(status_code=400, detail="父缺陷不能为子缺陷")
        # 检查子缺陷是否为父缺陷
        if str(defect.type) == DefectType.BUG.value:  # BUG表示缺陷类型
            raise HTTPException(status_code=400, detail="子缺陷不能为缺陷类型")
    
    # 创建缺陷对象
    defect_data = defect.model_dump()
    # 将tags列表转换为JSON字符串
    if 'tags' in defect_data:
        import json
        defect_data['tags'] = json.dumps(defect_data['tags'], ensure_ascii=False)
    
    # 过滤掉Defect模型中不存在的字段
    allowed_fields = {
        'title', 'description', 'status', 'priority', 'type', 'severity',
        'project_id', 'assignee_id', 'reporter_id', 'verified_by_id',
        'version', 'environment', 'steps_to_reproduce', 'expected_result',
        'actual_result', 'resolution', 'parent_id', 'tags', 'due_date', 'source'
    }
    filtered_data = {k: v for k, v in defect_data.items() if k in allowed_fields}
    
    db_defect = Defect(**filtered_data)
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
    
    # 重新查询缺陷以包含关联对象
    db_defect_with_relations = db.query(Defect).options(
        joinedload(Defect.reporter),
        joinedload(Defect.assignee),
        joinedload(Defect.handler),
        joinedload(Defect.project)
    ).filter(Defect.id == db_defect.id).first()
    
    return standard_response(
        data=DefectResponse.model_validate(db_defect_with_relations, from_attributes=True),
        message="缺陷创建成功"
    )



# 缺陷统计接口