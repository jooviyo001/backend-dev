from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, text
from typing import Optional
from models.database import get_db
from models.organization import Organization, OrganizationType, OrganizationStatus
from models.associations import organization_members
from models.project import Project
from models.user import User
from models.enums import OrganizationType, OrganizationStatus, MemberRole

from schemas import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse, 
    OrganizationTreeNode, OrganizationMemberCreate, OrganizationMemberUpdate, 
    OrganizationMemberResponse, OrganizationStatistics, OrganizationMove,
    OrganizationBatchDelete,
    BaseResponse,
    OrganizationBatchUpdate
)
from utils.auth import get_current_user
from utils.response_utils import success_response, error_response
from utils.status_codes import INTERNAL_ERROR, BAD_REQUEST, NOT_FOUND
# from utils.snowflake_column import SnowflakeId
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 辅助函数：构建组织路径
def build_organization_path(db: Session, org_id) -> str:
    """构建组织路径"""
    path_parts = []
    current_id = org_id
    
    while current_id: # type: ignore
        org = db.query(Organization).filter(Organization.id == current_id).first()
        if not org:
            break
        path_parts.insert(0, str(current_id))
        current_id = org.parent_id
    
    return "/" + "/".join(path_parts) if path_parts else "/"

# 辅助函数：更新子组织层级
def update_children_level_and_path(db: Session, parent_org: Organization):
    """更新子组织的层级和路径"""
    children = db.query(Organization).filter(Organization.parent_id == parent_org.id).all()
    for child in children:
        child.level = parent_org.level + 1 # type: ignore
        child.path = build_organization_path(db, child.id) # type: ignore
        db.add(child)
        update_children_level_and_path(db, child)

# 辅助函数：获取组织成员数量
def get_member_count(db: Session, org_id) -> int:
    """获取组织成员数量"""
    try:
        return db.query(func.count(organization_members.c.user_id)).filter(
            organization_members.c.organization_id == org_id
        ).scalar() or 0
    except Exception:
        return 0

# 辅助函数：获取子组织数量
def get_child_count(db: Session, org_id) -> int:
    """获取子组织数量"""
    try:
        return db.query(func.count(Organization.id)).filter(
            Organization.parent_id == org_id
        ).scalar() or 0
    except Exception:
        return 0

