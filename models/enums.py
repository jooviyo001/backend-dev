"""
枚举定义模块
包含系统中所有的枚举类型定义
"""
import enum


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    TODO = "todo"                # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    REVIEW = "review"            # 审核中
    DONE = "done"                # 已完成
    CANCELLED = "cancelled"      # 已取消


class TaskPriority(str, enum.Enum):
    """任务优先级枚举"""
    LOW = "low"        # 低优先级
    MEDIUM = "medium"  # 中等优先级
    HIGH = "high"      # 高优先级
    URGENT = "urgent"  # 紧急


class TaskType(str, enum.Enum):
    """任务类型枚举"""
    FEATURE = "feature"              # 功能开发
    BUG = "bug"                      # 缺陷修复
    IMPROVEMENT = "improvement"      # 改进优化
    DOCUMENTATION = "documentation"  # 文档编写
    TEST = "test"                    # 测试任务


class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    PLANNING = "planning"      # 规划中
    ACTIVE = "active"          # 进行中
    ON_HOLD = "on_hold"        # 暂停
    COMPLETED = "completed"    # 已完成
    ARCHIVED = "archived"      # 已归档


class ProjectPriority(str, enum.Enum):
    """项目优先级枚举"""
    LOW = "low"        # 低优先级
    MEDIUM = "medium"  # 中等优先级
    HIGH = "high"      # 高优先级
    URGENT = "urgent"  # 紧急


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"      # 系统管理员
    MANAGER = "manager"  # 管理者
    MEMBER = "member"    # 普通成员
    USER = "user"        # 普通用户


class MemberRole(str, enum.Enum):
    """组织成员角色枚举"""
    ADMIN = "admin"      # 管理员
    MANAGER = "manager"  # 经理
    MEMBER = "member"    # 普通成员
    USER = "user"        # 普通用户


class OrganizationType(str, enum.Enum):
    """组织类型枚举"""
    COMPANY = "company"        # 公司
    DEPARTMENT = "department"  # 部门
    TEAM = "team"              # 团队
    GROUP = "group"            # 小组


class OrganizationStatus(str, enum.Enum):
    """组织状态枚举"""
    ACTIVE = "active"      # 活跃
    INACTIVE = "inactive"  # 非活跃


class DefectStatus(str, enum.Enum):
    """缺陷状态枚举"""
    NEW = "new"                    # 新建
    ASSIGNED = "assigned"          # 已分配
    IN_PROGRESS = "in_progress"    # 处理中
    RESOLVED = "resolved"          # 已解决
    VERIFIED = "verified"          # 已验证
    CLOSED = "closed"              # 已关闭
    REOPENED = "reopened"          # 重新打开


class DefectPriority(str, enum.Enum):
    """缺陷优先级枚举"""
    LOW = "low"        # 低优先级
    MEDIUM = "medium"  # 中等优先级
    HIGH = "high"      # 高优先级
    URGENT = "urgent"  # 紧急


class DefectType(str, enum.Enum):
    """缺陷类型枚举"""
    BUG = "bug"                    # 功能缺陷
    UI_BUG = "ui_bug"              # 界面缺陷
    PERFORMANCE = "performance"    # 性能问题
    SECURITY = "security"          # 安全问题
    COMPATIBILITY = "compatibility" # 兼容性问题


class DefectSeverity(str, enum.Enum):
    """缺陷严重程度枚举"""
    CRITICAL = "critical"  # 严重
    MAJOR = "major"        # 重要
    MODERATE = "moderate"  # 一般
    MINOR = "minor"        # 轻微
    TRIVIAL = "trivial"    # 微不足道