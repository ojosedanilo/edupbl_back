from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.occurrences.models import Occurrence
from app.domains.occurrences.schemas import (
    OccurrenceCreate,
    OccurrenceList,
    OccurrencePublic,
    OccurrenceUpdate,
)
from app.domains.users.models import User
from app.shared.db.database import get_session
from app.shared.rbac.dependencies import PermissionChecker
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user

router = APIRouter(prefix='/occurrences', tags=['occurrences'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# --------------------------------------------------------------------------- #
# POST /occurrences                                                           #
# --------------------------------------------------------------------------- #
@router.post(
    '/',
    status_code=HTTPStatus.CREATED,
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_CREATE}))
    ],
)
async def create_occurrence(
    data: OccurrenceCreate,
    session: Session,
    current_user: CurrentUser,
):
    """Cria uma nova ocorrência. `created_by_id` é sempre o usuário logado."""
    student = await session.get(User, data.student_id)
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Student not found'
        )

    occurrence = Occurrence(
        created_by_id=current_user.id,
        student_id=data.student_id,
        title=data.title,
        description=data.description,
    )

    session.add(occurrence)
    await session.commit()
    await session.refresh(occurrence)
    return occurrence


# --------------------------------------------------------------------------- #
# GET /occurrences   (todas — coordenador / admin)                            #
# --------------------------------------------------------------------------- #
@router.get(
    '/',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_ALL}))
    ],
)
async def list_all_occurrences(session: Session):
    result = await session.scalars(select(Occurrence))
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/me   (aluno → sobre mim | professor → que criei)           #
# --------------------------------------------------------------------------- #
@router.get(
    '/me',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_OWN}))
    ],
)
async def list_my_occurrences(
    session: Session,
    current_user: CurrentUser,
):
    if current_user.role == UserRole.STUDENT:
        stmt = select(Occurrence).where(
            Occurrence.student_id == current_user.id
        )
    else:
        stmt = select(Occurrence).where(
            Occurrence.created_by_id == current_user.id
        )

    result = await session.scalars(stmt)
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/{id}                                                       #
# --------------------------------------------------------------------------- #
@router.get(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_OWN}))
    ],
)
async def get_occurrence(
    occurrence_id: int,
    session: Session,
    current_user: CurrentUser,
):
    occurrence = await session.scalar(
        select(Occurrence).where(Occurrence.id == occurrence_id)
    )
    if not occurrence:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Occurrence not found'
        )

    if (
        current_user.role == UserRole.STUDENT
        and occurrence.student_id != current_user.id
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )

    return occurrence


# --------------------------------------------------------------------------- #
# PUT /occurrences/{id}                                                       #
# --------------------------------------------------------------------------- #
@router.put(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_EDIT}))
    ],
)
async def update_occurrence(
    occurrence_id: int,
    data: OccurrenceUpdate,
    session: Session,
    current_user: CurrentUser,
):
    occurrence = await session.scalar(
        select(Occurrence).where(Occurrence.id == occurrence_id)
    )
    if not occurrence:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Occurrence not found'
        )

    if (
        current_user.role == UserRole.TEACHER
        and occurrence.created_by_id != current_user.id
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(occurrence, field, value)

    await session.commit()
    await session.refresh(occurrence)
    return occurrence


# --------------------------------------------------------------------------- #
# DELETE /occurrences/{id}                                                    #
# --------------------------------------------------------------------------- #
@router.delete(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_DELETE}))
    ],
)
async def delete_occurrence(
    occurrence_id: int,
    session: Session,
    current_user: CurrentUser,
):
    occurrence = await session.scalar(
        select(Occurrence).where(Occurrence.id == occurrence_id)
    )
    if not occurrence:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Occurrence not found'
        )

    if (
        current_user.role == UserRole.TEACHER
        and occurrence.created_by_id != current_user.id
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )

    # Garante que todos os atributos estão carregados antes da deleção
    await session.refresh(occurrence)

    await session.delete(occurrence)
    await session.commit()
    return occurrence
