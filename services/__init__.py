"""服务层模块初始化文件

提供服务层的统一导入接口
"""

from .permission_service import PermissionService, get_permission_service

from .task_service import TaskService

__all__ = [
    "TaskService"
]