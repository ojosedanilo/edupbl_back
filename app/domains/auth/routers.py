from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from jwt import DecodeError, ExpiredSignatureError, decode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.domains.auth.schemas import Token
from app.domains.users.models import User
from app.domains.users.schemas import UserPublic
from app.shared.database import get_session
from app.shared.rbac.dependencies import role_required
from app.shared.rbac.roles import UserRole
from app.shared.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_password,
)

ESCOPO_ACCESS_TOKEN = '/auth/token'
ESCOPO_REFRESH_TOKEN = '/auth/refresh_token'

router = APIRouter(prefix='/auth', tags=['auth'])

OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post('/token', response_model=Token)
async def login_for_access_token(
    form_data: OAuth2Form, session: Session, response: Response
):
    user = await session.scalar(
        select(User).where(User.email == form_data.username)
    )

    if not user:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Incorrect email or password',
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Incorrect email or password',
        )

    access_token = create_access_token(data={'sub': user.email})
    refresh_token = create_refresh_token(data={'sub': user.email})

    # Armazena o access token no cookie
    response.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == 'production',
        samesite='strict',
        path=ESCOPO_ACCESS_TOKEN,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {'access_token': access_token, 'token_type': 'bearer'}


@router.post('/logout')
async def logout(response: Response):
    # Remove o cookie de refresh token
    response.delete_cookie('refresh_token')
    return {'message': 'Logout successful'}


@router.post('/refresh_token', response_model=Token)
async def refresh_access_token(
    request: Request, response: Response, session: Session
):
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token:
        raise credentials_exception

    try:
        payload = decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        subject_email = payload.get('sub')
        if not subject_email:
            raise credentials_exception

    except DecodeError:
        raise credentials_exception

    except ExpiredSignatureError:
        raise credentials_exception

    user = await session.scalar(
        select(User).where(User.email == subject_email)
    )
    if not user:
        raise credentials_exception

    new_access_token = create_access_token(data={'sub': user.email})
    new_refresh_token = create_refresh_token(data={'sub': user.email})

    # Atualiza o cookie do refresh token com o novo token e a nova expiração
    response.set_cookie(
        'refresh_token',
        new_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == 'production',
        samesite='strict',
        path=ESCOPO_REFRESH_TOKEN,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {'access_token': new_access_token, 'token_type': 'bearer'}


@router.get('/me', response_model=UserPublic)
async def get_me(current_user: CurrentUser):
    return current_user


@router.get('/admin', response_model=UserPublic)
async def get_admin(
    coordinator: UserPublic = Depends(
        role_required([UserRole.COORDINATOR, UserRole.ADMIN])
    ),
):
    return coordinator
