"""
Configurações da aplicação carregadas via variáveis de ambiente / .env.

Em produção, defina as variáveis diretamente no ambiente (não use .env).
Em desenvolvimento, crie um arquivo .env na raiz do projeto
(veja .env.example para referência).
"""

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Localiza o .env na raiz do projeto independente de onde o processo roda.
# parents[3]: app/core/settings.py → app/core → app → backend → raiz_projeto
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / '.env'

# ── Diretórios de dados ────────────────────────────────────────────────── #
# Fonte única de verdade para todos os paths de data/.
# Módulos que precisam desses caminhos importam daqui — nunca recalculam
# via __file__ próprio, evitando divergência quando a profundidade muda.
DATA_DIR = BASE_DIR / 'data'
AVATAR_DIR = DATA_DIR / 'avatars'
SEED_IMAGES_DIR = DATA_DIR / 'fotos'
USUARIOS_DIR = DATA_DIR / 'usuarios'
HORARIOS_DIR = DATA_DIR / 'horarios'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        case_sensitive=True,
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # ── Aplicação ──────────────────────────────────────────────────── #
    APP_NAME: str = 'EduPBL'
    DEBUG: bool = False
    ENVIRONMENT: str = 'development'  # 'development' | 'production'
    API_URL: str = 'http://localhost:8000/'
    FRONTEND_URL: str = 'http://localhost:5173'

    # ── E-mail ────────────────────────────────────────────────────── #
    SMTP_HOST: str = 'smtp.gmail.com'
    SMTP_PORT: int = 587
    SMTP_USER: str = 'your_app_gmail@gmail.com'
    SMTP_PASSWORD: str = 'your_google_app_passoword'
    SMTP_FROM: str = 'your_app_gmail@gmail.com'
    SMTP_ENABLED: bool = False

    # ── WhatsApp ──────────────────────────────────────────────────── #
    WHATSAPP_ENABLED: bool = False
    WHATSAPP_DB_PATH: str = './data/whatsapp_session.db'
    WHATSAPP_DEVICE_NAME: str = 'edupbl_bot'

    # ── Cookies ────────────────────────────────────────────────────── #
    # Computed fields derivados de ENVIRONMENT.
    # TODO: remover os valores fixos e restaurar a lógica comentada
    #       ao separar os ambientes de dev e produção.

    @computed_field
    @property
    def COOKIE_SAME_SITE(self) -> str:
        # Produção exige 'none' para cookies cross-origin (frontend ≠ backend).
        # Desenvolvimento usa 'lax' para funcionar em HTTP sem HTTPS.
        return 'none' if self.ENVIRONMENT == 'production' else 'lax'

    @computed_field
    @property
    def COOKIE_SECURE(self) -> bool:
        # SameSite='none' exige Secure=True (apenas em produção com HTTPS).
        # Em desenvolvimento com HTTP, Secure=False para o browser aceitar o cookie.
        return self.ENVIRONMENT == 'production'

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

    DATABASE_URL: str | None = None

    @computed_field
    @property
    def RESOLVED_DATABASE_URL(self) -> str:
        # 1. Prioriza DATABASE_URL do .env
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # 2. Monta dinamicamente com valores já carregados do .env
        return (
            f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}'
            f'@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
        )


settings = Settings()

# print(f'!!! {settings.RESOLVED_DATABASE_URL}')
