from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Acha a raiz do projeto automaticamente
BASE_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = BASE_DIR / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, case_sensitive=True, env_file_encoding='utf-8'
    )

    # ----- App -----
    APP_NAME: str = 'EduPBL'
    DEBUG: bool = False
    # !!! Mudar para 'production' na produção
    ENVIRONMENT: str = 'development'  # 'development' ou 'production'
    API_URL: str = 'http://localhost:8000/'
    COOKIE_SAME_SITE: str = 'none'
    #
    COOKIE_SECURE: bool = True if ENVIRONMENT == 'production' else False

    # ----- Autenticação -----
    SECRET_KEY: str = 'test-secret-key-not-for-production'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 dias
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_TIME_COST: int = 3

    # ----- Banco -----
    DB_USER: str = 'edupbl'
    DB_PASSWORD: str = 'edupbl'
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_NAME: str = 'edupbl'
    DATABASE_URL: str = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@localhost:5432/{DB_NAME}'


settings = Settings()
