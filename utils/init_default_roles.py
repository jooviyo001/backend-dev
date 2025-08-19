"""默认角色初始化模块
在系统启动时创建默认的系统角色
"""

from sqlalchemy.orm import Session
from models.database import get_db
from models.role import Role
from services.role_service import RoleService
from schemas.role import RoleCreate
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 默认系统角色配置
DEFAULT_ROLES = [
    {
        "code": "SYSTEM_ADMIN",
        "name": "系统管理员",
        "description": "拥有系统最高权限，可以管理所有功能模块",
        "is_active": True
    },
    {
        "code": "PROJECT_MANAGER",
        "name": "项目经理",
        "description": "负责项目管理，可以创建和管理项目、分配任务",
        "is_active": True
    },
    {
        "code": "TEAM_LEADER",
        "name": "团队负责人",
        "description": "负责团队管理，可以管理团队成员和任务分配",
        "is_active": True
    },
    {
        "code": "DEVELOPER",
        "name": "开发人员",
        "description": "负责开发工作，可以处理分配的开发任务",
        "is_active": True
    },
    {
        "code": "TESTER",
        "name": "测试人员",
        "description": "负责测试工作，可以创建和执行测试用例",
        "is_active": True
    },
    {
        "code": "DESIGNER",
        "name": "设计师",
        "description": "负责UI/UX设计工作，可以管理设计相关任务",
        "is_active": True
    },
    {
        "code": "ANALYST",
        "name": "业务分析师",
        "description": "负责需求分析和业务梳理工作",
        "is_active": True
    },
    {
        "code": "VIEWER",
        "name": "查看者",
        "description": "只读权限，可以查看项目和任务信息",
        "is_active": True
    }
]

def create_default_role(db: Session, role_config: dict) -> Role:
    """创建默认角色
    
    Args:
        db: 数据库会话
        role_config: 角色配置字典
        
    Returns:
        Role: 创建或已存在的角色对象
    """
    # 检查角色是否已存在
    existing_role = db.query(Role).filter(Role.code == role_config["code"]).first()
    if existing_role:
        logger.info(f"角色 {role_config['code']} 已存在，跳过创建")
        return existing_role
    
    # 创建角色服务实例
    role_service = RoleService(db)
    
    # 创建角色数据对象
    role_data = RoleCreate(
        code=role_config["code"],
        name=role_config["name"],
        description=role_config["description"],
        is_active=role_config["is_active"]
    )
    
    try:
        # 创建角色
        new_role = role_service.create_role(role_data)
        logger.info(f"成功创建角色: {new_role.code} - {new_role.name}")
        return new_role
    except Exception as e:
        logger.error(f"创建角色 {role_config['code']} 时发生错误: {str(e)}")
        # 如果是因为角色已存在导致的错误，尝试查询现有角色
        existing_role = db.query(Role).filter(Role.code == role_config["code"]).first()
        if existing_role:
            return existing_role
        raise

def init_default_roles():
    """初始化默认角色"""
    logger.info("开始初始化默认系统角色...")
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 创建默认角色
        created_roles = []
        for role_config in DEFAULT_ROLES:
            role = create_default_role(db, role_config)
            created_roles.append(role)
        
        logger.info(f"默认角色初始化完成，共创建/检查了 {len(created_roles)} 个角色")
        
        # 输出角色信息摘要
        logger.info("=== 默认系统角色信息 ===")
        for role in created_roles:
            logger.info(f"角色编码: {role.code}")
            logger.info(f"角色名称: {role.name}")
            logger.info(f"角色描述: {role.description}")
            logger.info(f"是否启用: {role.is_active}")
            logger.info("---")
        
        return True
        
    except Exception as e:
        logger.error(f"初始化默认角色时发生错误: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def check_default_roles_exist() -> bool:
    """检查默认角色是否已存在"""
    db = next(get_db())
    try:
        for role_config in DEFAULT_ROLES:
            role = db.query(Role).filter(Role.code == role_config["code"]).first()
            if not role:
                return False
        return True
    finally:
        db.close()

def get_role_by_code(code: str) -> Role:
    """根据角色编码获取角色
    
    Args:
        code: 角色编码
        
    Returns:
        Role: 角色对象，如果不存在则返回None
    """
    db = next(get_db())
    try:
        return db.query(Role).filter(Role.code == code).first()
    finally:
        db.close()

if __name__ == "__main__":
    # 直接运行此脚本时初始化默认角色
    init_default_roles()