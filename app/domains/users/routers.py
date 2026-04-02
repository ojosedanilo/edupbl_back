"""
Rotas de usuários:
  POST /users
  GET /users
  PUT /users/{user_id}
  PATCH /users/me/password
  DELETE /users/{user_id}

Regras de autorização:
  - Criar usuário: aberto (sem autenticação)
  - Listar usuários: autenticado
  - Atualizar / Deletar: apenas o próprio usuário
  - Trocar senha: próprio usuário, com confirmação da senha atual
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User
from app.domains.users.schemas import (
    FilterPage,
    PasswordChange,
    UserList,
    UserPublic,
    UserSchema,
    UserUpdate,
)
from app.shared.db.database import get_session
from app.shared.schemas import Message
from app.shared.security import (
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix='/users', tags=['users'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# --------------------------------------------------------------------------- #
# POST /users — Criar usuário                                                 #
# --------------------------------------------------------------------------- #


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserSchema, session: Session):
    """
    Cria um novo usuário.

    Verifica conflito de username e e-mail antes de inserir.
    Retorna mensagens de erro distintas para cada campo em conflito.
    """
    existing = await session.scalar(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )

    if existing:
        if existing.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username already exists',
            )
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Email already exists',
        )

    db_user = User(
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        password=get_password_hash(user.password),
        role=user.role,
        is_tutor=user.is_tutor,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


# --------------------------------------------------------------------------- #
# GET /users — Listar usuários (com paginação)                                #
# --------------------------------------------------------------------------- #


@router.get('/', response_model=UserList)
async def read_users(
    session: Session,
    filter_users: Annotated[FilterPage, Query()],
):
    """Lista usuários com paginação via offset/limit."""
    result = await session.scalars(
        select(User).offset(filter_users.offset).limit(filter_users.limit)
    )
    return {'users': result.all()}


# --------------------------------------------------------------------------- #
# PUT /users/{user_id} — Atualizar usuário                                   #
# --------------------------------------------------------------------------- #


@router.put('/{user_id}', response_model=UserPublic)
async def update_user(
    user: UserUpdate,
    session: Session,
    current_user: CurrentUser,
    user_id: int = Path(alias='user_id'),
):
    """
    Atualiza os dados do usuário.

    Apenas o próprio usuário pode se atualizar (self-service).
    Verifica conflito de username/e-mail com outros usuários antes de salvar.
    Apenas campos enviados na requisição são alterados (patch semântico via PUT).
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    # Verifica conflito de username/e-mail com outros usuários
    if user.username is not None or user.email is not None:
        conditions = []
        if user.username is not None:
            conditions.append(User.username == user.username)
        if user.email is not None:
            conditions.append(User.email == user.email)

        conflicting = await session.scalar(
            select(User).where(or_(*conditions))
        )

        if conflicting and conflicting.id != current_user.id:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username or Email already exists',
            )

    # Aplica apenas os campos enviados (exclude_unset ignora omitidos)
    for field, value in user.model_dump(exclude_unset=True).items():
        if field == 'password':
            setattr(current_user, field, get_password_hash(value))
        else:
            setattr(current_user, field, value)

    await session.commit()
    await session.refresh(current_user)
    return current_user


# --------------------------------------------------------------------------- #
# PATCH /users/me/password — Trocar senha                                    #
# --------------------------------------------------------------------------- #


@router.patch('/me/password', response_model=Message)
async def change_my_password(
    data: PasswordChange,
    session: Session,
    current_user: CurrentUser,
):
    """
    Troca a senha do usuário logado e limpa o flag must_change_password.

    Exige a senha atual para confirmar a identidade antes de aceitar a nova.
    """
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Current password is incorrect',
        )

    current_user.password = get_password_hash(data.new_password)
    current_user.must_change_password = False

    await session.commit()
    return {'message': 'Password updated successfully'}


# --------------------------------------------------------------------------- #
# DELETE /users/{user_id} — Deletar usuário                                  #
# --------------------------------------------------------------------------- #


@router.delete('/{user_id}', response_model=Message)
async def delete_user(
    session: Session,
    current_user: CurrentUser,
    user_id: int = Path(alias='user_id'),
):
    """
    Deleta o usuário. Apenas o próprio usuário pode se deletar.

    Ocorrências criadas pelo usuário terão created_by_id → NULL (SET NULL).
    Ocorrências sobre o usuário (aluno) serão deletadas (CASCADE).
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    await session.delete(current_user)
    await session.commit()
    return {'message': 'User deleted'}