# 组织列表（不分页）
@router.get("/list", response_model=BaseResponse)
async def get_organizations(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    type: Optional[OrganizationType] = Query(None, description="组织类型"),
    status: Optional[OrganizationStatus] = Query(None, description="组织状态"),
    parent_id: Optional[str] = Query(None, description="父组织ID"),
    manager_id: Optional[str] = Query(None, description="负责人ID"),
    level: Optional[int] = Query(None, description="组织层级"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织列表"""
    try:
        # ID格式处理函数 - 保持原始格式
        def extract_id(id_str):
            """保持ID的原始格式，不进行转换"""
            return id_str if id_str else None
        
        query = db.query(Organization)
        
        # 关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    Organization.name.contains(keyword),
                    Organization.code.contains(keyword),
                    Organization.description.contains(keyword)
                )
            )
        
        # 类型筛选
        if type:
            query = query.filter(Organization.type == type)
        
        # 状态筛选
        if status:
            query = query.filter(Organization.status == status)
        
        # 父组织筛选
        if parent_id is not None:
            extracted_parent_id = extract_id(parent_id)
            if extracted_parent_id:
                query = query.filter(Organization.parent_id == extracted_parent_id)
        
        # 负责人筛选
        if manager_id:
            extracted_manager_id = extract_id(manager_id)
            if extracted_manager_id:
                query = query.filter(Organization.manager_id == extracted_manager_id)
        
        # 层级筛选
        if level:
            query = query.filter(Organization.level == level)
        
        organizations = query.order_by(Organization.sort.asc(), Organization.created_at.desc()).all()
        
        # 构建响应数据
        result = []
        for org in organizations:
            # 安全获取父组织名称
            parent_name = None
            if org.parent_id: # type: ignore
                try:
                    parent_org = db.query(Organization).filter(Organization.id == org.parent_id).first()
                    parent_name = parent_org.name if parent_org else None
                except Exception:
                    parent_name = None
            
            # 安全获取管理员名称
            manager_name = None # type: ignore            
            if org.manager_id: # type: ignore
                try:
                    manager = db.query(User).filter(User.id == org.manager_id).first()
                    manager_name = manager.name if manager else None
                except Exception:
                    manager_name = None
            
            org_data = OrganizationResponse(
                id=str(org.id),
                name=str(org.name),
                code=str(org.code),
                type=org.type, # type: ignore
                status=org.status, # type: ignore
                description=str(org.description) if org.description else None, # type: ignore
                parent_id=str(org.parent_id) if org.parent_id else None, # type: ignore
                parent_name=parent_name, # type: ignore
                level=int(org.level), # type: ignore
                path=str(org.path) if org.path else None, # type: ignore
                manager_id=str(org.manager_id) if org.manager_id else None, # type: ignore
                manager_name=manager_name, # type: ignore
                member_count=get_member_count(db, org.id), # type: ignore
                child_count=get_child_count(db, org.id), # type: ignore
                sort=int(org.sort), # type: ignore
                address=str(org.address) if org.address else None, # type: ignore
                phone=str(org.phone) if org.phone else None, # type: ignore
                email=str(org.email) if org.email else None, # type: ignore
                website=str(org.website) if org.website else None, # type: ignore
                logo=str(org.logo) if org.logo else None, # type: ignore
                is_active=bool(org.is_active), # type: ignore
                created_at=org.created_at, # type: ignore
                updated_at=org.updated_at # type: ignore
            )
            result.append(org_data)
        
        return success_response(data=result, message="获取组织列表成功")
        
    except Exception as e:
        logger.error(f"获取组织列表失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织列表失败")


# 组织分页列表
@router.get("/page", response_model=BaseResponse)
async def get_organizations_page(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    type: Optional[OrganizationType] = Query(None, description="组织类型"),
    status: Optional[OrganizationStatus] = Query(None, description="组织状态"),
    parent_id: Optional[str] = Query(None, description="父组织ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织分页数据"""
    try:
        # ID格式处理函数 - 保持原始格式
        def extract_id(id_str):
            """保持ID的原始格式，不进行转换"""
            return id_str if id_str else None
        
        query = db.query(Organization)
        
        # 关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    Organization.name.contains(keyword),
                    Organization.code.contains(keyword),
                    Organization.description.contains(keyword)
                )
            )
        
        # 类型筛选
        if type:
            query = query.filter(Organization.type == type)
        
        # 状态筛选
        if status:
            query = query.filter(Organization.status == status)
        
        # 父组织筛选
        if parent_id is not None:
            extracted_parent_id = extract_id(parent_id)
            if extracted_parent_id:
                query = query.filter(Organization.parent_id == extracted_parent_id)
        
        # 分页
        total = query.count()
        organizations = query.order_by(Organization.sort.asc(), Organization.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        # 构建响应数据
        items = []
        for org in organizations:
            org_data = OrganizationResponse(
                id=str(org.id),
                name=str(org.name),
                code=str(org.code),
                type=org.type, # type: ignore
                status=org.status, # type: ignore
                description=str(org.description) if org.description else None, # type: ignore
                parent_id=str(org.parent_id) if org.parent_id else None, # type: ignore
                parent_name=str(db.query(Organization).filter(Organization.id == org.parent_id).first().name) if org.parent_id else None, # type: ignore
                level=int(org.level), # type: ignore
                path=str(org.path) if org.path else None, # type: ignore
                manager_id=str(org.manager_id) if org.manager_id else None, # type: ignore
                manager_name=str(db.query(User).filter(User.id == org.manager_id).first().name) if org.manager_id else None, # type: ignore
                member_count=get_member_count(db, org.id),
                child_count=get_child_count(db, org.id),
                sort=int(org.sort), # type: ignore
                address=str(org.address) if org.address else None, # type: ignore
                phone=str(org.phone) if org.phone else None, # type: ignore
                email=str(org.email) if org.email else None, # type: ignore
                website=str(org.website) if org.website else None, # type: ignore
                logo=str(org.logo) if org.logo else None, # type: ignore
                is_active=bool(org.is_active),
                created_at=org.created_at, # type: ignore
                updated_at=org.updated_at # type: ignore
            )
            items.append(org_data)
        
        data = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        
        return success_response(data=data, message="获取组织分页数据成功")
        
    except Exception as e:
        logger.error(f"获取组织分页数据失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织分页数据失败")

# 组织树形结构
@router.get("/tree", response_model=BaseResponse)
async def get_organization_tree(
    parent_id: Optional[str] = Query(None, description="父组织ID，为空时获取根组织"),
    include_inactive: bool = Query(False, description="是否包含停用组织"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织树形结构"""
    try:
        # ID格式处理函数 - 保持原始格式
        def extract_id(id_str):
            """保持ID的原始格式，不进行转换"""
            return id_str if id_str else None
        
        def build_tree_node(org: Organization) -> OrganizationTreeNode:
            """构建树节点"""
            children_query = db.query(Organization).filter(Organization.parent_id == org.id)
            if not include_inactive:
                children_query = children_query.filter(Organization.status == OrganizationStatus.ACTIVE)
            
            children = children_query.order_by(Organization.sort.asc()).all()
            
            return OrganizationTreeNode(
                id=str(org.id),
                name=str(org.name),
                code=str(org.code),
                type=org.type,
                status=org.status,
                parent_id=str(org.parent_id) if org.parent_id else None, # type: ignore
                level=int(org.level), # type: ignore
                member_count=get_member_count(db, org.id), # type: ignore
                children=[build_tree_node(child) for child in children]
            )
        
        # 获取根组织或指定父组织的子组织
        extracted_parent_id = extract_id(parent_id)
        query = db.query(Organization).filter(Organization.parent_id == extracted_parent_id)
        if not include_inactive:
            query = query.filter(Organization.status == OrganizationStatus.ACTIVE)
        
        root_orgs = query.order_by(Organization.sort.asc()).all()
        tree_data = [build_tree_node(org) for org in root_orgs]
        
        return success_response(data=tree_data, message="获取组织树成功")
        
    except Exception as e:
        logger.error(f"获取组织树失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织树失败")

@router.get("/{organization_id}", response_model=BaseResponse)
async def get_organization(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取组织详情"""
    try:
        # 直接使用传入的organization_id，不进行格式转换
        extracted_org_id = organization_id
        organization = db.query(Organization).options(
            joinedload(Organization.parent),
            joinedload(Organization.manager)
        ).filter(Organization.id == extracted_org_id).first()
        
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        org_data = OrganizationResponse(
            id=organization.id, # type: ignore
            name=organization.name, # type: ignore
            code=organization.code, # type: ignore
            type=organization.type, # type: ignore
            status=organization.status, # type: ignore
            description=organization.description, # type: ignore
            parent_id=organization.parent_id, # type: ignore
            parent_name=organization.parent.name if organization.parent else None,
            level=organization.level, # type: ignore
            path=organization.path, # type: ignore
            manager_id=organization.manager_id, # type: ignore
            manager_name=organization.manager.name if organization.manager else None, # type: ignore
            member_count=get_member_count(db, organization.id), # type: ignore
            child_count=get_child_count(db, organization.id), # type: ignore
            sort=organization.sort, # type: ignore
            address=organization.address, # type: ignore
            phone=organization.phone, # type: ignore
            email=organization.email, # type: ignore
            website=organization.website, # type: ignore
            logo=organization.logo, # type: ignore
            is_active=organization.status == OrganizationStatus.ACTIVE, # type: ignore
            created_at=organization.created_at, # type: ignore
            updated_at=organization.updated_at # type: ignore
        )
        
        return success_response(data=org_data, message="获取组织详情成功")
        
    except Exception as e:
        logger.error(f"获取组织详情失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织详情失败")

# 组织创建
@router.post("/create", response_model=BaseResponse)
async def create_organization(
    organization: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建组织"""
    try:
        # 检查组织编码是否已存在
        existing_code = db.query(Organization).filter(Organization.code == organization.code).first()
        if existing_code:
            return error_response(code=BAD_REQUEST, data={"code": organization.code}, message="组织编码已存在")
        
        # 检查同级组织名称是否已存在
        existing_name = db.query(Organization).filter(
            and_(
                Organization.name == organization.name,
                Organization.parent_id == organization.parent_id
            )
        ).first()
        if existing_name:
            return error_response(code=BAD_REQUEST, data={"name": organization.name}, message="同级组织中名称已存在")

        
        # 验证父组织是否存在
        parent_org = None
        if organization.parent_id:
            parent_org = db.query(Organization).filter(Organization.id == organization.parent_id).first()
            if not parent_org:
                return error_response(code=BAD_REQUEST, data={"parent_id": organization.parent_id}, message="父组织不存在")
        
        # 验证负责人是否存在
        if organization.manager_id:
            manager = db.query(User).filter(User.id == organization.manager_id).first()
            if not manager:
                return error_response(code=BAD_REQUEST, data={"manager_id": organization.manager_id}, message="负责人不存在")
        
        # 计算层级
        level = 1 if not parent_org else parent_org.level + 1
        
        # 创建组织
        db_organization = Organization(
            name=organization.name,
            code=organization.code,
            type=organization.type,
            status=organization.status,
            description=organization.description,
            parent_id=organization.parent_id,
            level=level,
            manager_id=organization.manager_id,
            sort=organization.sort,
            address=organization.address,
            phone=organization.phone,
            email=organization.email,
            website=organization.website,
            is_active=organization.status == OrganizationStatus.ACTIVE
        )
        
        db.add(db_organization)
        db.flush()  # 获取ID但不提交
        
        # 构建路径
        db_organization.path = build_organization_path(db, db_organization.id) # type: ignore
        
        db.commit()
        db.refresh(db_organization)
        
        # 构建响应数据
        org_data = OrganizationResponse(
            id=db_organization.id, # type: ignore
            name=db_organization.name, # type: ignore
            code=db_organization.code, # type: ignore
            type=db_organization.type, # type: ignore
            status=db_organization.status, # type: ignore
            description=db_organization.description, # type: ignore
            parent_id=db_organization.parent_id, # type: ignore
            parent_name=parent_org.name if parent_org else None, # type: ignore
            level=db_organization.level, # type: ignore
            path=db_organization.path, # type: ignore
            manager_id=db_organization.manager_id, # type: ignore
            manager_name=None,  # 需要查询获取
            member_count=0,
            child_count=0,
            sort=db_organization.sort, # type: ignore
            address=db_organization.address, # type: ignore
            phone=db_organization.phone, # type: ignore
            email=db_organization.email, # type: ignore
            website=db_organization.website, # type: ignore
            logo=db_organization.logo, # type: ignore
            is_active=db_organization.is_active, # type: ignore
            created_at=db_organization.created_at, # type: ignore
            updated_at=db_organization.updated_at # type: ignore
        )
        
        return success_response(data=org_data, message="创建组织成功")
        
    except Exception as e:
        logger.error(f"创建组织失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, data={"detail": str(e)}, message="创建组织失败")

# 组织更新
@router.put("/update/{organization_id}", response_model=BaseResponse)
async def update_organization(
    organization_id: str,
    organization_data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新组织信息"""
    try:
        # 直接使用传入的organization_id，不进行格式转换
        extracted_org_id = organization_id
        organization = db.query(Organization).options(
            joinedload(Organization.parent),
            joinedload(Organization.manager)
        ).filter(Organization.id == extracted_org_id).first()
        
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 检查组织编码是否已被其他组织使用
        if organization_data.code and organization_data.code != organization.code:
            existing_code = db.query(Organization).filter(
                and_(Organization.code == organization_data.code, Organization.id != extracted_org_id)
            ).first()
            if existing_code:
                return error_response(code=BAD_REQUEST, message="组织编码已存在")
        
        # 检查同级组织名称是否已被其他组织使用
        if organization_data.name and organization_data.name != organization.name:
            parent_id = organization_data.parent_id if organization_data.parent_id is not None else organization.parent_id
            existing_name = db.query(Organization).filter(
                and_(
                    Organization.name == organization_data.name,
                    Organization.parent_id == parent_id,
                    Organization.id != extracted_org_id
                )
            ).first()
            if existing_name:
                return error_response(code=BAD_REQUEST, message="同级组织中名称已存在")
        
        # 验证父组织变更
        if organization_data.parent_id is not None and organization_data.parent_id != organization.parent_id:
            # 不能将组织设为自己的子组织
            if organization_data.parent_id == extracted_org_id:
                return error_response(code=BAD_REQUEST, message="不能将组织设为自己的子组织")
            
            # 验证新父组织是否存在
            if organization_data.parent_id:
                new_parent = db.query(Organization).filter(Organization.id == organization_data.parent_id).first()
                if not new_parent:
                    return error_response(code=BAD_REQUEST, message="父组织不存在")
                
                # 检查是否会形成循环引用
                current_parent_id = new_parent.parent_id
                while current_parent_id:
                    if current_parent_id == extracted_org_id: # type: ignore
                        return error_response(code=BAD_REQUEST, message="不能形成循环引用")
                    parent = db.query(Organization).filter(Organization.id == current_parent_id).first()
                    current_parent_id = parent.parent_id if parent else None
        
        # 验证负责人是否存在
        if organization_data.manager_id:
            manager = db.query(User).filter(User.id == organization_data.manager_id).first()
            if not manager:
                return error_response(code=BAD_REQUEST, message="负责人不存在")
        
        # 更新组织信息
        update_data = organization_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(organization, field, value)
        
        # 如果父组织发生变化，需要重新计算层级和路径
        if organization_data.parent_id is not None and organization_data.parent_id != organization.parent_id:
            if organization.parent_id: # type: ignore
                parent_org = db.query(Organization).filter(Organization.id == organization.parent_id).first()
                organization.level = parent_org.level + 1 if parent_org else 1 # type: ignore
            else:
                organization.level = 1 # type: ignore
            
            # 更新路径
            organization.path = build_organization_path(db, organization.id) # type: ignore
            
            # 递归更新子组织的层级和路径
            update_children_level_and_path(db, organization)
        
        # 更新状态相关字段
        if organization_data.status:
            organization.is_active = organization_data.status == OrganizationStatus.ACTIVE # type: ignore
        
        db.commit()
        db.refresh(organization)
        
        # 构建响应数据
        org_data = OrganizationResponse(
            id=organization.id, # type: ignore
            name=organization.name, # type: ignore
            code=organization.code, # type: ignore
            type=organization.type, # type: ignore
            status=organization.status, # type: ignore
            description=organization.description, # type: ignore
            parent_id=organization.parent_id, # type: ignore
            parent_name=organization.parent.name if organization.parent else None,
            level=organization.level, # type: ignore
            path=organization.path, # type: ignore
            manager_id=organization.manager_id, # type: ignore
            manager_name=organization.manager.name if organization.manager else None,
            member_count=get_member_count(db, organization.id),
            child_count=get_child_count(db, organization.id),
            sort=organization.sort, # type: ignore
            address=organization.address, # type: ignore
            phone=organization.phone, # type: ignore
            email=organization.email, # type: ignore
            website=organization.website, # type: ignore
            logo=organization.logo, # type: ignore
            is_active=organization.is_active, # type: ignore
            created_at=organization.created_at, # type: ignore
            updated_at=organization.updated_at # type: ignore
        )
        
        return success_response(data=org_data, message="更新组织信息成功")
        
    except Exception as e:
        logger.error(f"更新组织信息失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, data={"detail": str(e)}, message="更新组织信息失败")

# 组织删除
@router.delete("/delete/{organization_id}", response_model=BaseResponse)
async def delete_organization(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除组织"""
    try:
        # 直接使用传入的organization_id，不进行格式转换
        extracted_org_id = organization_id
        organization = db.query(Organization).filter(Organization.id == extracted_org_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, data={"organization_id": organization_id}, message="组织不存在")
        
        # 检查是否有子组织
        child_count = get_child_count(db, extracted_org_id)
        if child_count > 0:
            return error_response(code=BAD_REQUEST, data={"child_count": child_count}, message="组织下还有子组织，无法删除")
        
        # 检查是否有成员
        member_count = get_member_count(db, extracted_org_id)
        if member_count > 0:
            return error_response(code=BAD_REQUEST, data={"member_count": member_count}, message="组织下还有成员，无法删除")

        
        # 检查是否有关联的项目
        project_count = db.query(func.count(Project.id)).filter(Project.organization_id == extracted_org_id).scalar() or 0
        if project_count > 0:
            return error_response(code=BAD_REQUEST, data={"project_count": project_count}, message="组织下还有项目，无法删除")
        
        db.delete(organization)
        db.commit()
        
        return success_response(data={"organization_id": organization_id}, message="删除组织成功")
        
    except Exception as e:
        logger.error(f"删除组织失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="删除组织失败")

# 批量删除组织
@router.post("/batch-delete", response_model=BaseResponse)
async def batch_delete_organizations(
    request: OrganizationBatchDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量删除组织"""
    try:
        deleted_count = 0
        failed_ids = []
        
        for org_id in request.ids:
            try:
                organization = db.query(Organization).filter(Organization.id == org_id).first()
                if not organization:
                    failed_ids.append(org_id)
                    continue
                
                # 检查是否有子组织
                if get_child_count(db, org_id) > 0:
                    failed_ids.append(org_id)
                    continue
                
                # 检查是否有成员
                if get_member_count(db, org_id) > 0:
                    failed_ids.append(org_id)
                    continue
                
                # 检查是否有关联的项目
                project_count = db.query(func.count(Project.id)).filter(Project.organization_id == org_id).scalar() or 0
                if project_count > 0:
                    failed_ids.append(org_id)
                    continue
                
                db.delete(organization)
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"删除组织 {org_id} 失败: {str(e)}")
                failed_ids.append(org_id)
        
        db.commit()
        
        message = f"成功删除 {deleted_count} 个组织"
        if failed_ids:
            message += f"，{len(failed_ids)} 个组织删除失败"
        
        return success_response(
            data={"deleted_count": deleted_count, "failed_ids": failed_ids},
            message=message
        )
        
    except Exception as e:
        logger.error(f"批量删除组织失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="批量删除组织失败")

# 批量启用/禁用组织
@router.post("/batch-update-status", response_model=BaseResponse)
async def batch_update_organization_status(
    request: OrganizationBatchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量启用/禁用组织"""
    try:
        updated_count = 0
        failed_ids = []

        for org_id in request.ids:
            try:
                organization = db.query(Organization).filter(Organization.id == org_id).first()
                if not organization:
                    failed_ids.append(org_id)
                    continue

                organization.status = request.status # type: ignore
                organization.is_active = (request.status == OrganizationStatus.active) # type: ignore
                db.add(organization)
                updated_count += 1

            except Exception as e:
                logger.error(f"更新组织 {org_id} 状态失败: {str(e)}")
                failed_ids.append(org_id)

        db.commit()

        message = f"成功更新 {updated_count} 个组织的状态"
        if failed_ids:
            message += f"，{len(failed_ids)} 个组织状态更新失败"

        return success_response(
            data={"updated_count": updated_count, "failed_ids": failed_ids},
            message=message
        )

    except Exception as e:
        logger.error(f"批量更新组织状态失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="批量更新组织状态失败")

# 移动组织
@router.put("/{organization_id}/move", response_model=BaseResponse)
async def move_organization(
    organization_id: str,
    request: OrganizationMove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移动组织"""
    try:
        # 直接使用传入的organization_id，不进行格式转换
        extracted_org_id = organization_id
        organization = db.query(Organization).filter(Organization.id == extracted_org_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 验证新父组织
        if request.parent_id:
            new_parent = db.query(Organization).filter(Organization.id == request.parent_id).first()
            if not new_parent:
                return error_response(code=BAD_REQUEST, message="父组织不存在")
            
            # 不能将组织移动到自己或自己的子组织下
            if request.parent_id == extracted_org_id:
                return error_response(code=BAD_REQUEST, message="不能将组织移动到自己下面")
            
            # 检查是否会形成循环引用
            current_parent_id = new_parent.parent_id
            while current_parent_id:
                if current_parent_id == extracted_org_id:
                    return error_response(code=BAD_REQUEST, message="不能形成循环引用")
                parent = db.query(Organization).filter(Organization.id == current_parent_id).first()
                current_parent_id = parent.parent_id if parent else None
        
        # 更新父组织
        organization.parent_id = request.parent_id
        
        # 重新计算层级
        if request.parent_id:
            parent_org = db.query(Organization).filter(Organization.id == request.parent_id).first()
            organization.level = parent_org.level + 1
        else:
            organization.level = 1
        
        # 更新路径
        organization.path = build_organization_path(db, organization.id)
        
        # 递归更新子组织的层级和路径
        update_children_level_and_path(db, organization)
        
        db.commit()
        db.refresh(organization)
        
        # 构建响应数据
        org_data = OrganizationResponse(
            id=organization.id,
            name=organization.name,
            code=organization.code,
            type=organization.type,
            status=organization.status,
            description=organization.description,
            parent_id=organization.parent_id,
            parent_name=organization.parent.name if organization.parent else None,
            level=organization.level,
            path=organization.path,
            manager_id=organization.manager_id,
            manager_name=organization.manager.name if organization.manager else None,
            member_count=get_member_count(db, organization.id),
            child_count=get_child_count(db, organization.id),
            sort=organization.sort,
            address=organization.address,
            phone=organization.phone,
            email=organization.email,
            website=organization.website,
            logo=organization.logo,
            is_active=organization.is_active,
            created_at=organization.created_at,
            updated_at=organization.updated_at
        )
        
        return success_response(data=org_data, message="移动组织成功")
        
    except Exception as e:
        logger.error(f"移动组织失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="移动组织失败")

# 组织统计
@router.get("/{organization_id}/statistics", response_model=BaseResponse)
async def get_organization_statistics(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织统计信息"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 统计直接成员数量
        direct_member_count = get_member_count(db, organization_id)
        
        # 统计所有子组织成员数量（包括子组织的子组织）
        def get_all_descendant_member_count(org_id) -> int:
            count = get_member_count(db, org_id)
            children = db.query(Organization).filter(Organization.parent_id == org_id).all()
            for child in children:
                count += get_all_descendant_member_count(child.id)
            return count
        
        total_member_count = get_all_descendant_member_count(organization_id)
        
        # 统计直接子组织数量
        direct_child_count = get_child_count(db, organization_id)
        
        # 统计所有子组织数量（包括子组织的子组织）
        def get_all_descendant_count(org_id) -> int:
            count = get_child_count(db, org_id)
            children = db.query(Organization).filter(Organization.parent_id == org_id).all()
            for child in children:
                count += get_all_descendant_count(child.id)
            return count
        
        total_child_count = get_all_descendant_count(organization_id)
        
        # 统计项目数量
        project_count = db.query(func.count(Project.id)).filter(Project.organization_id == organization_id).scalar() or 0
        
        # 按类型统计子组织
        child_type_stats = db.query(
            Organization.type,
            func.count(Organization.id).label('count')
        ).filter(Organization.parent_id == organization_id).group_by(Organization.type).all()
        
        # 按状态统计子组织
        child_status_stats = db.query(
            Organization.status,
            func.count(Organization.id).label('count')
        ).filter(Organization.parent_id == organization_id).group_by(Organization.status).all()
        
        statistics = OrganizationStatistics(
            organization_id=organization_id,
            direct_member_count=direct_member_count,
            total_member_count=total_member_count,
            direct_child_count=direct_child_count,
            total_child_count=total_child_count,
            project_count=project_count,
            child_type_stats={stat.type.value: stat.count for stat in child_type_stats},
            child_status_stats={stat.status.value: stat.count for stat in child_status_stats}
        )
        
        return success_response(data=statistics, message="获取组织统计信息成功")
        
    except Exception as e:
        logger.error(f"获取组织统计信息失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织统计信息失败")

# 添加组织成员
@router.post("/{organization_id}/members", response_model=BaseResponse)
async def add_organization_member(
    organization_id: str,
    member_data: OrganizationMemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加组织成员"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        user = db.query(User).filter(User.id == member_data.user_id).first()
        if not user:
            return error_response(code=NOT_FOUND, message="用户不存在")
        
        # 检查用户是否已是组织成员
        existing_member = db.query(organization_members).filter(
            and_(
                organization_members.c.organization_id == organization_id,
                organization_members.c.user_id == member_data.user_id
            )
        ).first()
        
        if existing_member:
            return error_response(code=BAD_REQUEST, message="用户已是组织成员")
        
        # 添加成员
        stmt = organization_members.insert().values(
            organization_id=organization_id,
            user_id=member_data.user_id,
            role=member_data.role,
            joined_at=func.now()
        )
        db.execute(stmt)
        db.commit()
        
        # 构建响应数据
        member_response = OrganizationMemberResponse(
            user_id=member_data.user_id,
            username=user.username,
            name=user.name,
            email=user.email,
            role=member_data.role,
            joined_at=func.now()
        )
        
        return success_response(data=member_response, message="添加组织成员成功")
        
    except Exception as e:
        logger.error(f"添加组织成员失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="添加组织成员失败")

# 更新组织成员角色
@router.put("/{organization_id}/members/{user_id}", response_model=BaseResponse)
async def update_organization_member(
    organization_id: str,
    user_id: str,
    member_data: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新组织成员角色"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(code=NOT_FOUND, message="用户不存在")
        
        # 检查用户是否是组织成员
        member = db.query(organization_members).filter(
            and_(
                organization_members.c.organization_id == organization_id,
                organization_members.c.user_id == user_id
            )
        ).first()
        
        if not member:
            return error_response(code=NOT_FOUND, message="用户不是组织成员")
        
        # 更新成员角色
        stmt = organization_members.update().where(
            and_(
                organization_members.c.organization_id == organization_id,
                organization_members.c.user_id == user_id
            )
        ).values(role=member_data.role)
        
        db.execute(stmt)
        db.commit()
        
        # 构建响应数据
        member_response = OrganizationMemberResponse(
            user_id=user_id,
            username=user.username,
            name=user.name,
            email=user.email,
            role=member_data.role,
            joined_at=member.joined_at
        )
        
        return success_response(data=member_response, message="更新组织成员角色成功")
        
    except Exception as e:
        logger.error(f"更新组织成员角色失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="更新组织成员角色失败")

# 移除组织成员
@router.delete("/{organization_id}/members/{user_id}", response_model=BaseResponse)
async def remove_organization_member(
    organization_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移除组织成员"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(code=NOT_FOUND, message="用户不存在")
        
        # 检查用户是否是组织成员
        member = db.query(organization_members).filter(
            and_(
                organization_members.c.organization_id == organization_id,
                organization_members.c.user_id == user_id
            )
        ).first()
        
        if not member:
            return error_response(code=NOT_FOUND, message="用户不是组织成员")
        
        # 移除成员
        stmt = organization_members.delete().where(
            and_(
                organization_members.c.organization_id == organization_id,
                organization_members.c.user_id == user_id
            )
        )
        db.execute(stmt)
        db.commit()
        
        return success_response(message="移除组织成员成功")
        
    except Exception as e:
        logger.error(f"移除组织成员失败: {str(e)}")
        db.rollback()
        return error_response(code=INTERNAL_ERROR, message="移除组织成员失败")

# 获取组织成员列表
@router.get("/{organization_id}/members", response_model=BaseResponse)
async def get_organization_members(
    organization_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    role: Optional[MemberRole] = Query(None, description="成员角色"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织成员列表"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 构建查询
        query = db.query(
            User,
            organization_members.c.role,
            organization_members.c.joined_at
        ).join(
            organization_members,
            User.id == organization_members.c.user_id
        ).filter(
            organization_members.c.organization_id == organization_id
        )
        
        # 关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    User.username.contains(keyword),
                    User.name.contains(keyword),
                    User.email.contains(keyword)
                )
            )
        
        # 角色筛选
        if role:
            query = query.filter(organization_members.c.role == role)
        
        # 分页
        total = query.count()
        members = query.order_by(organization_members.c.joined_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        # 构建响应数据
        items = []
        for user, role, joined_at in members:
            member_data = OrganizationMemberResponse(
                user_id=user.id,
                username=user.username,
                name=user.name,
                email=user.email,
                role=role,
                joined_at=joined_at
            )
            items.append(member_data)
        
        pagination_data = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
        
        return success_response(data=pagination_data, message="获取组织成员列表成功")
        
    except Exception as e:
        logger.error(f"获取组织成员列表失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织成员列表失败")

# 获取用户所属组织列表
@router.get("/user/{user_id}", response_model=BaseResponse)
async def get_user_organizations(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户所属组织列表"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(code=NOT_FOUND, message="用户不存在")
        
        # 查询用户所属的组织
        organizations_query = db.query(
            Organization,
            organization_members.c.role,
            organization_members.c.joined_at
        ).join(
            organization_members,
            Organization.id == organization_members.c.organization_id
        ).filter(
            organization_members.c.user_id == user_id
        ).order_by(organization_members.c.joined_at.desc())
        
        organizations = organizations_query.all()
        
        # 构建响应数据
        items = []
        for org, role, joined_at in organizations:
            org_data = OrganizationResponse(
                id=org.id,
                name=org.name,
                code=org.code,
                type=org.type,
                status=org.status,
                description=org.description,
                parent_id=org.parent_id,
                parent_name=org.parent.name if org.parent else None,
                level=org.level,
                path=org.path,
                manager_id=org.manager_id,
                manager_name=org.manager.name if org.manager else None,
                member_count=get_member_count(db, org.id),
                child_count=get_child_count(db, org.id),
                sort=org.sort,
                address=org.address,
                phone=org.phone,
                email=org.email,
                website=org.website,
                logo=org.logo,
                is_active=org.is_active,
                created_at=org.created_at,
                updated_at=org.updated_at
            )
            items.append(org_data)
        
        return success_response(data=items, message="获取用户所属组织列表成功")
        
    except Exception as e:
        logger.error(f"获取用户所属组织列表失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取用户所属组织列表失败")

# 获取组织路径
@router.get("/{organization_id}/path", response_model=BaseResponse)
async def get_organization_path(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织路径"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 构建路径数组
        path_items = []
        current_org = organization
        
        while current_org:
            path_item = {
                "id": current_org.id,
                "name": current_org.name,
                "code": current_org.code,
                "level": current_org.level
            }
            path_items.insert(0, path_item)  # 插入到开头，保持从根到当前的顺序
            
            if current_org.parent_id:
                current_org = db.query(Organization).filter(Organization.id == current_org.parent_id).first()
            else:
                current_org = None
        
        return success_response(data=path_items, message="获取组织路径成功")
        
    except Exception as e:
        logger.error(f"获取组织路径失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织路径失败")

# 获取子组织列表
@router.get("/{organization_id}/children", response_model=BaseResponse)
async def get_organization_children(
    organization_id: str,
    include_inactive: bool = Query(False, description="是否包含非活跃组织"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取子组织列表"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 构建查询
        query = db.query(Organization).filter(Organization.parent_id == organization_id)
        
        # 是否包含非活跃组织
        if not include_inactive:
            query = query.filter(Organization.is_active == True)
        
        children = query.order_by(Organization.sort.asc(), Organization.created_at.asc()).all()
        
        # 构建响应数据
        items = []
        for child in children:
            child_data = OrganizationResponse(
                id=child.id,
                name=child.name,
                code=child.code,
                type=child.type,
                status=child.status,
                description=child.description,
                parent_id=child.parent_id,
                parent_name=child.parent.name if child.parent else None,
                level=child.level,
                path=child.path,
                manager_id=child.manager_id,
                manager_name=child.manager.name if child.manager else None,
                member_count=get_member_count(db, child.id),
                child_count=get_child_count(db, child.id),
                sort=child.sort,
                address=child.address,
                phone=child.phone,
                email=child.email,
                website=child.website,
                logo=child.logo,
                is_active=child.is_active,
                created_at=child.created_at,
                updated_at=child.updated_at
            )
            items.append(child_data)
        
        return success_response(data=items, message="获取子组织列表成功")
        
    except Exception as e:
        logger.error(f"获取子组织列表失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取子组织列表失败")

# 获取组织项目列表
@router.get("/{organization_id}/projects", response_model=BaseResponse)
async def get_organization_projects(
    organization_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    status: Optional[str] = Query(None, description="项目状态"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取组织项目列表"""
    try:
        # 直接使用传入的organization_id，不进行格式转换
        extracted_org_id = organization_id
        
        organization = db.query(Organization).filter(Organization.id == extracted_org_id).first()
        if not organization:
            return error_response(code=NOT_FOUND, message="组织不存在")
        
        # 构建查询
        query = db.query(Project).filter(Project.organization_id == extracted_org_id)
        
        # 关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    Project.name.contains(keyword),
                    Project.description.contains(keyword)
                )
            )
        
        # 状态筛选
        if status:
            query = query.filter(Project.status == status)
        
        # 分页
        total = query.count()
        projects = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        # 构建响应数据
        items = []
        for project in projects:
            project_data = {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "organization_id": project.organization_id,
                "organization_name": project.organization.name if project.organization else None,
                "created_at": project.created_at,
                "updated_at": project.updated_at
            }
            items.append(project_data)
        
        pagination_data = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
        
        return success_response(data=pagination_data, message="获取组织项目列表成功")
        
    except Exception as e:
        logger.error(f"获取组织项目列表失败: {str(e)}")
        return error_response(code=INTERNAL_ERROR, message="获取组织项目列表失败")