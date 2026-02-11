from core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Credenciais do banco de dados
DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
DB_HOST = 'localhost'  # settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_NAME = settings.DB_NAME

# Cria a URL do banco de dados
# O formato é: dialect+driver://username:password@host:port/database
DATABASE_URL = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
# Cria o engine do SQLAlchemy
engine = create_engine(DATABASE_URL)
# Cria a sessão local do SQLAlchemy
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency para obter a sessão do banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
