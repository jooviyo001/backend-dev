"""
默认用户初始化模块
在系统启动时创建默认的超管、项目经理和普通用户账户
"""

from sqlalchemy.orm import Session
from models.database import get_db
from models.models import User, UserRole, Organization
from utils.auth import get_password_hash
from utils.snowflake import generate_snowflake_id
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 默认用户配置
DEFAULT_USERS = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin123",
        "full_name": "系统管理员",
        "role": UserRole.ADMIN,
        "is_verified": True,
        "is_active": True
    },
    {
        "username": "manager",
        "email": "manager@example.com", 
        "password": "manager123",
        "full_name": "项目经理",
        "role": UserRole.MANAGER,
        "is_verified": True,
        "is_active": True
    },
    {
        "username": "developer",
        "email": "developer@example.com",
        "password": "developer123", 
        "full_name": "开发人员",
        "role": UserRole.DEVELOPER,
        "is_verified": True,
        "is_active": True
    }
]

def create_default_organization(db: Session) -> Organization:
    """创建默认组织"""
    # 检查是否已存在默认组织
    existing_org = db.query(Organization).filter(Organization.name == "默认组织").first()
    if existing_org:
        logger.info("默认组织已存在，跳过创建")
        return existing_org
    
    # 创建默认组织
    default_org = Organization(
        id=generate_snowflake_id(),
        name="默认组织",
        description="系统默认组织，用于管理初始用户和项目",
        is_active=True
    )
    
    db.add(default_org)
    db.commit()
    db.refresh(default_org)
    
    logger.info(f"创建默认组织成功: {default_org.name} (ID: {default_org.id})")
    return default_org

def create_default_user(db: Session, user_config: dict) -> User:
    """创建单个默认用户"""
    # 检查用户是否已存在
    existing_user = db.query(User).filter(
        (User.username == user_config["username"]) | 
        (User.email == user_config["email"])
    ).first()
    
    if existing_user:
        logger.info(f"用户 {user_config['username']} 已存在，跳过创建")
        return existing_user
    
    # 创建新用户
    user = User(
        username=user_config["username"],
        email=user_config["email"],
        password_hash=get_password_hash(user_config["password"]),
        full_name=user_config["full_name"],
        role=user_config["role"],
        is_verified=user_config["is_verified"],
        is_active=user_config["is_active"]
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"创建用户成功: {user.username} ({user.role.value}) - {user.email}")
    return user

def init_default_users():
    """初始化默认用户"""
    logger.info("开始初始化默认用户...")
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 创建默认组织
        default_org = create_default_organization(db)
        
        # 创建默认用户
        created_users = []
        for user_config in DEFAULT_USERS:
            user = create_default_user(db, user_config)
            created_users.append(user)
            
            # 将用户添加到默认组织
            if user not in default_org.members:
                default_org.members.append(user)
        
        # 提交组织成员关系
        db.commit()
        
        logger.info(f"默认用户初始化完成，共创建/检查了 {len(created_users)} 个用户")
        
        # 输出用户信息摘要
        logger.info("=== 默认用户账户信息 ===")
        for user_config in DEFAULT_USERS:
            logger.info(f"角色: {user_config['role'].value}")
            logger.info(f"用户名: {user_config['username']}")
            logger.info(f"邮箱: {user_config['email']}")
            logger.info(f"密码: {user_config['password']}")
            logger.info(f"姓名: {user_config['full_name']}")
            logger.info("---")
        
        return True
        
    except Exception as e:
        logger.error(f"初始化默认用户时发生错误: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def check_default_users_exist() -> bool:
    """检查默认用户是否已存在"""
    db = next(get_db())
    try:
        for user_config in DEFAULT_USERS:
            user = db.query(User).filter(User.username == user_config["username"]).first()
            if not user:
                return False
        return True
    finally:
        db.close()

if __name__ == "__main__":
    # 直接运行此脚本时初始化默认用户
    init_default_users()