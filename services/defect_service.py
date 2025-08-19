"""缺陷服务模块

包含缺陷相关的业务逻辑处理
"""
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, and_, func, case
from datetime import datetime, date, timedelta
from fastapi import HTTPException

from models.defect import Defect, DefectStatusHistory
from models.user import User
from models.project import Project
from models.enums import DefectStatus, DefectPriority, DefectType, DefectSeverity, UserRole
from schemas.defect import (
    DefectCreate, DefectUpdate, DefectResponse, DefectAssign,
    DefectStatisticsResponse, DefectStatusStatistics, DefectPriorityStatistics,
    DefectTypeStatistics, DefectSeverityStatistics, DefectTrendData, DefectPageQuery
)
from utils.exceptions import BusinessException, ResourceNotFoundException, ValidationException
from utils.status_codes import NOT_FOUND, VALIDATION_ERROR, FORBIDDEN
from utils.snowflake import generate_defect_id
from utils.query_optimizer import (
    monitor_query_performance, cache_query_result, QueryOptimizer, BatchQueryProcessor
)
import json


class DefectService:
    """缺陷服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 验证方法 ====================
    
    def validate_defect_exists(self, defect_id: str) -> Defect:
        """验证缺陷是否存在"""
        defect = self.db.query(Defect).filter(Defect.id == defect_id).first()
        if not defect:
            raise HTTPException(status_code=404, detail="缺陷不存在")
        return defect
    
    def validate_user_exists(self, user_id: str, user_type: str) -> User:
        """验证用户是否存在"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"{user_type}不存在")
        return user
    
    def validate_project_exists(self, project_id: str) -> Project:
        """验证项目是否存在"""
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return project
    
    def check_defect_permission(self, defect: Defect, current_user: User, operation: str = "read") -> bool:
        """检查缺陷权限"""
        if current_user.role == UserRole.ADMIN:
            return True
        
        # 非管理员权限检查
        user_related = (
            defect.created_by == current_user.id or 
            defect.assignee_id == current_user.id or 
            defect.reporter_id == current_user.id or 
            defect.verified_by_id == current_user.id
        )
        
        if operation == "read":
            return user_related
        elif operation == "write":
            return defect.created_by == current_user.id or defect.assignee_id == current_user.id
        elif operation == "delete":
            return defect.created_by == current_user.id
        elif operation == "status_change":
            return defect.assignee_id == current_user.id or defect.created_by == current_user.id
        
        return False
    
    # ==================== 查询方法 ====================
    
    @monitor_query_performance
    @cache_query_result("defect_detail", ttl=300)
    def get_defect_with_relations(self, defect_id: str) -> Optional[Defect]:
        """获取包含关联对象的缺陷详情"""
        # 使用查询优化器优化JOIN查询
        base_query = self.db.query(Defect).filter(Defect.id == defect_id)
        
        # 预加载关联关系
        eager_load_relations = [
            'reporter', 'assignee', 'handler', 'project', 'parent', 'children'
        ]
        optimized_query = QueryOptimizer.optimize_join_query(
            base_query, eager_load_relations
        )
        
        return optimized_query.first()
    
    @monitor_query_performance
    @cache_query_result("defects_page", ttl=60)
    def get_defects_page(self, query: DefectPageQuery, current_user: User) -> tuple[int, list[Defect]]:
        """分页获取缺陷列表"""
        # 查询缺陷表，预加载关联对象
        db_query = self.db.query(Defect).options(
            joinedload(Defect.reporter),
            joinedload(Defect.assignee),
            joinedload(Defect.handler),
            joinedload(Defect.project)
        )
        
        # 应用用户过滤条件
        db_query = self._apply_user_filter(db_query, current_user)
        
        # 关键词搜索 - 使用查询优化器
        if query.keyword:
            search_fields = [Defect.title, Defect.description]
            db_query = QueryOptimizer.build_search_query(
                db_query, search_fields, query.keyword
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
        from utils.pagination import paginate_query
        total, defects = paginate_query(db_query, query.page, query.size)
        return total, defects
    
    @monitor_query_performance
    @cache_query_result("defect_statistics", ttl=300)
    def get_defect_statistics(self, project_id: Optional[str], current_user: User) -> DefectStatisticsResponse:
        """获取缺陷统计信息"""
        
        # 构建基础查询
        base_query = self.db.query(Defect)
        project_name = None
        
        if project_id:
            # 验证项目是否存在
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="项目不存在")
            base_query = base_query.filter(Defect.project_id == project_id)
            project_name = project.name
        
        # 使用优化的计数查询
        total_count = QueryOptimizer.optimize_count_query(base_query)
        
        # 未关闭缺陷数（状态不是 CLOSED）
        open_count = base_query.filter(Defect.status != DefectStatus.CLOSED).count()
        
        # 已关闭缺陷数
        closed_count = base_query.filter(Defect.status == DefectStatus.CLOSED).count()
        
        # 逾期缺陷数（有截止时间且已过期的未关闭缺陷）
        current_time = datetime.now()
        overdue_count = base_query.filter(
            and_(
                Defect.due_date.isnot(None),
                Defect.due_date < current_time,
                Defect.status != DefectStatus.CLOSED
            )
        ).count()
        
        # 未分配缺陷数
        unassigned_count = base_query.filter(Defect.assignee_id.is_(None)).count()
        
        # 状态统计
        status_stats = self.db.query(
            Defect.status,
            func.count(Defect.id).label('count')
        ).filter(
            Defect.project_id == project_id if project_id else True
        ).group_by(Defect.status).all()
        
        status_statistics = []
        for status, count in status_stats:
            percentage = (count / total_count * 100) if total_count > 0 else 0
            status_statistics.append(DefectStatusStatistics(
                status=status,
                count=count,
                percentage=round(percentage, 2)
            ))
        
        # 优先级统计
        priority_stats = self.db.query(
            Defect.priority,
            func.count(Defect.id).label('count')
        ).filter(
            Defect.project_id == project_id if project_id else True
        ).group_by(Defect.priority).all()
        
        priority_statistics = []
        for priority, count in priority_stats:
            percentage = (count / total_count * 100) if total_count > 0 else 0
            priority_statistics.append(DefectPriorityStatistics(
                priority=priority,
                count=count,
                percentage=round(percentage, 2)
            ))
        
        # 类型统计
        type_stats = self.db.query(
            Defect.type,
            func.count(Defect.id).label('count')
        ).filter(
            Defect.project_id == project_id if project_id else True
        ).group_by(Defect.type).all()
        
        type_statistics = []
        for defect_type, count in type_stats:
            percentage = (count / total_count * 100) if total_count > 0 else 0
            type_statistics.append(DefectTypeStatistics(
                type=defect_type,
                count=count,
                percentage=round(percentage, 2)
            ))
        
        # 严重程度统计
        severity_stats = self.db.query(
            Defect.severity,
            func.count(Defect.id).label('count')
        ).filter(
            Defect.project_id == project_id if project_id else True
        ).group_by(Defect.severity).all()
        
        severity_statistics = []
        for severity, count in severity_stats:
            percentage = (count / total_count * 100) if total_count > 0 else 0
            severity_statistics.append(DefectSeverityStatistics(
                severity=severity,
                count=count,
                percentage=round(percentage, 2)
            ))
        
        # 趋势数据（最近30天）
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=29)  # 30天数据
        
        # 按日期统计新建、解决、关闭的缺陷数量
        trend_query = self.db.query(
            func.date(Defect.created_at).label('date'),
            func.count(Defect.id).label('created_count')
        ).filter(
            and_(
                func.date(Defect.created_at) >= start_date,
                func.date(Defect.created_at) <= end_date,
                Defect.project_id == project_id if project_id else True
            )
        ).group_by(func.date(Defect.created_at)).all()
        
        # 解决缺陷统计（通过状态历史表）
        resolved_query = self.db.query(
            func.date(DefectStatusHistory.changed_at).label('date'),
            func.count(DefectStatusHistory.id).label('resolved_count')
        ).join(Defect, DefectStatusHistory.defect_id == Defect.id).filter(
            and_(
                func.date(DefectStatusHistory.changed_at) >= start_date,
                func.date(DefectStatusHistory.changed_at) <= end_date,
                DefectStatusHistory.new_status == DefectStatus.RESOLVED,
                Defect.project_id == project_id if project_id else True
            )
        ).group_by(func.date(DefectStatusHistory.changed_at)).all()
        
        # 关闭缺陷统计
        closed_query = self.db.query(
            func.date(DefectStatusHistory.changed_at).label('date'),
            func.count(DefectStatusHistory.id).label('closed_count')
        ).join(Defect, DefectStatusHistory.defect_id == Defect.id).filter(
            and_(
                func.date(DefectStatusHistory.changed_at) >= start_date,
                func.date(DefectStatusHistory.changed_at) <= end_date,
                DefectStatusHistory.new_status == DefectStatus.CLOSED,
                Defect.project_id == project_id if project_id else True
            )
        ).group_by(func.date(DefectStatusHistory.changed_at)).all()
        
        # 构建趋势数据字典
        trend_dict = {}
        current_date = start_date
        while current_date <= end_date:
            trend_dict[current_date.strftime('%Y-%m-%d')] = {
                'created_count': 0,
                'resolved_count': 0,
                'closed_count': 0
            }
            current_date += timedelta(days=1)
        
        # 填充创建数据
        for date, count in trend_query:
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
            if date_str in trend_dict:
                trend_dict[date_str]['created_count'] = count
        
        # 填充解决数据
        for date, count in resolved_query:
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
            if date_str in trend_dict:
                trend_dict[date_str]['resolved_count'] = count
        
        # 填充关闭数据
        for date, count in closed_query:
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
            if date_str in trend_dict:
                trend_dict[date_str]['closed_count'] = count
        
        # 转换为趋势数据列表
        trend_data = []
        for date_str in sorted(trend_dict.keys()):
            data = trend_dict[date_str]
            trend_data.append(DefectTrendData(
                date=date_str,
                created_count=data['created_count'],
                resolved_count=data['resolved_count'],
                closed_count=data['closed_count']
            ))
        
        # 构建响应数据
        return DefectStatisticsResponse(
            total_count=total_count,
            open_count=open_count,
            closed_count=closed_count,
            overdue_count=overdue_count,
            unassigned_count=unassigned_count,
            status_statistics=status_statistics,
            priority_statistics=priority_statistics,
            type_statistics=type_statistics,
            severity_statistics=severity_statistics,
            trend_data=trend_data,
            project_id=project_id,
            project_name=project_name
        )
    
    def _apply_user_filter(self, query, current_user: User):
        """应用用户权限过滤条件"""
        user_filter = self.build_user_filter(current_user)
        if user_filter is not None:
            query = query.filter(user_filter)
        return query
    
    def build_user_filter(self, current_user: User):
        """构建用户权限过滤条件"""
        if current_user.role == UserRole.ADMIN:
            return None
        
        return or_(
            Defect.created_by == current_user.id,
            Defect.assignee_id == current_user.id,
            Defect.reporter_id == current_user.id,
            Defect.verified_by_id == current_user.id
        )
    
    def get_my_defects(self, current_user: User, limit: int = 10) -> List[Defect]:
        """获取用户相关的缺陷列表"""
        query = self.db.query(Defect).options(
            joinedload(Defect.reporter),
            joinedload(Defect.assignee),
            joinedload(Defect.handler),
            joinedload(Defect.project)
        )
        
        user_filter = self.build_user_filter(current_user)
        if user_filter is not None:
            query = query.filter(user_filter)
        
        return query.order_by(desc(Defect.created_at)).limit(limit).all()
    
    # ==================== CRUD操作 ====================
    
    def create_defect(self, defect_data: DefectCreate, current_user: User) -> Defect:
        """创建缺陷"""
        # 验证关联对象
        self.validate_project_exists(defect_data.project_id)
        
        if defect_data.assignee_id:
            self.validate_user_exists(defect_data.assignee_id, "执行人")
        
        if defect_data.reporter_id:
            self.validate_user_exists(defect_data.reporter_id, "报告人")
        
        if defect_data.verified_by_id:
            self.validate_user_exists(defect_data.verified_by_id, "验证人")
        
        if defect_data.parent_id:
            parent_defect = self.validate_defect_exists(defect_data.parent_id)
        
        # 处理tags字段
        tags_json = None
        if defect_data.tags:
            tags_json = json.dumps(defect_data.tags, ensure_ascii=False)
        
        # 创建缺陷对象
        defect = Defect(
            id=generate_defect_id(),
            title=defect_data.title,
            description=defect_data.description,
            status=defect_data.status,
            priority=defect_data.priority,
            type=defect_data.type,
            severity=defect_data.severity,
            project_id=defect_data.project_id,
            assignee_id=defect_data.assignee_id,
            reporter_id=defect_data.reporter_id or current_user.id,
            verified_by_id=defect_data.verified_by_id,
            version=defect_data.version,
            environment=defect_data.environment,
            steps_to_reproduce=defect_data.steps_to_reproduce,
            expected_result=defect_data.expected_result,
            actual_result=defect_data.actual_result,
            resolution=defect_data.resolution,
            parent_id=defect_data.parent_id,
            tags=tags_json,
            due_date=defect_data.due_date,
            source=defect_data.source,
            created_by=current_user.id,
            created_at=datetime.now()
        )
        
        self.db.add(defect)
        self.db.commit()
        self.db.refresh(defect)
        
        return defect
    
    # ==================== 批量操作方法 ====================
    
    def batch_assign_defects(self, defect_ids: List[str], assignee_id: Optional[str], 
                           current_user: User, comment: Optional[str] = None) -> Dict[str, Any]:
        """批量指派缺陷责任人"""
        from schemas.defect import BatchOperationResultItem, BatchOperationResponse
        
        results = []
        success_count = 0
        failed_count = 0
        
        # 验证执行人是否存在
        assignee = None
        if assignee_id:
            try:
                assignee = self.validate_user_exists(assignee_id, "执行人")
            except HTTPException as e:
                # 如果执行人不存在，所有操作都失败
                for defect_id in defect_ids:
                    results.append(BatchOperationResultItem(
                        defect_id=defect_id,
                        success=False,
                        message=f"执行人不存在: {e.detail}",
                        defect_title=None
                    ))
                    failed_count += 1
                
                return BatchOperationResponse(
                    total_count=len(defect_ids),
                    success_count=0,
                    failed_count=len(defect_ids),
                    results=results
                )
        
        # 批量处理每个缺陷
        for defect_id in defect_ids:
            try:
                # 验证缺陷是否存在
                defect = self.validate_defect_exists(defect_id)
                
                # 权限检查
                if not self.check_defect_permission(defect, current_user, "write"):
                    results.append(BatchOperationResultItem(
                        defect_id=defect_id,
                        success=False,
                        message="无权限操作此缺陷",
                        defect_title=defect.title
                    ))
                    failed_count += 1
                    continue
                
                # 记录旧的执行人
                old_assignee_id = defect.assignee_id
                
                # 更新执行人
                defect.assignee_id = assignee_id
                defect.updated_at = datetime.now()
                
                # 状态自动变更逻辑
                if not old_assignee_id and assignee_id:
                    if defect.status == DefectStatus.NEW:
                        defect.status = DefectStatus.ASSIGNED
                        self.create_status_history(defect.id, DefectStatus.NEW, DefectStatus.ASSIGNED, 
                                                 current_user.id, "缺陷已分配，状态自动变更")
                
                # 记录分配历史
                operation_comment = comment or (
                    f"批量分配给 {assignee.username}" if assignee else "批量取消分配"
                )
                
                self.create_status_history(defect.id, defect.status, defect.status, 
                                         current_user.id, operation_comment)
                
                results.append(BatchOperationResultItem(
                    defect_id=defect_id,
                    success=True,
                    message="分配成功",
                    defect_title=defect.title
                ))
                success_count += 1
                
            except HTTPException as e:
                results.append(BatchOperationResultItem(
                    defect_id=defect_id,
                    success=False,
                    message=e.detail,
                    defect_title=None
                ))
                failed_count += 1
            except Exception as e:
                results.append(BatchOperationResultItem(
                    defect_id=defect_id,
                    success=False,
                    message=f"操作失败: {str(e)}",
                    defect_title=None
                ))
                failed_count += 1
        
        # 提交事务
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"批量操作提交失败: {str(e)}")
        
        return BatchOperationResponse(
            total_count=len(defect_ids),
            success_count=success_count,
            failed_count=failed_count,
            results=results
        )
    
    def batch_delete_defects(self, defect_ids: List[str], current_user: User, 
                           comment: Optional[str] = None) -> Dict[str, Any]:
        """批量删除缺陷（软删除）"""
        from schemas.defect import BatchOperationResultItem, BatchOperationResponse
        
        results = []
        success_count = 0
        failed_count = 0
        
        # 批量处理每个缺陷
        for defect_id in defect_ids:
            try:
                # 验证缺陷是否存在
                defect = self.validate_defect_exists(defect_id)
                
                # 权限检查 - 只有创建者和管理员可以删除
                if not self.check_defect_permission(defect, current_user, "delete"):
                    results.append(BatchOperationResultItem(
                        defect_id=defect_id,
                        success=False,
                        message="无权限删除此缺陷",
                        defect_title=defect.title
                    ))
                    failed_count += 1
                    continue
                
                # 检查缺陷是否已删除
                if defect.is_deleted:
                    results.append(BatchOperationResultItem(
                        defect_id=defect_id,
                        success=False,
                        message="缺陷已被删除",
                        defect_title=defect.title
                    ))
                    failed_count += 1
                    continue
                
                # 软删除
                defect.is_deleted = True
                defect.deleted_at = datetime.now()
                defect.updated_at = datetime.now()
                
                # 记录删除历史
                operation_comment = comment or "批量删除缺陷"
                self.create_status_history(defect.id, defect.status, defect.status, 
                                         current_user.id, operation_comment)
                
                results.append(BatchOperationResultItem(
                    defect_id=defect_id,
                    success=True,
                    message="删除成功",
                    defect_title=defect.title
                ))
                success_count += 1
                
            except HTTPException as e:
                results.append(BatchOperationResultItem(
                    defect_id=defect_id,
                    success=False,
                    message=e.detail,
                    defect_title=None
                ))
                failed_count += 1
            except Exception as e:
                results.append(BatchOperationResultItem(
                    defect_id=defect_id,
                    success=False,
                    message=f"操作失败: {str(e)}",
                    defect_title=None
                ))
                failed_count += 1
        
        # 提交事务
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"批量操作提交失败: {str(e)}")
        
        return BatchOperationResponse(
            total_count=len(defect_ids),
            success_count=success_count,
            failed_count=failed_count,
            results=results
        )
    
    def update_defect(self, defect_id: str, defect_update: DefectUpdate, current_user: User) -> Defect:
        """更新缺陷"""
        defect = self.validate_defect_exists(defect_id)
        
        # 权限检查
        if not self.check_defect_permission(defect, current_user, "write"):
            raise HTTPException(status_code=403, detail="无权限修改此缺陷")
        
        # 验证关联对象
        update_data = defect_update.model_dump(exclude_unset=True)
        
        if 'project_id' in update_data:
            self.validate_project_exists(update_data['project_id'])
        
        if 'assignee_id' in update_data:
            self.validate_user_exists(update_data['assignee_id'], "执行人")
        
        if 'reporter_id' in update_data:
            self.validate_user_exists(update_data['reporter_id'], "报告人")
        
        if 'verified_by_id' in update_data:
            self.validate_user_exists(update_data['verified_by_id'], "验证人")
        
        if 'parent_id' in update_data and update_data['parent_id']:
            parent_defect = self.db.query(Defect).filter(Defect.id == update_data['parent_id']).first()
            if not parent_defect:
                raise HTTPException(status_code=404, detail="父缺陷不存在")
            if parent_defect.id == defect.id:
                raise HTTPException(status_code=400, detail="缺陷不能设置自己为父缺陷")
        
        # 记录状态变更
        old_status = defect.status
        new_status = update_data.get('status', old_status)
        
        # 处理tags字段
        if 'tags' in update_data and update_data['tags'] is not None:
            update_data['tags'] = json.dumps(update_data['tags'], ensure_ascii=False)
        
        # 更新缺陷字段
        for field, value in update_data.items():
            if hasattr(defect, field):
                setattr(defect, field, value)
        
        # 设置更新人和更新时间
        defect.updated_by = current_user.id
        defect.updated_at = datetime.now()
        
        # 如果状态发生变更，记录状态历史
        if old_status != new_status:
            self.create_status_history(defect.id, old_status, new_status, current_user.id,
                                     f"缺陷状态从 {old_status.value} 变更为 {new_status.value}")
        
        self.db.commit()
        self.db.refresh(defect)
        
        return defect
    
    def delete_defect(self, defect_id: str, current_user: User) -> bool:
        """删除缺陷（软删除）"""
        defect = self.validate_defect_exists(defect_id)
        
        # 权限检查
        if not self.check_defect_permission(defect, current_user, "delete"):
            raise HTTPException(status_code=403, detail="无权限删除此缺陷")
        
        # 检查是否有子缺陷
        child_defects = self.db.query(Defect).filter(Defect.parent_id == defect_id).count()
        if child_defects > 0:
            raise HTTPException(status_code=400, detail="存在子缺陷，无法删除")
        
        # 软删除
        defect.is_deleted = True
        defect.deleted_by = current_user.id
        defect.deleted_at = datetime.now()
        
        # 记录状态历史
        self.create_status_history(defect.id, defect.status, None, current_user.id, "缺陷已删除")
        
        self.db.commit()
        return True
    
    # ==================== 状态管理 ====================
    
    def validate_status_transition(self, old_status: DefectStatus, new_status: DefectStatus) -> bool:
        """验证状态转换的合法性"""
        valid_transitions = {
            DefectStatus.NEW: [DefectStatus.ASSIGNED, DefectStatus.IN_PROGRESS, DefectStatus.CLOSED],
            DefectStatus.ASSIGNED: [DefectStatus.IN_PROGRESS, DefectStatus.NEW, DefectStatus.CLOSED],
            DefectStatus.IN_PROGRESS: [DefectStatus.RESOLVED, DefectStatus.ASSIGNED, DefectStatus.CLOSED],
            DefectStatus.RESOLVED: [DefectStatus.VERIFIED, DefectStatus.REOPENED, DefectStatus.CLOSED],
            DefectStatus.VERIFIED: [DefectStatus.CLOSED, DefectStatus.REOPENED],
            DefectStatus.CLOSED: [DefectStatus.REOPENED],
            DefectStatus.REOPENED: [DefectStatus.ASSIGNED, DefectStatus.IN_PROGRESS, DefectStatus.CLOSED]
        }
        
        return new_status in valid_transitions.get(old_status, [])
    
    def change_defect_status(self, defect_id: str, new_status: DefectStatus, 
                           current_user: User, comment: Optional[str] = None) -> Defect:
        """变更缺陷状态"""
        defect = self.validate_defect_exists(defect_id)
        
        # 权限检查
        if not self.check_defect_permission(defect, current_user, "status_change"):
            raise HTTPException(status_code=403, detail="无权限修改此缺陷状态")
        
        old_status = defect.status
        if old_status == new_status:
            raise HTTPException(status_code=400, detail="新状态与当前状态相同")
        
        # 验证状态转换
        if not self.validate_status_transition(old_status, new_status):
            raise HTTPException(status_code=400, detail=f"不允许从 {old_status.value} 变更为 {new_status.value}")
        
        # 更新状态
        defect.status = new_status
        defect.updated_by = current_user.id
        defect.updated_at = datetime.now()
        
        # 如果状态变更为已关闭，设置关闭时间
        if new_status == DefectStatus.CLOSED:
            defect.closed_at = datetime.now()
        
        # 记录状态历史
        self.create_status_history(defect.id, old_status, new_status, current_user.id,
                                 comment or f"状态从 {old_status.value} 变更为 {new_status.value}")
        
        self.db.commit()
        self.db.refresh(defect)
        
        return defect
    
    def create_status_history(self, defect_id: str, old_status: DefectStatus, 
                            new_status: Optional[DefectStatus], changed_by: str, comment: str):
        """创建状态历史记录"""
        status_history = DefectStatusHistory(
            defect_id=defect_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            comment=comment
        )
        self.db.add(status_history)
    
    def get_defect_status_history(self, defect_id: str, current_user: User) -> List[DefectStatusHistory]:
        """获取缺陷状态历史"""
        defect = self.validate_defect_exists(defect_id)
        
        # 权限检查
        if not self.check_defect_permission(defect, current_user, "read"):
            raise HTTPException(status_code=403, detail="无权限查看此缺陷历史")
        
        return self.db.query(DefectStatusHistory).options(
            joinedload(DefectStatusHistory.changed_by_user)
        ).filter(
            DefectStatusHistory.defect_id == defect_id
        ).order_by(desc(DefectStatusHistory.changed_at)).all()
    
    # ==================== 分配管理 ====================
    
    def assign_defect(self, defect_id: str, assign_data: DefectAssign, current_user: User) -> Defect:
        """分配缺陷"""
        defect = self.validate_defect_exists(defect_id)
        
        # 权限检查：非管理员只能分配自己创建的缺陷
        if current_user.role != UserRole.ADMIN:
            if defect.created_by != current_user.id:
                raise HTTPException(status_code=403, detail="无权限分配此缺陷")
        
        assignee = None
        if assign_data.assignee_id:
            assignee = self.validate_user_exists(assign_data.assignee_id, "执行人")
        
        # 记录旧的分配信息
        old_assignee_id = defect.assignee_id
        old_assignee_name = defect.assignee_name
        
        # 更新分配信息
        defect.assignee_id = assign_data.assignee_id
        defect.assignee_name = assignee.name if assignee else None
        defect.updated_by = current_user.id
        defect.updated_at = datetime.now()
        
        # 如果从未分配变为已分配，自动变更状态
        if not old_assignee_id and assign_data.assignee_id:
            if defect.status == DefectStatus.NEW:
                defect.status = DefectStatus.ASSIGNED
                self.create_status_history(defect.id, DefectStatus.NEW, DefectStatus.ASSIGNED, 
                                         current_user.id, "缺陷已分配，状态自动变更")
        
        # 记录分配历史
        comment = assign_data.comment or (
            f"缺陷分配给 {assignee.username}" if assignee else "取消缺陷分配"
        )
        
        self.create_status_history(defect.id, defect.status, defect.status, current_user.id, comment)
        
        self.db.commit()
        self.db.refresh(defect)
        
        return defect