from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import get_db
from app.core.auth import get_current_user, check_permission
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.organization import Organization
from app.models.file import File
from app.schemas.base import BaseResponse

router = APIRouter()

# 搜索相关的 Pydantic 模式
from pydantic import BaseModel, Field

class SearchResult(BaseModel):
    """搜索结果项"""
    id: str
    type: str = Field(..., description="结果类型：project, task, user, organization, file")
    title: str = Field(..., description="标题")
    description: Optional[str] = Field(None, description="描述")
    url: str = Field(..., description="详情链接")
    highlight: Optional[str] = Field(None, description="高亮内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    created_at: datetime
    updated_at: datetime

class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResult]
    total: int
    took: float = Field(..., description="搜索耗时（毫秒）")
    aggregations: Dict[str, Any] = Field(default_factory=dict, description="聚合统计")

class SearchParams(BaseModel):
    """搜索参数"""
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    types: Optional[List[str]] = Field(None, description="搜索类型过滤")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页大小")
    sort: Optional[str] = Field(None, description="排序方式：relevance, date_desc, date_asc")
    date_from: Optional[datetime] = Field(None, description="开始日期")
    date_to: Optional[datetime] = Field(None, description="结束日期")

class QuickSearchResult(BaseModel):
    """快速搜索结果"""
    projects: List[SearchResult] = []
    tasks: List[SearchResult] = []
    users: List[SearchResult] = []
    organizations: List[SearchResult] = []
    files: List[SearchResult] = []

