from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from models.defect import DefectStatus, DefectPriority, DefectType, DefectSeverity

# 缺陷相关模式
class DefectBase(BaseModel):
    # 字段解释：责任人是当前环节处理的人，处理人为开发人员，开发人员可以是多个
    title: str  # 标题
    description: Optional[str] = None  # 描述
    status: DefectStatus = DefectStatus.NEW  # 状态
    priority: DefectPriority = DefectPriority.MEDIUM  # 优先级
    type: DefectType = DefectType.BUG  # 类型
    severity: DefectSeverity = DefectSeverity.MAJOR  # 严重程度
    project_id: str = Field(..., description="项目ID")
    project_name: Optional[str] = Field(None, description="项目名称")
    assignee_id: Optional[str] = Field(None, description="负责人ID")
    assignee_name: Optional[str] = Field(None, description="负责人名称")
    handler_id: Optional[str] = Field(None, description="问题处理人ID")
    handler_name: Optional[str] = Field(None, description="问题处理人名称")
    reporter_id: Optional[str] = Field(None, description="报告人ID")
    reporter_name: Optional[str] = Field(None, description="报告人名称")
    verified_by_id: Optional[str] = Field(None, description="验证人ID")
    verified_by_name: Optional[str] = Field(None, description="验证人名称")
    version: Optional[str] = Field(None, description="版本")
    environment: Optional[str] = Field(None, description="环境")
    steps_to_reproduce: Optional[str] = Field(None, description="复现步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    actual_result: Optional[str] = Field(None, description="实际结果")
    resolution: Optional[str] = Field(None, description="解决方法")
    parent_id: Optional[str] = Field(None, description="父缺陷ID")
    source: Optional[str] = Field(None, description="缺陷来源")
    tags: Optional[List[str]] = Field(None, description="标签")
    


# 缺陷响应模式
class DefectResponse(DefectBase):
    id: str
    created_at: datetime
    updated_at: datetime
    due_date: Optional[date] = Field(None, description="到期日期")
    closed_at: Optional[datetime] = Field(None, description="关闭时间")
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """自定义验证方法，从关联对象中填充名称字段"""
        # 处理 due_date 字段的类型转换
        if hasattr(obj, 'due_date') and obj.due_date and isinstance(obj.due_date, datetime):
            # 将 datetime 转换为 date
            obj.due_date = obj.due_date.date()
        
        # 先调用父类的验证
        instance = super().model_validate(obj, **kwargs)
        
        # 从关联的reporter对象中获取名称
        if hasattr(obj, 'reporter') and obj.reporter:
            instance.reporter_name = obj.reporter.name
        
        # 从关联的assignee对象中获取名称
        if hasattr(obj, 'assignee') and obj.assignee:
            instance.assignee_name = obj.assignee.name
        
        # 从关联的handler对象中获取名称
        if hasattr(obj, 'handler') and obj.handler:
            instance.handler_name = obj.handler.name
        
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
    severity: DefectSeverity = Field(DefectSeverity.MAJOR, description="严重程度")
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


# 缺陷统计相关模式
class DefectStatusStatistics(BaseModel):
    """缺陷状态统计"""
    status: DefectStatus = Field(..., description="缺陷状态")
    count: int = Field(..., description="数量")
    percentage: float = Field(..., description="百分比")


class DefectPriorityStatistics(BaseModel):
    """缺陷优先级统计"""
    priority: DefectPriority = Field(..., description="缺陷优先级")
    count: int = Field(..., description="数量")
    percentage: float = Field(..., description="百分比")


class DefectTypeStatistics(BaseModel):
    """缺陷类型统计"""
    type: DefectType = Field(..., description="缺陷类型")
    count: int = Field(..., description="数量")
    percentage: float = Field(..., description="百分比")


class DefectSeverityStatistics(BaseModel):
    """缺陷严重程度统计"""
    severity: DefectSeverity = Field(..., description="缺陷严重程度")
    count: int = Field(..., description="数量")
    percentage: float = Field(..., description="百分比")


class DefectTrendData(BaseModel):
    """缺陷趋势数据"""
    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    created_count: int = Field(..., description="新建缺陷数量")
    resolved_count: int = Field(..., description="解决缺陷数量")
    closed_count: int = Field(..., description="关闭缺陷数量")


class DefectStatisticsResponse(BaseModel):
    """缺陷统计响应"""
    # 总体统计
    total_count: int = Field(..., description="缺陷总数")
    open_count: int = Field(..., description="未关闭缺陷数")
    closed_count: int = Field(..., description="已关闭缺陷数")
    overdue_count: int = Field(..., description="逾期缺陷数")
    unassigned_count: int = Field(..., description="未分配缺陷数")
    
    # 分类统计
    status_statistics: List[DefectStatusStatistics] = Field(..., description="状态统计")
    priority_statistics: List[DefectPriorityStatistics] = Field(..., description="优先级统计")
    type_statistics: List[DefectTypeStatistics] = Field(..., description="类型统计")
    severity_statistics: List[DefectSeverityStatistics] = Field(..., description="严重程度统计")
    
    # 趋势数据 (最近30天)
    trend_data: List[DefectTrendData] = Field(..., description="趋势数据")
    
    # 项目统计 (如果指定了项目)
    project_id: Optional[str] = Field(None, description="项目ID")
    project_name: Optional[str] = Field(None, description="项目名称")


class DefectPageQuery(BaseModel):
    """缺陷分页查询请求模型"""
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(10, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    status: Optional[DefectStatus] = Field(None, description="缺陷状态")
    department_id: Optional[str] = Field(None, description="组织ID")
    project_id: Optional[str] = Field(None, description="项目ID")
    assignee_id: Optional[str] = Field(None, description="执行人ID")
    reporter_id: Optional[str] = Field(None, description="报告人ID")
    verified_by_id: Optional[str] = Field(None, description="验证人ID")
    priority: Optional[DefectPriority] = Field(None, description="缺陷优先级")
    type: Optional[DefectType] = Field(None, description="缺陷类型")
    severity: Optional[DefectSeverity] = Field(None, description="缺陷严重程度")
    parent_id: Optional[str] = Field(None, description="父缺陷ID")
    start_date: Optional[date] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[date] = Field(None, description="结束日期 (YYYY-MM-DD)")
    only_my_defects: Optional[bool] = Field(None, description="只显示我的缺陷")
    only_overdue: Optional[bool] = Field(None, description="只显示逾期缺陷")
    only_unassigned: Optional[bool] = Field(None, description="只显示未分配缺陷")


# 缺陷分配模式
class DefectAssign(BaseModel):
    assignee_id: Optional[str] = Field(None, description="执行人ID，为空表示取消分配")
    comment: Optional[str] = Field(None, description="分配备注")

# 缺陷状态历史模式
class DefectStatusHistory(BaseModel):
    status: DefectStatus = Field(..., description="状态")
    changed_at: datetime = Field(..., description="变更时间")
    changed_by: Optional[str] = Field(None, description="变更人ID")
    changed_by_name: Optional[str] = Field(None, description="变更人姓名")
    comment: Optional[str] = Field(None, description="变更备注")
    
    class Config:
        from_attributes = True

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
    handler_id: Optional[str] = Field(None, description="处理人ID")
    handler_name: Optional[str] = Field(None, description="处理人姓名")
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


# ==================== 批量操作模式 ====================

# 批量指派请求模式
class DefectBatchAssign(BaseModel):
    defect_ids: List[str] = Field(..., min_items=1, max_items=100, description="缺陷ID列表，最多100个")
    assignee_id: Optional[str] = Field(None, description="执行人ID，为空表示取消分配")
    comment: Optional[str] = Field(None, max_length=500, description="分配备注")
    
    @field_validator('defect_ids')
    @classmethod
    def validate_defect_ids(cls, v):
        """验证缺陷ID列表"""
        if not v:
            raise ValueError("缺陷ID列表不能为空")
        if len(v) != len(set(v)):
            raise ValueError("缺陷ID列表中存在重复项")
        return v


# 批量删除请求模式
class DefectBatchDelete(BaseModel):
    defect_ids: List[str] = Field(..., min_items=1, max_items=100, description="缺陷ID列表，最多100个")
    comment: Optional[str] = Field(None, max_length=500, description="删除备注")
    
    @field_validator('defect_ids')
    @classmethod
    def validate_defect_ids(cls, v):
        """验证缺陷ID列表"""
        if not v:
            raise ValueError("缺陷ID列表不能为空")
        if len(v) != len(set(v)):
            raise ValueError("缺陷ID列表中存在重复项")
        return v


# 批量操作结果项
class BatchOperationResultItem(BaseModel):
    defect_id: str = Field(..., description="缺陷ID")
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    defect_title: Optional[str] = Field(None, description="缺陷标题")


# 批量操作响应模式
class BatchOperationResponse(BaseModel):
    total_count: int = Field(..., description="总操作数量")
    success_count: int = Field(..., description="成功操作数量")
    failed_count: int = Field(..., description="失败操作数量")
    results: List[BatchOperationResultItem] = Field(..., description="详细操作结果")
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_count == 0:
            return 0.0
        return round(self.success_count / self.total_count * 100, 2)