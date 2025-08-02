# 状态码常量定义

# 成功状态码
SUCCESS = "200"                # 操作成功
CREATED = "201"               # 创建成功
ACCEPTED = "202"              # 请求已接受

# 客户端错误状态码
BAD_REQUEST = "400"           # 请求参数错误
UNAUTHORIZED = "401"          # 未授权
FORBIDDEN = "403"             # 禁止访问
NOT_FOUND = "404"             # 资源不存在
METHOD_NOT_ALLOWED = "405"    # 方法不允许
CONFLICT = "409"              # 资源冲突
TOO_MANY_REQUESTS = "429"     # 请求过多

# 服务器错误状态码
INTERNAL_ERROR = "500"        # 服务器内部错误
NOT_IMPLEMENTED = "501"       # 未实现
BAD_GATEWAY = "502"           # 网关错误
SERVICE_UNAVAILABLE = "503"   # 服务不可用

# 业务状态码（自定义）
BUSINESS_ERROR = "10000"      # 业务通用错误
VALIDATION_ERROR = "10001"    # 数据验证错误
DATABASE_ERROR = "10002"      # 数据库操作错误
AUTH_ERROR = "10003"          # 认证相关错误
PERMISSION_ERROR = "10004"    # 权限相关错误
RESOURCE_ERROR = "10005"      # 资源相关错误
FILE_ERROR = "10006"          # 文件操作错误

# 状态码描述映射
STATUS_MESSAGE = {
    SUCCESS: "操作成功",
    CREATED: "创建成功",
    ACCEPTED: "请求已接受",
    
    BAD_REQUEST: "请求参数错误",
    UNAUTHORIZED: "未授权",
    FORBIDDEN: "禁止访问",
    NOT_FOUND: "资源不存在",
    METHOD_NOT_ALLOWED: "方法不允许",
    CONFLICT: "资源冲突",
    TOO_MANY_REQUESTS: "请求过多",
    
    INTERNAL_ERROR: "服务器内部错误",
    NOT_IMPLEMENTED: "未实现",
    BAD_GATEWAY: "网关错误",
    SERVICE_UNAVAILABLE: "服务不可用",
    
    BUSINESS_ERROR: "业务通用错误",
    VALIDATION_ERROR: "数据验证错误",
    DATABASE_ERROR: "数据库操作错误",
    AUTH_ERROR: "认证相关错误",
    PERMISSION_ERROR: "权限相关错误",
    RESOURCE_ERROR: "资源相关错误",
    FILE_ERROR: "文件操作错误"
}

def get_message(code):
    """根据状态码获取对应的消息"""
    return STATUS_MESSAGE.get(code, "未知状态")