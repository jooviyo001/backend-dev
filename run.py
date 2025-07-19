#!/usr/bin/env python3
"""
应用程序启动脚本
用于在生产环境中启动FastAPI应用程序
"""

import os
import sys
import uvicorn
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="启动项目管理系统API服务器")
    
    parser.add_argument(
        "--host",
        type=str,
        default=settings.server_host,
        help=f"服务器主机地址 (默认: {settings.server_host})"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=settings.server_port,
        help=f"服务器端口 (默认: {settings.server_port})"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=settings.server_workers,
        help=f"工作进程数 (默认: {settings.server_workers})"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        default=settings.is_development,
        help="启用自动重载 (开发模式)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error", "critical"],
        default=settings.log_level.lower(),
        help=f"日志级别 (默认: {settings.log_level.lower()})"
    )
    
    parser.add_argument(
        "--env",
        type=str,
        choices=["development", "production", "testing"],
        default=settings.environment,
        help=f"运行环境 (默认: {settings.environment})"
    )
    
    parser.add_argument(
        "--ssl-keyfile",
        type=str,
        help="SSL私钥文件路径"
    )
    
    parser.add_argument(
        "--ssl-certfile",
        type=str,
        help="SSL证书文件路径"
    )
    
    parser.add_argument(
        "--access-log",
        action="store_true",
        default=True,
        help="启用访问日志"
    )
    
    parser.add_argument(
        "--no-access-log",
        action="store_true",
        help="禁用访问日志"
    )
    
    return parser.parse_args()

def validate_ssl_files(keyfile: str, certfile: str) -> bool:
    """验证SSL文件是否存在"""
    if keyfile and not Path(keyfile).exists():
        logger.error(f"SSL私钥文件不存在: {keyfile}")
        return False
    
    if certfile and not Path(certfile).exists():
        logger.error(f"SSL证书文件不存在: {certfile}")
        return False
    
    return True

def setup_environment(env: str):
    """设置环境变量"""
    os.environ["ENVIRONMENT"] = env
    
    # 根据环境设置其他变量
    if env == "production":
        os.environ["DEBUG"] = "false"
        os.environ["LOG_LEVEL"] = "INFO"
    elif env == "development":
        os.environ["DEBUG"] = "true"
        os.environ["LOG_LEVEL"] = "DEBUG"
    elif env == "testing":
        os.environ["DEBUG"] = "false"
        os.environ["LOG_LEVEL"] = "WARNING"

def check_dependencies():
    """检查必要的依赖"""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import redis
        logger.info("所有必要依赖已安装")
        return True
    except ImportError as e:
        logger.error(f"缺少必要依赖: {e}")
        logger.error("请运行: pip install -r requirements.txt")
        return False

def check_database_connection():
    """检查数据库连接"""
    try:
        from app.core.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("数据库连接正常")
        return True
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return False

def check_redis_connection():
    """检查Redis连接"""
    try:
        import redis
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True
        )
        r.ping()
        logger.info("Redis连接正常")
        return True
    except Exception as e:
        logger.warning(f"Redis连接失败: {e}")
        logger.warning("应用程序将在没有Redis的情况下运行")
        return False

def pre_start_checks():
    """启动前检查"""
    logger.info("执行启动前检查...")
    
    checks = [
        ("依赖检查", check_dependencies),
        ("数据库连接", check_database_connection),
        ("Redis连接", check_redis_connection),
    ]
    
    failed_checks = []
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                failed_checks.append(check_name)
        except Exception as e:
            logger.error(f"{check_name}失败: {e}")
            failed_checks.append(check_name)
    
    if failed_checks:
        logger.warning(f"以下检查失败: {', '.join(failed_checks)}")
        if "依赖检查" in failed_checks or "数据库连接" in failed_checks:
            logger.error("关键检查失败，无法启动应用程序")
            return False
    
    logger.info("启动前检查完成")
    return True

def main():
    """主函数"""
    args = parse_args()
    
    # 设置环境
    setup_environment(args.env)
    
    # 显示启动信息
    logger.info(f"启动 {settings.app_name} v{settings.app_version}")
    logger.info(f"环境: {args.env}")
    logger.info(f"主机: {args.host}")
    logger.info(f"端口: {args.port}")
    logger.info(f"工作进程: {args.workers}")
    logger.info(f"日志级别: {args.log_level}")
    
    # SSL配置
    ssl_config = {}
    if args.ssl_keyfile and args.ssl_certfile:
        if validate_ssl_files(args.ssl_keyfile, args.ssl_certfile):
            ssl_config = {
                "ssl_keyfile": args.ssl_keyfile,
                "ssl_certfile": args.ssl_certfile
            }
            logger.info("启用SSL/TLS")
        else:
            logger.error("SSL配置无效，使用HTTP")
    
    # 执行启动前检查
    if not pre_start_checks():
        sys.exit(1)
    
    # 访问日志配置
    access_log = args.access_log and not args.no_access_log
    
    # 构建uvicorn配置
    config = {
        "app": "app.main:app",
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
        "access_log": access_log,
        "use_colors": args.env == "development",
        "reload": args.reload,
        **ssl_config
    }
    
    # 在生产环境中使用多个worker
    if args.env == "production" and not args.reload:
        config["workers"] = args.workers
        logger.info(f"使用 {args.workers} 个工作进程")
    
    try:
        logger.info("启动服务器...")
        uvicorn.run(**config)
    
    except KeyboardInterrupt:
        logger.info("服务器被用户停止")
    
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()