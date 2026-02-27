from http import HTTPStatus

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.domains.auth import routers as auth_routers
from app.domains.users import routers as users_routers
from app.domains.users.schemas import Message

app = FastAPI(title='EduPBL')

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


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    return {'message': 'Olá Mundo!'}
