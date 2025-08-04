from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from typing import Optional, List
from math import ceil
import json

from models.database import get_db
from models.models import Project, User, Organization, Task
from schemas.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, BaseResponse, UserResponse
)
from utils.auth import (
    get_current_active_user, require_permission
)

router = APIRouter()

# 项目列表
@router.get("/list", response_model=BaseResponse)
async def get_projects(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[str] = Query(None, description="项目状态"),
    organization_id: Optional[str] = Query(None, description="组织ID"),
    creator_id: Optional[str] = Query(None, description="创建者ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取项目列表"""
    from utils.response_utils import list_response, paginate_query    

    
    query = db.query(Project).filter(Project.is_archived == False)
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Project.name.contains(keyword),
                Project.description.contains(keyword)
            )
        )
    
    # 状态过滤
    if status:
        query = query.filter(Project.status == status)
    
    # 组织过滤
    if organization_id:
        query = query.filter(Project.organization_id == organization_id)
    
    # 创建者过滤
    if creator_id:
        query = query.filter(Project.creator_id == creator_id)
    
    # 预加载关联数据
    query = query.options(
        joinedload(Project.manager),
        joinedload(Project.organization)
    )
    
    # 分页
    total, projects = paginate_query(query, page, size)
    
    # 构建响应数据，手动设置关联字段
    project_responses = []
    for project in projects:
        project_response = ProjectResponse.from_orm(project)
        project_response.manager_name = project.manager.name if project.manager else None
        project_response.organization_name = project.organization.name if project.organization else None
        project_responses.append(project_response)
    
    return list_response(
        records=project_responses,
        total=total,
        page=page,
        size=size,
        message="获取项目列表成功"
    )

