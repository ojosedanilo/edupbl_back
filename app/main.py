from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.domains.auth import routers as auth_routers
from app.domains.occurrences import routers as occurrences_routers
from app.domains.users import routers as users_routers
from app.domains.users.schemas import Message
from app.shared.db.database import SessionLocal
from app.shared.db.seed import seed_test_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerenciador de Contexto para INICIALIZAÇÃO e ENCERRAMENTO da aplicação.
    O código ANTES de 'yield' é executado na INICIALIZAÇÃO.
    O código DEPOIS de 'yield' é executado no ENCERRAMENTO.
    """
    # Obtém a sessão e cria os usuários
    async with SessionLocal() as session:
        # Só cria usuários de teste se estiver em desenvolvimento
        if settings.ENVIRONMENT == 'development':
            try:
                await seed_test_users(session)
            except Exception as e:
                print(e)
    yield


app = FastAPI(title='EduPBL', lifespan=lifespan)

# Configuração de CORS:
# Permite que o front-end em dev envie cookies (credenciais)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_routers.router)
app.include_router(users_routers.router)
app.include_router(occurrences_routers.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    return {'message': 'Olá Mundo!'}
