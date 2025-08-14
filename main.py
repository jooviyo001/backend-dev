import os
from fastapi.security import HTTPBearer
import uvicorn

# 导入数据库相关
from models.database import engine, Base
from utils.snowflake import init_snowflake
from utils.database_initializer import init_database
from utils.database_schema_manager import ensure_database_schema

# 导入配置模块
from config import create_app, configure_middleware, configure_exception_handlers
from config.app_config import configure_routes

# 初始化雪花算法（机器ID可以通过环境变量配置）
machine_id = int(os.getenv("MACHINE_ID", "1"))  # 默认机器ID为1
init_snowflake(machine_id)

# 检查和更新数据库表结构
print("🔍 正在检查数据库表结构...")
try:
    schema_success = ensure_database_schema()
    if schema_success:
        print("✅ 数据库表结构检查完成")
    else:
        print("❌ 数据库表结构检查失败，但继续启动")
except Exception as e:
    print(f"❌ 数据库表结构检查出错: {e}")
    print("⚠️  使用基础表创建方式...")
    # 如果新的检查方式失败，回退到原有方式
    Base.metadata.create_all(bind=engine)

# 初始化数据库数据（仅在开发环境）
try:
    init_database(force=False)
except Exception as e:
    print(f"⚠️  数据库初始化跳过: {e}")

# 创建FastAPI应用
app = create_app()

# 配置中间件
configure_middleware(app)

# 配置异常处理器
configure_exception_handlers(app)

# 配置路由
configure_routes(app)

# 安全配置
security = HTTPBearer()

if __name__ == "__main__":
    # 从环境变量获取配置，如果没有则使用默认值
    from dotenv import load_dotenv
    load_dotenv()
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🚀 启动项目管理系统API服务器...")
    print(f"📍 地址: http://{host}:{port}")
    print(f"🔧 调试模式: {debug}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    print(f"📖 ReDoc文档: http://{host}:{port}/redoc")
    
    if debug:
        # 开发模式使用import string以支持reload
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=True,
            log_level="debug"
        )
    else:
        # 生产模式直接传递app对象
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )