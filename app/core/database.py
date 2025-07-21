from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings

# 创建基础模型类
Base = declarative_base()

# 全局变量，用于存储引擎和会话
engine = None
AsyncSessionLocal = None

def init_db_connection():
    global engine, AsyncSessionLocal
    if settings.DATABASE_URL.startswith("sqlite+aiosqlite:///") or \
       "postgresql+asyncpg" in settings.DATABASE_URL or \
       "mysql+aiomysql" in settings.DATABASE_URL:
        # 异步数据库
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True
        )
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    else:
        # 同步数据库 (例如：sqlite:///./sql_app.db)
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_pre_ping=True
        )
        AsyncSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )

# 数据库依赖注入
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise Exception("Database connection not initialized. Call init_db_connection() first.")

    # 根据会话类型返回异步或同步会话
    if isinstance(AsyncSessionLocal, async_sessionmaker):
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    else:
        # For synchronous sessions, run in a thread pool executor to avoid blocking the event loop
        # This part might need adjustment if the FastAPI app is purely async.
        # For Alembic, this path won't be taken during model inspection.
        with AsyncSessionLocal() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()