@router.get("/", response_model=BaseResponse[SearchResponse])
async def global_search(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    types: Optional[str] = Query(None, description="搜索类型，逗号分隔"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    sort: Optional[str] = Query("relevance", description="排序方式"),
    date_from: Optional[datetime] = Query(None, description="开始日期"),
    date_to: Optional[datetime] = Query(None, description="结束日期"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("search:global"))
):
    """全局搜索"""
    import time
    start_time = time.time()
    
    # 解析搜索类型
    search_types = types.split(',') if types else ['project', 'task', 'user', 'organization', 'file']
    
    # 检查缓存
    cache_key = f"search:{current_user.id}:{keyword}:{':'.join(search_types)}:{page}:{page_size}:{sort}"
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        return BaseResponse(
            data=SearchResponse(**cached_result),
            message="搜索成功"
        )
    
    all_results = []
    aggregations = {}
    
    # 搜索项目
    if 'project' in search_types:
        project_results, project_count = await search_projects(
            keyword, db, current_user, date_from, date_to
        )
        all_results.extend(project_results)
        aggregations['projects'] = project_count
    
    # 搜索任务
    if 'task' in search_types:
        task_results, task_count = await search_tasks(
            keyword, db, current_user, date_from, date_to
        )
        all_results.extend(task_results)
        aggregations['tasks'] = task_count
    
    # 搜索用户
    if 'user' in search_types and current_user.role in ["admin", "manager"]:
        user_results, user_count = await search_users(
            keyword, db, current_user, date_from, date_to
        )
        all_results.extend(user_results)
        aggregations['users'] = user_count
    
    # 搜索组织
    if 'organization' in search_types:
        org_results, org_count = await search_organizations(
            keyword, db, current_user, date_from, date_to
        )
        all_results.extend(org_results)
        aggregations['organizations'] = org_count
    
    # 搜索文件
    if 'file' in search_types:
        file_results, file_count = await search_files(
            keyword, db, current_user, date_from, date_to
        )
        all_results.extend(file_results)
        aggregations['files'] = file_count
    
    # 排序
    if sort == "date_desc":
        all_results.sort(key=lambda x: x.updated_at, reverse=True)
    elif sort == "date_asc":
        all_results.sort(key=lambda x: x.updated_at)
    else:  # relevance
        # 简单的相关性排序：标题匹配优先
        def relevance_score(result):
            score = 0
            if keyword.lower() in result.title.lower():
                score += 10
            if result.description and keyword.lower() in result.description.lower():
                score += 5
            return score
        
        all_results.sort(key=relevance_score, reverse=True)
    
    # 分页
    total = len(all_results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_results = all_results[start_idx:end_idx]
    
    # 计算耗时
    took = (time.time() - start_time) * 1000
    
    search_response = SearchResponse(
        results=paginated_results,
        total=total,
        took=round(took, 2),
        aggregations=aggregations
    )
    
    # 缓存结果
    await redis_client.set(cache_key, search_response.dict(), expire=300)  # 5分钟缓存
    
    return BaseResponse(
        data=search_response,
        message="搜索成功"
    )

@router.get("/quick", response_model=BaseResponse[QuickSearchResult])
async def quick_search(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(5, ge=1, le=10, description="每类型限制数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("search:quick"))
):
    """快速搜索（用于搜索建议）"""
    # 检查缓存
    cache_key = f"quick_search:{current_user.id}:{keyword}:{limit}"
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        return BaseResponse(
            data=QuickSearchResult(**cached_result),
            message="搜索成功"
        )
    
    # 并发搜索各类型
    import asyncio
    
    async def get_quick_projects():
        results, _ = await search_projects(keyword, db, current_user, limit=limit)
        return results
    
    async def get_quick_tasks():
        results, _ = await search_tasks(keyword, db, current_user, limit=limit)
        return results
    
    async def get_quick_users():
        if current_user.role in ["admin", "manager"]:
            results, _ = await search_users(keyword, db, current_user, limit=limit)
            return results
        return []
    
    async def get_quick_organizations():
        results, _ = await search_organizations(keyword, db, current_user, limit=limit)
        return results
    
    async def get_quick_files():
        results, _ = await search_files(keyword, db, current_user, limit=limit)
        return results
    
    # 并发执行
    projects, tasks, users, organizations, files = await asyncio.gather(
        get_quick_projects(),
        get_quick_tasks(),
        get_quick_users(),
        get_quick_organizations(),
        get_quick_files()
    )
    
    quick_result = QuickSearchResult(
        projects=projects,
        tasks=tasks,
        users=users,
        organizations=organizations,
        files=files
    )
    
    # 缓存结果
    await redis_client.set(cache_key, quick_result.dict(), expire=180)  # 3分钟缓存
    
    return BaseResponse(
        data=quick_result,
        message="搜索成功"
    )

@router.get("/suggestions", response_model=BaseResponse[List[str]])
async def get_search_suggestions(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=20, description="建议数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_permission("search:suggestions"))
):
    """获取搜索建议"""
    # 检查缓存
    cache_key = f"search_suggestions:{current_user.id}:{keyword}:{limit}"
    cached_suggestions = await redis_client.get(cache_key)
    if cached_suggestions:
        return BaseResponse(
            data=cached_suggestions,
            message="获取成功"
        )
    
    suggestions = set()
    
    # 从项目名称中获取建议
    if current_user.role in ["admin", "manager"]:
        project_query = select(Project.name).where(
            Project.name.contains(keyword)
        ).limit(limit // 4)
    else:
        project_query = select(Project.name).where(
            and_(
                Project.name.contains(keyword),
                or_(
                    Project.manager_id == current_user.id,
                    Project.members.any(User.id == current_user.id)
                )
            )
        ).limit(limit // 4)
    
    project_result = await db.execute(project_query)
    for name in project_result.scalars():
        suggestions.add(name)
    
    # 从任务标题中获取建议
    if current_user.role in ["admin", "manager"]:
        task_query = select(Task.title).where(
            Task.title.contains(keyword)
        ).limit(limit // 4)
    else:
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        task_query = select(Task.title).where(
            and_(
                Task.title.contains(keyword),
                or_(
                    Task.assignee_id == current_user.id,
                    Task.reporter_id == current_user.id,
                    Task.project_id.in_(user_projects)
                )
            )
        ).limit(limit // 4)
    
    task_result = await db.execute(task_query)
    for title in task_result.scalars():
        suggestions.add(title)
    
    # 从组织名称中获取建议
    if current_user.role in ["admin", "manager"]:
        org_query = select(Organization.name).where(
            Organization.name.contains(keyword)
        ).limit(limit // 4)
    else:
        org_query = select(Organization.name).where(
            and_(
                Organization.name.contains(keyword),
                Organization.members.any(User.id == current_user.id)
            )
        ).limit(limit // 4)
    
    org_result = await db.execute(org_query)
    for name in org_result.scalars():
        suggestions.add(name)
    
    # 从文件名中获取建议
    if current_user.role in ["admin", "manager"]:
        file_query = select(File.original_filename).where(
            File.original_filename.contains(keyword)
        ).limit(limit // 4)
    else:
        file_query = select(File.original_filename).where(
            and_(
                File.original_filename.contains(keyword),
                File.uploader_id == current_user.id
            )
        ).limit(limit // 4)
    
    file_result = await db.execute(file_query)
    for filename in file_result.scalars():
        suggestions.add(filename)
    
    # 转换为列表并限制数量
    suggestion_list = list(suggestions)[:limit]
    
    # 缓存结果
    await redis_client.set(cache_key, suggestion_list, expire=600)  # 10分钟缓存
    
    return BaseResponse(
        data=suggestion_list,
        message="获取成功"
    )

# 辅助搜索函数
async def search_projects(
    keyword: str, 
    db: AsyncSession, 
    current_user: User, 
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None
) -> tuple[List[SearchResult], int]:
    """搜索项目"""
    query = select(Project).where(
        or_(
            Project.name.contains(keyword),
            Project.description.contains(keyword)
        )
    )
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        query = query.where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
    
    # 日期过滤
    if date_from:
        query = query.where(Project.created_at >= date_from)
    if date_to:
        query = query.where(Project.created_at <= date_to)
    
    # 获取总数
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    
    # 限制数量
    if limit:
        query = query.limit(limit)
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    search_results = []
    for project in projects:
        search_results.append(SearchResult(
            id=project.id,
            type="project",
            title=project.name,
            description=project.description,
            url=f"/projects/{project.id}",
            metadata={
                "status": project.status,
                "priority": project.priority,
                "progress": project.progress
            },
            created_at=project.created_at,
            updated_at=project.updated_at
        ))
    
    return search_results, total

async def search_tasks(
    keyword: str, 
    db: AsyncSession, 
    current_user: User, 
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None
) -> tuple[List[SearchResult], int]:
    """搜索任务"""
    query = select(Task).where(
        or_(
            Task.title.contains(keyword),
            Task.description.contains(keyword)
        )
    )
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        user_projects = select(Project.id).where(
            or_(
                Project.manager_id == current_user.id,
                Project.members.any(User.id == current_user.id)
            )
        )
        query = query.where(
            or_(
                Task.assignee_id == current_user.id,
                Task.reporter_id == current_user.id,
                Task.project_id.in_(user_projects)
            )
        )
    
    # 日期过滤
    if date_from:
        query = query.where(Task.created_at >= date_from)
    if date_to:
        query = query.where(Task.created_at <= date_to)
    
    # 获取总数
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    
    # 限制数量
    if limit:
        query = query.limit(limit)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    search_results = []
    for task in tasks:
        search_results.append(SearchResult(
            id=task.id,
            type="task",
            title=task.title,
            description=task.description,
            url=f"/tasks/{task.id}",
            metadata={
                "status": task.status,
                "priority": task.priority,
                "type": task.type,
                "project_id": task.project_id
            },
            created_at=task.created_at,
            updated_at=task.updated_at
        ))
    
    return search_results, total

async def search_users(
    keyword: str, 
    db: AsyncSession, 
    current_user: User, 
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None
) -> tuple[List[SearchResult], int]:
    """搜索用户"""
    query = select(User).where(
        or_(
            User.username.contains(keyword),
            User.name.contains(keyword),
            User.email.contains(keyword)
        )
    )
    
    # 日期过滤
    if date_from:
        query = query.where(User.created_at >= date_from)
    if date_to:
        query = query.where(User.created_at <= date_to)
    
    # 获取总数
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    
    # 限制数量
    if limit:
        query = query.limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    search_results = []
    for user in users:
        search_results.append(SearchResult(
            id=user.id,
            type="user",
            title=user.name or user.username,
            description=f"{user.email} - {user.department or '未设置部门'}",
            url=f"/users/{user.id}",
            metadata={
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "department": user.department
            },
            created_at=user.created_at,
            updated_at=user.updated_at
        ))
    
    return search_results, total

async def search_organizations(
    keyword: str, 
    db: AsyncSession, 
    current_user: User, 
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None
) -> tuple[List[SearchResult], int]:
    """搜索组织"""
    query = select(Organization).where(
        or_(
            Organization.name.contains(keyword),
            Organization.description.contains(keyword)
        )
    )
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Organization.members.any(User.id == current_user.id))
    
    # 日期过滤
    if date_from:
        query = query.where(Organization.created_at >= date_from)
    if date_to:
        query = query.where(Organization.created_at <= date_to)
    
    # 获取总数
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    
    # 限制数量
    if limit:
        query = query.limit(limit)
    
    result = await db.execute(query)
    organizations = result.scalars().all()
    
    search_results = []
    for org in organizations:
        search_results.append(SearchResult(
            id=org.id,
            type="organization",
            title=org.name,
            description=org.description,
            url=f"/organizations/{org.id}",
            metadata={
                "type": org.type,
                "email": org.email,
                "phone": org.phone
            },
            created_at=org.created_at,
            updated_at=org.updated_at
        ))
    
    return search_results, total

async def search_files(
    keyword: str, 
    db: AsyncSession, 
    current_user: User, 
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None
) -> tuple[List[SearchResult], int]:
    """搜索文件"""
    query = select(File).where(
        or_(
            File.filename.contains(keyword),
            File.original_filename.contains(keyword)
        )
    )
    
    # 权限过滤
    if current_user.role not in ["admin", "manager"]:
        query = query.where(File.uploader_id == current_user.id)
    
    # 日期过滤
    if date_from:
        query = query.where(File.created_at >= date_from)
    if date_to:
        query = query.where(File.created_at <= date_to)
    
    # 获取总数
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    
    # 限制数量
    if limit:
        query = query.limit(limit)
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    search_results = []
    for file in files:
        search_results.append(SearchResult(
            id=file.id,
            type="file",
            title=file.original_filename,
            description=f"文件大小：{file.file_size // 1024}KB",
            url=f"/files/{file.id}",
            metadata={
                "file_type": file.file_type,
                "file_extension": file.file_extension,
                "file_size": file.file_size,
                "entity_type": file.entity_type,
                "entity_id": file.entity_id
            },
            created_at=file.created_at,
            updated_at=file.updated_at
        ))
    
    return search_results, total