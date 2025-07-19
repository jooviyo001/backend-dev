import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入模型和配置
from app.core.config import settings
from app.core.database import Base
from app.models import *  # 导入所有模型

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url():
    """获取数据库URL"""
    # 优先使用环境变量中的数据库URL
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    
    # 如果没有环境变量，使用配置文件中的URL
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """运行迁移"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        # 自定义比较函数
        compare_server_default=True,
        # 包含对象名称
        include_object=include_object,
        # 渲染项目
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """决定是否包含对象在迁移中"""
    # 排除某些表或对象
    if type_ == "table" and name in ["alembic_version"]:
        return False
    
    # 排除临时表
    if type_ == "table" and name.startswith("temp_"):
        return False
    
    # 排除测试表
    if type_ == "table" and name.startswith("test_"):
        return False
    
    return True


def render_item(type_, obj, autogen_context):
    """自定义渲染项目"""
    # 可以在这里自定义如何渲染迁移脚本中的项目
    return False


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 获取数据库URL
    database_url = get_database_url()
    
    # 为异步操作配置引擎
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # 检查是否是异步数据库URL
    database_url = get_database_url()
    
    if "postgresql+asyncpg" in database_url or "mysql+aiomysql" in database_url:
        # 异步数据库
        asyncio.run(run_async_migrations())
    else:
        # 同步数据库
        from sqlalchemy import create_engine
        
        connectable = create_engine(
            database_url,
            poolclass=pool.NullPool,
        )
        
        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()