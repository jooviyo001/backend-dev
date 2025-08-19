"""权限检查工具模块
提供用户权限验证功能
"""
from models.user import User
from models.enums import UserRole


def check_permission(user: User, permission: str) -> bool:
    """检查用户是否具有指定权限
    
    Args:
        user: 用户对象
        permission: 权限字符串，格式为 "resource:action"
        
    Returns:
        bool: 是否具有权限
    """
    if not user or not user.is_active:
        return False
    
    # 管理员拥有所有权限
    if user.role == UserRole.ADMIN:
        return True
    
    # 解析权限字符串
    try:
        resource, action = permission.split(":")
    except ValueError:
        return False
    
    # 根据资源和操作检查权限
    if resource == "comment":
        if action in ["create", "read"]:
            # 所有用户都可以创建和查看评论
            return True
        elif action in ["update", "delete"]:
            # 管理员和经理可以修改/删除任何评论
            return user.role in [UserRole.ADMIN, UserRole.MANAGER]
    
    # 默认拒绝
    return False


def has_admin_permission(user: User) -> bool:
    """检查用户是否具有管理员权限"""
    return user and user.is_active and user.role == UserRole.ADMIN


def has_manager_permission(user: User) -> bool:
    """检查用户是否具有管理员或经理权限"""
    return user and user.is_active and user.role in [UserRole.ADMIN, UserRole.MANAGER]