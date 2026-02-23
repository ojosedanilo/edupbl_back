from http import HTTPStatus

from fastapi import FastAPI

from app.domains.auth import routers as auth_routers
from app.domains.users import routers as users_routers
from app.domains.users.schemas import Message

app = FastAPI(title='EduPBL')

app.include_router(auth_routers.router)
app.include_router(users_routers.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    return {'message': 'Olá Mundo!'}
