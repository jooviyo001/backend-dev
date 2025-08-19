# 移除 permission_middleware 的导入以避免循环依赖
# 需要使用时请直接从 utils.permission_middleware 导入
from .permission_cache import (
    PermissionCache,
    PermissionCacheConfig,
    PermissionCacheMetrics,
    permission_cache,
    cached_permission_check,
    get_permission_cache
)