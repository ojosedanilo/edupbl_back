"""
Configurações da aplicação carregadas via variáveis de ambiente / .env.

Em produção, defina as variáveis diretamente no ambiente (não use .env).
Em desenvolvimento, crie um arquivo .env na raiz do projeto
(veja .env.example para referência).
"""

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Localiza o .env na raiz do projeto independente de onde o processo roda
BASE_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = BASE_DIR / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, case_sensitive=True, env_file_encoding='utf-8'
    )

    # ── Aplicação ──────────────────────────────────────────────────── #
    APP_NAME: str = 'EduPBL'
    DEBUG: bool = False
    ENVIRONMENT: str = 'development'  # 'development' | 'production'
    API_URL: str = 'http://localhost:8000/'

    # ── Cookies ────────────────────────────────────────────────────── #
    # Computed fields derivados de ENVIRONMENT.
    # TODO: remover os valores fixos e restaurar a lógica comentada
    #       ao separar os ambientes de dev e produção.

    @computed_field
    @property
    def COOKIE_SAME_SITE(self) -> str:
        # Produção exige 'none' para cookies cross-origin (frontend ≠ backend).
        # Desenvolvimento usaria 'lax', mas está fixo em 'none' por ora.
        return 'none'
        # return 'none' if self.ENVIRONMENT == 'production' else 'lax'

    @computed_field
    @property
    def COOKIE_SECURE(self) -> bool:
        # 'none' para SameSite exige Secure=True — mesmo em dev.
        return True
        # return self.ENVIRONMENT == 'production'

    # ── Autenticação JWT ───────────────────────────────────────────── #
    SECRET_KEY: str = 'test-secret-key-not-for-production'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 dias

    # Parâmetros do Argon2 (hash de senhas)
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_TIME_COST: int = 3

    # ── Banco de dados ─────────────────────────────────────────────── #
    DB_USER: str = 'edupbl'
    DB_PASSWORD: str = 'edupbl'
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_NAME: str = 'edupbl'
    DATABASE_URL: str = (
        f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@localhost:5432/{DB_NAME}'
    )


settings = Settings()