@router.get("/page", response_model=BaseResponse)
async def get_projects_page(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[str] = Query(None, description="项目状态"),
    organization_id: Optional[str] = Query(None, description="组织ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取项目分页数据"""
    return await get_projects(keyword, status, organization_id, None, page, size, db, current_user)

# 我的项目
@router.get("/my", response_model=BaseResponse)
async def get_my_projects(
    status: Optional[str] = Query(None, description="项目状态"),
    role: Optional[str] = Query(None, description="在项目中的角色"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取当前用户参与的项目"""
    from utils.response_utils import list_response
    
    query = db.query(Project).filter(
        and_(
            Project.is_archived == False,
            or_(
                Project.creator_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
    )
    
    # 状态过滤
    if status:
        query = query.filter(Project.status == status)
    
    # 预加载关联数据
    query = query.options(
        joinedload(Project.manager),
        joinedload(Project.organization)
    )
    
    projects = query.all()
    
    # 构建响应数据，手动设置关联字段
    project_responses = []
    for project in projects:
        project_response = ProjectResponse.from_orm(project)
        project_response.manager_name = project.manager.name if project.manager else None
        project_response.organization_name = project.organization.name if project.organization else None
        project_responses.append(project_response)
    
    return list_response(
        items=project_responses,
        message="获取我的项目成功"
    )

# 项目详情
@router.get("/{project_id}", response_model=BaseResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取项目详情"""
    print(f"Received project_id: {project_id}") # 添加这行日志
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    # 项目详情
    project_response_data = ProjectResponse.model_validate(project, from_attributes=True)
    # 项目成员
    project_response_data.members = [
        {"name": member.name, "role": member.role, "id": member.id}
        for member in project.members
    ]
    # 项目任务 - 只返回最新的前5条
    latest_tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc()).limit(5).all()
    project_response_data.tasks = [
        {
            "title": task.title, 
            "status": task.status, 
            "id": task.id,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "assignee_name": task.assignee.name if task.assignee else None
        }
        for task in latest_tasks
    ]
    # 项目组织
    project_response_data.organization_name = project.organization.name if project.organization else ""
    # 项目组织ID
    project_response_data.organization_id = project.organization_id
    # 项目负责人
    project_response_data.manager_name = project.manager.name if project.manager else ""
    # 项目创建时间
    project_response_data.created_at = project.created_at
    # 项目更新时间
    project_response_data.updated_at = project.updated_at
    # 项目负责人ID
    project_response_data.manager_id = project.manager_id
    # 项目预算
    project_response_data.budget = float(project.budget) if project.budget else None
    # 项目标签 - 从JSON字符串解析为数组
    try:
        project_response_data.tags = json.loads(project.tags) if project.tags else []
    except (json.JSONDecodeError, TypeError):
        project_response_data.tags = []

    return BaseResponse(
        message="获取项目详情成功",
        data=project_response_data
    )

@router.get("/{project_id}/members", response_model=BaseResponse)
async def get_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取项目成员列表"""
    print(f"Received project_id for members: {project_id}") # 添加这行日志
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    return BaseResponse(
        message="获取项目成员列表成功",
        data=[{"name": member.name, "role": member.role, "id": member.id} for member in project.members]
    )

# 创建项目
@router.post("/create", response_model=BaseResponse)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """创建项目"""
    # 检查项目名是否已存在
    if db.query(Project).filter(Project.name == project_data.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="项目名已存在"
        )
    
    # 检查组织是否存在
    if project_data.organization_id:
        organization = db.query(Organization).filter(
            Organization.id == project_data.organization_id
        ).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="组织不存在"
            )
    
    # 检查项目经理是否存在
    if project_data.manager_id:
        manager = db.query(User).filter(User.id == project_data.manager_id).first()
        if not manager:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定的项目经理不存在"
            )
    
    # 检查成员是否存在
    members_to_add = []
    if project_data.member_ids:
        for member_id in project_data.member_ids:
            member = db.query(User).filter(User.id == member_id).first()
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"用户ID {member_id} 不存在"
                )
            members_to_add.append(member)
    
    # 创建新项目
    db_project = Project(
        name=project_data.name,
        description=project_data.description,
        status=project_data.status,
        priority=project_data.priority,
        start_date=project_data.start_date,
        end_date=project_data.end_date,
        creator_id=current_user.id,
        manager_id=project_data.manager_id,
        organization_id=project_data.organization_id,
        budget=project_data.budget,
        tags=json.dumps(project_data.tags) if project_data.tags else None
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    # 将创建者添加为项目成员（如果不在成员列表中）
    if current_user not in members_to_add:
        db_project.members.append(current_user)
    
    # 添加指定的项目成员
    for member in members_to_add:
        if member not in db_project.members:
            db_project.members.append(member)
    
    # 如果指定了项目经理且经理不在成员列表中，也添加为成员
    if project_data.manager_id:
        manager = db.query(User).filter(User.id == project_data.manager_id).first()
        if manager and manager not in db_project.members:
            db_project.members.append(manager)
    
    db.commit()
    db.refresh(db_project)

    # 填充 ProjectResponse 的 members 字段
    project_response_data = ProjectResponse.from_orm(db_project)
    project_response_data.members = [UserResponse.from_orm(member) for member in db_project.members]
    
    return BaseResponse(
        message="创建项目成功",
        data=project_response_data
    )

# 更新项目
@router.put("/{project_id}/update", response_model=BaseResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """更新项目信息"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查项目名是否已被其他项目使用
    if project_data.name and project_data.name != project.name:
        existing_project = db.query(Project).filter(
            and_(Project.name == project_data.name, Project.id != project_id)
        ).first()
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="项目名已存在"
            )
    
    # 更新项目信息
    update_data = project_data.dict(exclude_unset=True)
    
    # 处理 tags 字段 - 转换为JSON字符串
    if 'tags' in update_data:
        if update_data['tags'] is not None:
            project.tags = json.dumps(update_data['tags'])
        else:
            project.tags = None
        del update_data['tags']
    
    # 处理 manager_id 更新
    if 'manager_id' in update_data:
        if update_data['manager_id']:
            manager = db.query(User).filter(User.id == update_data['manager_id']).first()
            if not manager:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="指定的项目经理不存在"
                )
            project.manager_id = update_data['manager_id']
        else:
            project.manager_id = None
        del update_data['manager_id'] # 避免重复设置

    # 处理 member_ids 更新
    if 'member_ids' in update_data:
        # 清空现有成员
        project.members.clear()
        members_to_add = []
        if update_data['member_ids']:
            for member_id in update_data['member_ids']:
                member = db.query(User).filter(User.id == member_id).first()
                if not member:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"用户ID {member_id} 不存在"
                    )
                members_to_add.append(member)
        
        # 添加指定的项目成员
        for member in members_to_add:
            if member not in project.members:
                project.members.append(member)
        
        del update_data['member_ids'] # 避免重复设置

    # 更新其他字段
    for field, value in update_data.items():
        setattr(project, field, value)

    # 确保当前用户和项目经理（如果存在）是成员
    if current_user not in project.members:
        project.members.append(current_user)
    
    if project.manager_id:
        manager = db.query(User).filter(User.id == project.manager_id).first()
        if manager and manager not in project.members:
            project.members.append(manager)

    db.commit()
    db.refresh(project)
    
    # 填充 ProjectResponse 的 members 字段
    project_response_data = ProjectResponse.from_orm(project)
    # 填充 ProjectResponse 的 creator 字段
    if project.creator:
        project_response_data.creator = UserResponse.from_orm(project.creator)
    # 填充 ProjectResponse 的 members 字段
    project_response_data.members = [UserResponse.from_orm(member) for member in project.members]

    return BaseResponse(
        message="更新项目信息成功",
        data=project_response_data
    )

# 删除项目
@router.delete("/{project_id}/delete", response_model=BaseResponse)
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """删除项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    db.delete(project)
    db.commit()
    
    return BaseResponse(message="删除项目成功")

# 归档项目
@router.put("/{project_id}/archive", response_model=BaseResponse)
async def archive_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """归档项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    project.is_archived = True
    db.commit()
    
    return BaseResponse(message="归档项目成功")

# 恢复项目
@router.put("/{project_id}/restore", response_model=BaseResponse)
async def restore_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """恢复已归档的项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    project.is_archived = False
    db.commit()
    
    return BaseResponse(message="恢复项目成功")

# 项目添加成员
@router.post("/{project_id}/members/{user_id}", response_model=BaseResponse)
async def add_project_member(
    project_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """添加项目成员"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户是否已是项目成员
    if user in project.members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户已是项目成员"
        )
    
    project.members.append(user)
    db.commit()
    
    return BaseResponse(message="添加项目成员成功")



# 项目成员列表
@router.get("/{project_id}/members", response_model=BaseResponse)
async def get_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取项目成员列表"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    return BaseResponse(
        message="获取项目成员成功",
        data=[UserResponse.from_orm(member) for member in project.members]
    )