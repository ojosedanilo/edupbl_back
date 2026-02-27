from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Acha a raiz do projeto automaticamente
BASE_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = BASE_DIR / 'example.env'  # !!! Mudar para .env na produção


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, case_sensitive=True, env_file_encoding='utf-8'
    )

    APP_NAME: str = 'EduPBL'
    DEBUG: bool = False
    ENVIRONMENT: str = 'development'  # 'development' ou 'production'

    # Banco
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 dias

    ARGON2_MEMORY_COST: int = 65536
    ARGON2_TIME_COST: int = 3


settings = Settings()
