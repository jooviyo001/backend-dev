from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from models import UserRole

# 用户相关模式
class UserBase(BaseModel):
    username: str
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    organization_name: Optional[str] = None  # 组织名称
    role: UserRole = UserRole.MEMBER
    status: Optional[str] = Field(None, description="用户状态")
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None  # 用户是否活跃
    is_verified: Optional[bool] = Field(None, description="用户是否已验证")
    avatar: Optional[str] = None
    password: Optional[str] = Field(None, description="新密码")
    status: Optional[str] = Field(None, description="用户状态")
    
    @field_validator('department', mode='before')
    def convert_department(cls, v):
        """处理department字段，如果是数组则取第一个元素"""
        if isinstance(v, list) and len(v) > 0:
            return v[0]
        return v
    
    @field_validator('status')
    def validate_status(cls, v):
        """验证status字段"""
        if v is not None and v not in ['active', 'inactive']:
            raise ValueError('状态必须是 active 或 inactive')
        return v

class UserProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    organization_id: Optional[str] = None  # 组织ID
    department: Optional[str] = None  # 部门
    avatar: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[UserRole] = None

# 用户返回体定义
class UserResponse(UserBase):
    id: str  # 支持雪花ID格式，如 'U208228089547722752'
    is_active: bool
    is_verified: bool
    position: Optional[str] = None  # 职位
    organization_id: Optional[str] = None  # 所属组织ID
    organization_name: Optional[str] = None  # 组织名称
    role: UserRole = UserRole.MEMBER  # 用户角色
    status: Optional[str] = Field(None, description="用户状态")
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    avatar: Optional[str] = None
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """自定义验证方法，从关联对象中填充组织名称字段"""
        # 先调用父类的验证
        instance = super().model_validate(obj, **kwargs)
        
        # 从关联的organization对象中获取组织名称
        if hasattr(obj, 'organization') and obj.organization:
            instance.organization_name = obj.organization.name
            
        return instance
    
    class Config:
        from_attributes = True

# 认证相关模式
class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

# 登录模式
class LoginRequest(BaseModel):
    username: str
    password: str

# 登录响应模式
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# 注册模式
class RegisterRequest(UserCreate):
    confirm_password: str
            
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('密码不匹配')
        return v

# 注册响应模式
class RegisterResponse(BaseModel):
    data: Optional[UserResponse] = None

# 通知设置相关模式
class NotificationSettings(BaseModel):
    """通知设置模型"""
    email_notifications: bool = Field(True, description="是否启用邮件通知")
    push_notifications: bool = Field(True, description="是否启用推送通知")
    sms_notifications: bool = Field(False, description="是否启用短信通知")
    task_assigned: bool = Field(True, description="任务分配通知")
    task_completed: bool = Field(True, description="任务完成通知")
    task_overdue: bool = Field(True, description="任务逾期通知")
    project_updates: bool = Field(True, description="项目更新通知")
    defect_assigned: bool = Field(True, description="缺陷分配通知")
    defect_resolved: bool = Field(True, description="缺陷解决通知")
    system_announcements: bool = Field(True, description="系统公告通知")
    
    class Config:
        from_attributes = True

class NotificationSettingsResponse(BaseModel):
    """通知设置响应模型"""
    user_id: str
    settings: NotificationSettings
    updated_at: datetime
    
    class Config:
        from_attributes = True

class NotificationSettingsUpdate(BaseModel):
    """通知设置更新模型"""
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    task_assigned: Optional[bool] = None
    task_completed: Optional[bool] = None
    task_overdue: Optional[bool] = None
    project_updates: Optional[bool] = None
    defect_assigned: Optional[bool] = None
    defect_resolved: Optional[bool] = None
    system_announcements: Optional[bool] = None

# 语言设置相关模式
class LanguageSettings(BaseModel):
    """语言设置模型"""
    language: str = Field("zh-CN", description="界面语言")
    timezone: str = Field("Asia/Shanghai", description="时区设置")
    date_format: str = Field("YYYY-MM-DD", description="日期格式")
    time_format: str = Field("24h", description="时间格式")
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """验证语言代码"""
        allowed_languages = ['zh-CN', 'zh-TW', 'en-US', 'ja-JP', 'ko-KR']
        if v not in allowed_languages:
            raise ValueError(f'语言代码必须是以下之一: {", ".join(allowed_languages)}')
        return v
    
    @field_validator('time_format')
    @classmethod
    def validate_time_format(cls, v):
        """验证时间格式"""
        if v not in ['12h', '24h']:
            raise ValueError('时间格式必须是 12h 或 24h')
        return v
    
    class Config:
        from_attributes = True

class LanguageSettingsResponse(BaseModel):
    """语言设置响应模型"""
    user_id: str
    settings: LanguageSettings
    updated_at: datetime
    
    class Config:
        from_attributes = True

class LanguageSettingsUpdate(BaseModel):
    """语言设置更新模型"""
    language: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """验证语言代码"""
        if v is not None:
            allowed_languages = ['zh-CN', 'zh-TW', 'en-US', 'ja-JP', 'ko-KR']
            if v not in allowed_languages:
                raise ValueError(f'语言代码必须是以下之一: {", ".join(allowed_languages)}')
        return v
    
    @field_validator('time_format')
    @classmethod
    def validate_time_format(cls, v):
        """验证时间格式"""
        if v is not None and v not in ['12h', '24h']:
            raise ValueError('时间格式必须是 12h 或 24h')
        return v