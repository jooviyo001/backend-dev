from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from math import ceil

from models.database import get_db
from models.models import Project, User, Organization
from schemas.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, BaseResponse, PaginationResponse
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
    
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以O开头（组织ID）
        if id_str.startswith('O') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以U开头（用户ID）
        if id_str.startswith('U') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以USER_开头（旧格式）
        if id_str.startswith('USER_'):
            return id_str[5:]
        return id_str
    
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
        org_id = extract_id(organization_id)
        query = query.filter(Project.organization_id == org_id)
    
    # 创建者过滤
    if creator_id:
        creator_id_num = extract_id(creator_id)
        query = query.filter(Project.creator_id == creator_id_num)
    
    # 分页
    total, projects = paginate_query(query, page, size)
    
    return list_response(
        items=[ProjectResponse.from_orm(project) for project in projects],
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
    
    projects = query.all()
    
    return list_response(
        items=[ProjectResponse.from_orm(project) for project in projects],
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
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    project_id_num = extract_id(project_id)
    project = db.query(Project).filter(Project.id == project_id_num).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    return BaseResponse(
        message="获取项目详情成功",
        data=ProjectResponse.from_orm(project)
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
        organization_id=project_data.organization_id
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
    
    return BaseResponse(
        message="创建项目成功",
        data=ProjectResponse.from_orm(db_project)
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
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    project_id_num = extract_id(project_id)
    project = db.query(Project).filter(Project.id == project_id_num).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查项目名是否已被其他项目使用
    if project_data.name and project_data.name != project.name:
        existing_project = db.query(Project).filter(
            and_(Project.name == project_data.name, Project.id != project_id_num)
        ).first()
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="项目名已存在"
            )
    
    # 更新项目信息
    update_data = project_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    
    return BaseResponse(
        message="更新项目信息成功",
        data=ProjectResponse.from_orm(project)
    )

# 删除项目
@router.delete("/{project_id}/delete", response_model=BaseResponse)
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """删除项目"""
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    project_id_num = extract_id(project_id)
    project = db.query(Project).filter(Project.id == project_id_num).first()
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
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    project_id_num = extract_id(project_id)
    project = db.query(Project).filter(Project.id == project_id_num).first()
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
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    project_id_num = extract_id(project_id)
    project = db.query(Project).filter(Project.id == project_id_num).first()
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
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以U开头（用户ID）
        if id_str.startswith('U') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以USER_开头（旧格式）
        if id_str.startswith('USER_'):
            return id_str[5:]
        return id_str
    
    project_id_num = extract_id(project_id)
    user_id_num = extract_id(user_id)
    
    project = db.query(Project).filter(Project.id == project_id_num).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    user = db.query(User).filter(User.id == user_id_num).first()
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

# 项目移除成员
@router.delete("/{project_id}/members/{user_id}", response_model=BaseResponse)
async def remove_project_member(
    project_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write"))
):
    """移除项目成员"""
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以U开头（用户ID）
        if id_str.startswith('U') and id_str[1:].isdigit():
            return id_str[1:]
        # 如果以USER_开头（旧格式）
        if id_str.startswith('USER_'):
            return id_str[5:]
        return id_str
    
    project_id_num = extract_id(project_id)
    user_id_num = extract_id(user_id)
    
    project = db.query(Project).filter(Project.id == project_id_num).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    user = db.query(User).filter(User.id == user_id_num).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户是否是项目成员
    if user not in project.members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不是项目成员"
        )
    
    # 不能移除项目创建者
    if user_id_num == project.creator_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除项目创建者"
        )
    
    project.members.remove(user)
    db.commit()
    
    return BaseResponse(message="移除项目成员成功")

# 项目成员列表
@router.get("/{project_id}/members", response_model=BaseResponse)
async def get_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read"))
):
    """获取项目成员列表"""
    # ID格式处理函数
    def extract_id(id_str):
        """提取ID的数字部分，兼容多种格式"""
        if not id_str:
            return None
        # 如果是纯数字，直接返回
        if id_str.isdigit():
            return id_str
        # 如果以P开头（项目ID）
        if id_str.startswith('P') and id_str[1:].isdigit():
            return id_str[1:]
        return id_str
    
    project_id_num = extract_id(project_id)
    project = db.query(Project).filter(Project.id == project_id_num).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    from schemas.schemas import UserResponse
    return BaseResponse(
        message="获取项目成员成功",
        data=[UserResponse.from_orm(member) for member in project.members]
    )