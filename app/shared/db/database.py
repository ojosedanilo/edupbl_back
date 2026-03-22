from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import settings

# URL do banco de dados
DATABASE_URL = settings.DATABASE_URL

# Cria o engine do SQLAlchemy (nao conecta ate a primeira operacao)
engine = create_async_engine(DATABASE_URL, future=True)
# Cria a sessao local do SQLAlchemy
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


# Dependency para obter a sessao do banco de dados
async def get_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
