"""
Configuração do banco de dados: engine, session factory e dependency.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import settings

# Engine assíncrono — a conexão real só é aberta na primeira operação
if settings.ENVIRONMENT == 'production':
    engine = create_async_engine(
        settings.RESOLVED_DATABASE_URL,
        future=True,
        connect_args={'ssl': 'require'},
    )
else:
    engine = create_async_engine(settings.RESOLVED_DATABASE_URL, future=True)

# Factory de sessões — expire_on_commit=False evita lazy-load após commit
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


async def get_session():
    """FastAPI dependency que fornece uma sessão async por requisição."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
