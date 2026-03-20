from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User
from app.domains.users.schemas import (
    FilterPage,
    Message,
    PasswordChange,
    UserList,
    UserPublic,
    UserSchema,
    UserUpdate,
)
from app.shared.database import get_session
from app.shared.security import (
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix='/users', tags=['users'])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserSchema, session: Session):
    db_user = await session.scalar(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )

    if db_user:
        if db_user.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username already exists',
            )
        elif db_user.email == user.email:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Email already exists',
            )

    hashed_password = get_password_hash(user.password)

    db_user = User(
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        password=hashed_password,
        role=user.role,
        is_tutor=user.is_tutor,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return db_user


@router.get('/', response_model=UserList)
async def read_users(
    session: Session, filter_users: Annotated[FilterPage, Query()]
):
    query = await session.scalars(
        select(User).offset(filter_users.offset).limit(filter_users.limit)
    )

    users = query.all()

    return {'users': users}


@router.put('/{user_id}', response_model=UserPublic)
async def update_user(
    user_id: int,
    user: UserUpdate,
    session: Session,
    current_user: CurrentUser,
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    # Validar conflitos de username/email antes de atualizar
    if user.username is not None or user.email is not None:
        conditions = []
        if user.username is not None:
            conditions.append(User.username == user.username)
        if user.email is not None:
            conditions.append(User.email == user.email)

        # Busca se existe outro usuário com username OU email que queremos usar
        db_user = await session.scalar(select(User).where(or_(*conditions)))

        # Se encontrou alguém E não é o próprio usuário atual
        if db_user and db_user.id != current_user.id:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username or Email already exists',
            )

    # Atualizar apenas campos que foram enviados
    update_data = user.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == 'password':
            # Hash da senha antes de salvar
            setattr(current_user, field, get_password_hash(value))
        else:
            setattr(current_user, field, value)

    await session.commit()
    await session.refresh(current_user)

    return current_user


@router.patch('/me/password', response_model=Message)
async def change_my_password(
    data: PasswordChange,
    session: Session,
    current_user: CurrentUser,
):
    """Troca a senha do usuário logado e limpa o flag must_change_password."""
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Current password is incorrect',
        )

    current_user.password = get_password_hash(data.new_password)
    current_user.must_change_password = False

    await session.commit()

    return {'message': 'Password updated successfully'}


@router.delete('/{user_id}', response_model=Message)
async def delete_user(
    user_id: int,
    session: Session,
    current_user: CurrentUser,
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    await session.delete(current_user)
    await session.commit()

    return {'message': 'User deleted'}
