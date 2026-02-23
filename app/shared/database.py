from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import settings

# URL do banco de dados
DATABASE_URL = settings.DATABASE_URL

# Cria o engine do SQLAlchemy
engine = create_async_engine(DATABASE_URL)
# Cria a sessão local do SQLAlchemy
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


# Dependency para obter a sessão do banco de dados
async def get_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
