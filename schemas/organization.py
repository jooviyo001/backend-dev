from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from models import OrganizationType, OrganizationStatus, MemberRole

# 组织相关模式
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="组织名称")
    code: str = Field(..., min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$", description="组织编码")
    type: OrganizationType = Field(..., description="组织类型")
    description: Optional[str] = Field(None, max_length=200, description="组织描述")
    parent_id: Optional[str] = Field(None, description="父组织ID")
    manager_id: Optional[str] = Field(None, description="负责人ID")
    sort: int = Field(0, ge=0, le=999, description="排序权重")
    address: Optional[str] = Field(None, max_length=255, description="地址")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    website: Optional[str] = Field(None, max_length=255, description="网站")

# 组织创建模式
class OrganizationCreate(OrganizationBase):
    status: OrganizationStatus = Field(OrganizationStatus.ACTIVE, description="组织状态")

# 组织更新模式
class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="组织名称")
    code: Optional[str] = Field(None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$", description="组织编码")
    type: Optional[OrganizationType] = Field(None, description="组织类型")
    parent_id: Optional[str] = Field(None, description="父组织ID")
    status: Optional[OrganizationStatus] = Field(None, description="组织状态")
    description: Optional[str] = Field(None, max_length=200, description="组织描述")
    manager_id: Optional[str] = Field(None, description="负责人ID")
    sort: Optional[int] = Field(None, ge=0, le=999, description="排序权重")
    address: Optional[str] = Field(None, max_length=255, description="地址")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    website: Optional[str] = Field(None, max_length=255, description="网站")

class OrganizationStatusUpdate(BaseModel):
    status: OrganizationStatus = Field(..., description="组织状态")

# 组织批量更新模式
class OrganizationBatchUpdate(BaseModel):
    ids: List[str] = Field(..., min_length=1, description="组织ID数组")
    status: OrganizationStatus = Field(..., description="组织状态")

# 组织响应模式
class OrganizationResponse(BaseModel):
    id: str
    name: str
    code: str
    type: OrganizationType
    status: OrganizationStatus
    description: Optional[str] = None
    parent_id: Optional[str] = None
    parent_name: Optional[str] = None
    level: int
    path: Optional[str] = None
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    member_count: int = 0
    child_count: int = 0
    sort: int
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo: Optional[str] = None
    is_active: bool  # 保留兼容性
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 组织树节点模式
class OrganizationTreeNode(BaseModel):
    id: str
    name: str
    code: str
    type: OrganizationType
    status: OrganizationStatus
    parent_id: Optional[str] = None
    level: int
    children: List["OrganizationTreeNode"] = []  # 递归引用自身

# 组织成员模式
class OrganizationMemberBase(BaseModel):
    user_id: str = Field(..., description="用户ID")
    position: Optional[str] = Field(None, max_length=100, description="职位")
    role: MemberRole = Field(MemberRole.MEMBER, description="角色")

class OrganizationMemberCreate(OrganizationMemberBase):
    pass

class OrganizationMemberUpdate(BaseModel):
    position: Optional[str] = Field(None, max_length=100, description="职位")
    role: Optional[MemberRole] = Field(None, description="角色")

class OrganizationMemberResponse(BaseModel):
    id: str
    department_id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_avatar: Optional[str] = None
    position: Optional[str] = None
    role: MemberRole
    joined_at: datetime
    
    class Config:
        from_attributes = True

# 组织统计模式
class OrganizationStatistics(BaseModel):
    total: int = 0
    by_type: dict = {}
    by_status: dict = {}
    total_members: int = 0
    average_members_per_org: float = 0.0
    max_level: int = 0

# 组织移动模式
class OrganizationMove(BaseModel):
    parent_id: Optional[str] = Field(None, description="新父组织ID")

# 批量操作模式
class OrganizationBatchDelete(BaseModel):
    ids: List[str] = Field(..., min_length=1, description="组织ID数组")