"""
Ponto de entrada da aplicação FastAPI.

Inicialização (lifespan):
  - Em development: popula o banco com usuários de teste via seed_test_users.
  - Em production: nenhuma ação automática no boot.

CORS:
  Configurado para aceitar credenciais (cookies) do frontend em desenvolvimento.
  Adicione as origens de produção aqui quando fizer o deploy.

Documentação (Swagger / ReDoc):
  Desabilitada em produção — endpoints /docs e /redoc não são expostos.
  Em desenvolvimento, ficam ativos normalmente.
"""

from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.settings import settings
from app.domains.auth import routers as auth_routers
from app.domains.delays import routers as delays_routers
from app.domains.occurrences import routers as occurrences_routers
from app.domains.schedules import routers as schedules_routers
from app.domains.users import routers as users_routers
from app.shared.db.database import SessionLocal, get_session
from app.shared.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executado na inicialização (antes do yield) e no encerramento (após).
    O seed de dados NÃO roda automaticamente no boot — use o script
    ``scripts/seed_db.py`` para popular o banco manualmente.
    """
    yield


# Docs desabilitadas em produção: Swagger e ReDoc expõem detalhes internos
# da API (schemas, endpoints, exemplos) que não devem ser públicos em produção.
_docs_url = '/docs' if settings.ENVIRONMENT != 'production' else None
_redoc_url = '/redoc' if settings.ENVIRONMENT != 'production' else None

# redirect_slashes=False: desativa o comportamento padrão do FastAPI de emitir
# 307 quando a URL chega sem barra final. Com o proxy do Vite em dev, esse 307
# gerava um Location absoluto apontando para localhost:8000 — o browser saía
# do proxy, perdia o Authorization header e recebia 401 em loop.
app = FastAPI(
    title='EduPBL',
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# CORS: permite o frontend de dev enviar cookies (withCredentials: true)
# Tanto 'localhost' quanto '127.0.0.1' são aceitos para evitar erros de cross-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        settings.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_routers.router)
app.include_router(users_routers.router)
app.include_router(occurrences_routers.router)
app.include_router(schedules_routers.router)
app.include_router(delays_routers.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=HealthResponse)
async def read_root():
    """Health check — retorna status da API, ambiente e conectividade com o banco."""
    db_status = 'offline'
    db_url_display = settings.RESOLVED_DATABASE_URL

    # Tenta uma query mínima para confirmar conectividade com o banco
    try:
        async for session in get_session():
            await session.execute(text('SELECT 1'))
        db_status = 'online'
    except Exception:
        pass

    # Oculta credenciais da URL em produção
    if settings.ENVIRONMENT == 'production':
        try:
            from urllib.parse import urlparse

            parsed = urlparse(db_url_display)
            db_url_display = parsed._replace(
                netloc=f'***:***@{parsed.hostname}:{parsed.port}'
            ).geturl()
        except Exception:
            db_url_display = '(oculto em produção)'

    return HealthResponse(
        message='Olá Mundo!',
        environment=settings.ENVIRONMENT,
        database_status=db_status,
        database_url=db_url_display,
    )
