from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from models.defect import DefectStatus, DefectPriority, DefectType, DefectSeverity

# 缺陷相关模式
class DefectBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: DefectStatus = DefectStatus.NEW
    priority: DefectPriority = DefectPriority.MEDIUM
    type: DefectType = DefectType.BUG
    severity: DefectSeverity = DefectSeverity.MODERATE
    project_id: str
    project_name: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    reporter_id: Optional[str] = None
    reporter_name: Optional[str] = None
    verified_by_id: Optional[str] = None
    verified_by_name: Optional[str] = None
    version: Optional[str] = None
    environment: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    resolution: Optional[str] = None
    parent_id: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None

# 缺陷响应模式
class DefectResponse(DefectBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """自定义验证方法，从关联对象中填充名称字段"""
        # 先调用父类的验证
        instance = super().model_validate(obj, **kwargs)
        
        # 从关联的reporter对象中获取名称
        if hasattr(obj, 'reporter') and obj.reporter:
            instance.reporter_name = obj.reporter.name
        
        # 从关联的assignee对象中获取名称
        if hasattr(obj, 'assignee') and obj.assignee:
            instance.assignee_name = obj.assignee.name
        
        # 从关联的project对象中获取项目名称
        if hasattr(obj, 'project') and obj.project:
            instance.project_name = obj.project.name
            
        return instance
    
    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v):
        """解析tags字段，支持JSON字符串转换为列表"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                return json.loads(v) if v else []
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []
    
    class Config:
        from_attributes = True

# 缺陷创建模式
class DefectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="缺陷标题")
    description: Optional[str] = Field(None, description="缺陷描述")
    status: DefectStatus = Field(DefectStatus.NEW, description="缺陷状态")
    priority: DefectPriority = Field(DefectPriority.MEDIUM, description="优先级")
    type: DefectType = Field(DefectType.BUG, description="缺陷类型")
    severity: DefectSeverity = Field(DefectSeverity.MODERATE, description="严重程度")
    project_id: str = Field(..., description="项目ID")
    assignee_id: Optional[str] = Field(None, description="执行人ID")
    reporter_id: Optional[str] = Field(None, description="报告人ID")
    verified_by_id: Optional[str] = Field(None, description="验证人ID")
    version: Optional[str] = Field(None, max_length=100, description="版本")
    environment: Optional[str] = Field(None, max_length=100, description="环境")
    steps_to_reproduce: Optional[str] = Field(None, description="重现步骤")
    expected_result: Optional[str] = Field(None, description="期望结果")
    actual_result: Optional[str] = Field(None, description="实际结果")
    resolution: Optional[str] = Field(None, description="解决方案")
    parent_id: Optional[str] = Field(None, description="父缺陷ID")
    tags: Optional[List[str]] = Field(None, description="标签")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    source: Optional[str] = Field(None, max_length=100, description="缺陷来源")

# 缺陷更新模式
class DefectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="缺陷标题")
    description: Optional[str] = Field(None, description="缺陷描述")
    status: Optional[DefectStatus] = Field(None, description="缺陷状态")
    priority: Optional[DefectPriority] = Field(None, description="优先级")
    type: Optional[DefectType] = Field(None, description="缺陷类型")
    severity: Optional[DefectSeverity] = Field(None, description="严重程度")
    project_id: Optional[str] = Field(None, description="项目ID")
    assignee_id: Optional[str] = Field(None, description="执行人ID")
    reporter_id: Optional[str] = Field(None, description="报告人ID")
    verified_by_id: Optional[str] = Field(None, description="验证人ID")
    version: Optional[str] = Field(None, max_length=100, description="版本")
    environment: Optional[str] = Field(None, max_length=100, description="环境")
    steps_to_reproduce: Optional[str] = Field(None, description="重现步骤")
    expected_result: Optional[str] = Field(None, description="期望结果")
    actual_result: Optional[str] = Field(None, description="实际结果")
    resolution: Optional[str] = Field(None, description="解决方案")
    parent_id: Optional[str] = Field(None, description="父缺陷ID")
    tags: Optional[List[str]] = Field(None, description="标签")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    source: Optional[str] = Field(None, max_length=100, description="缺陷来源")