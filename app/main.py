"""
Ponto de entrada da aplicação FastAPI.

Inicialização (lifespan):
  - Em development: popula o banco com usuários de teste via seed_test_users.
  - Em production: nenhuma ação automática no boot.

CORS:
  Configurado para aceitar credenciais (cookies) do frontend em desenvolvimento.
  Adicione as origens de produção aqui quando fizer o deploy.
"""

from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.domains.auth import routers as auth_routers
from app.domains.delays import routers as delays_routers
from app.domains.occurrences import routers as occurrences_routers
from app.domains.schedules import routers as schedules_routers
from app.domains.users import routers as users_routers
from app.shared.db.database import SessionLocal
from app.shared.db.seed import seed_test_users
from app.shared.schemas import Message


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executado na inicialização (antes do yield) e no encerramento (após).
    O bloco de seed só roda em development para não poluir produção.
    """
    if settings.ENVIRONMENT == 'development':
        async with SessionLocal() as session:
            try:
                await seed_test_users(session)
            except Exception as e:
                # Não interrompe o boot se o seed falhar (ex: banco vazio)
                print(f'[seed] Aviso: {e}')
    yield


app = FastAPI(title='EduPBL', lifespan=lifespan)

# CORS: permite o frontend de dev enviar cookies (withCredentials: true)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_routers.router)
app.include_router(users_routers.router)
app.include_router(occurrences_routers.router)
app.include_router(schedules_routers.router)
app.include_router(delays_routers.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    """Health check básico — confirma que a API está no ar."""
    return {'message': 'Olá Mundo!'}
