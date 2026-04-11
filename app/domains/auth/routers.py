"""
Rotas de autenticação:
  POST /auth/token
  POST /auth/logout
  POST /auth/refresh_token
  GET  /auth/me
  GET  /auth/me/permissions
  GET  /auth/admin

Estratégia de tokens:
  - access_token  → JWT de curta duração, enviado no header Authorization
  - refresh_token → JWT de longa duração, armazenado em cookie HttpOnly
                    com path restrito a /auth/refresh_token para minimizar
                    a superfície de exposição
"""

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
from app.domains.users.schemas import (
    UserPublic,
    UserWithPermissions,
)
from app.shared.db.database import get_session
from app.shared.password_validator import validate_password
from app.shared.rbac.dependencies import role_required
from app.shared.rbac.helpers import get_user_permissions
from app.shared.rbac.roles import UserRole
from app.shared.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)

# Path do cookie de refresh — deve bater exatamente em set/delete.
# Lido das settings para variar entre dev (proxy Vite reescreve o path)
# e produção (backend servido diretamente em /auth/refresh_token).
REFRESH_COOKIE_PATH = settings.REFRESH_COOKIE_PATH

router = APIRouter(prefix='/auth', tags=['auth'])

# Aliases de dependency para reduzir repetição nas assinaturas
OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _set_refresh_cookie(response: Response, token: str) -> None:
    """
    Grava o refresh_token como cookie HttpOnly restrito a REFRESH_COOKIE_PATH.

    O path restrito garante que o browser só envie o cookie nas chamadas
    a /auth/refresh_token, reduzindo a exposição em outras rotas.
    """
    response.set_cookie(
        'refresh_token',
        token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,
        path=REFRESH_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )


def _build_token_response(user: User, response: Response) -> dict:
    """
    Cria access + refresh tokens, grava o refresh no cookie e retorna
    o dicionário que será serializado como Token pelo endpoint.
    """
    access_token = create_access_token(data={'sub': user.email})
    refresh_token = create_refresh_token(data={'sub': user.email})
    _set_refresh_cookie(response, refresh_token)

    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'must_change_password': user.must_change_password,
    }


# --------------------------------------------------------------------------- #
# POST /auth/change-password — Trocar senha                                  #
# --------------------------------------------------------------------------- #


@router.post('/change-password')
async def change_password(
    old_password: str,
    new_password: str,
    db: Session,
    current_user: CurrentUser,
):
    # Verificar senha antiga
    if not verify_password(old_password, current_user.password):
        raise HTTPException(401, 'Senha atual incorreta')

    # Validar nova senha
    password_result = validate_password(
        new_password,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        current_password_hash=current_user.password,
    )

    if not password_result.valid:
        raise HTTPException(
            status_code=400,
            detail={
                'valid': False,
                'errors': [e.value for e in password_result.erros],
                'suggestions': [s.value for s in password_result.suggestions],
            },
        )

    # Atualizar senha
    current_user.password = get_password_hash(new_password)
    current_user.must_change_password = False
    await db.commit()

    return {'message': 'Senha alterada com sucesso'}


# --------------------------------------------------------------------------- #
# POST /auth/token — Login                                                    #
# --------------------------------------------------------------------------- #


@router.post('/token', response_model=Token)
async def login_for_access_token(
    form_data: OAuth2Form, session: Session, response: Response
):
    """
    Autentica o usuário com e-mail e senha.

    Retorna o access_token no corpo e define o refresh_token como cookie.
    Intencionalmente usa a mesma mensagem de erro para e-mail e senha inválidos,
    evitando enumerar usuários cadastrados.
    """
    user = await session.scalar(
        select(User).where(User.email == form_data.username)
    )

    # Mensagem genérica para não vazar se o e-mail existe ou não
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Incorrect email or password',
        )

    if not user.is_active:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Inactive user',
        )

    return _build_token_response(user, response)


# --------------------------------------------------------------------------- #
# POST /auth/logout — Logout                                                  #
# --------------------------------------------------------------------------- #


@router.post('/logout')
async def logout(response: Response):
    """
    Remove o cookie de refresh_token do browser.

    O path e os atributos de segurança precisam ser idênticos aos usados
    na criação — do contrário, o browser não remove o cookie.
    """
    response.delete_cookie(
        'refresh_token',
        path=REFRESH_COOKIE_PATH,
        samesite=settings.COOKIE_SAME_SITE,
        secure=settings.COOKIE_SECURE,
        httponly=True,
    )
    return {'message': 'Logout successful'}


# --------------------------------------------------------------------------- #
# POST /auth/refresh_token — Renovação de tokens                             #
# --------------------------------------------------------------------------- #


@router.post('/refresh_token', response_model=Token)
async def refresh_access_token(
    request: Request, response: Response, session: Session
):
    """
    Renova o access_token usando o refresh_token do cookie HttpOnly.

    Emite um novo par de tokens (rotation), o que invalida implicitamente
    o refresh_token anterior (o novo substitui o cookie).
    """
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
        subject_email: str | None = payload.get('sub')
        if not subject_email:
            raise credentials_exception

    except (DecodeError, ExpiredSignatureError):
        raise credentials_exception

    user = await session.scalar(
        select(User).where(User.email == subject_email)
    )
    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Inactive user',
        )

    return _build_token_response(user, response)


# --------------------------------------------------------------------------- #
# GET /auth/me — Perfil do usuário logado                                     #
# --------------------------------------------------------------------------- #


@router.get('/me', response_model=UserPublic)
async def get_me(current_user: CurrentUser):
    """Retorna os dados públicos do usuário autenticado."""
    return current_user


# --------------------------------------------------------------------------- #
# GET /auth/me/permissions — Permissões do usuário logado                     #
# --------------------------------------------------------------------------- #


@router.get('/me/permissions', response_model=UserWithPermissions)
async def get_me_permissions(current_user: CurrentUser):
    """Retorna os dados públicos + conjunto de permissões do usuário autenticado."""
    permissions = get_user_permissions(current_user)
    base = UserPublic.model_validate(current_user)
    return UserWithPermissions(**base.model_dump(), permissions=permissions)


# --------------------------------------------------------------------------- #
# GET /auth/admin — Rota de teste de role                                     #
# --------------------------------------------------------------------------- #


@router.get('/admin', response_model=UserPublic)
async def get_admin(
    coordinator: UserPublic = Depends(
        role_required([UserRole.COORDINATOR, UserRole.ADMIN])
    ),
):
    """Rota de exemplo para verificar acesso restrito a Coordenador/Admin."""
    return coordinator
