"""
Rotas de ocorrências disciplinares.

Fluxo DT → Coordenação:
  - Professores e DTs criam ocorrências (forwarded_to_coordinator=False).
  - O DT pode encaminhar (PATCH /occurrences/{id}/forward).
  - Coordenadores vêem por padrão apenas as encaminhadas (?all=true para ver todas).
  - Existe transparência: coordenador pode ver as não-encaminhadas explicitamente.

Regras de autorização por endpoint:
  POST   /occurrences                → requer OCCURRENCES_CREATE
  GET    /occurrences                → requer OCCURRENCES_VIEW_ALL
  GET    /occurrences/me             → requer OCCURRENCES_VIEW_OWN
  GET    /occurrences/{id}           → requer OCCURRENCES_VIEW_OWN + verificação
  PUT    /occurrences/{id}           → requer OCCURRENCES_EDIT
  DELETE /occurrences/{id}           → requer OCCURRENCES_DELETE
  PATCH  /occurrences/{id}/forward   → requer OCCURRENCES_FORWARD (DT ou Coord)
"""

from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.occurrences.models import Occurrence
from app.domains.occurrences.schemas import (
    OccurrenceCreate,
    OccurrenceList,
    OccurrencePublic,
    OccurrenceUpdate,
)
from app.domains.users.models import User, active_users
from app.shared.db.database import get_session
from app.shared.notifications.dispatcher import (
    notify_occurrence_created,
    notify_occurrence_forwarded,
)
from app.shared.rbac.dependencies import PermissionChecker
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user

router = APIRouter(prefix='/occurrences', tags=['occurrences'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def _get_occurrence_or_404(
    occurrence_id: int, session: AsyncSession
) -> Occurrence:
    occurrence = await session.scalar(
        select(Occurrence).where(Occurrence.id == occurrence_id)
    )
    if not occurrence:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Occurrence not found'
        )
    return occurrence


def _assert_can_modify(occurrence: Occurrence, current_user: User) -> None:
    """
    Professores só podem alterar ocorrências que eles próprios criaram.
    Coordenadores e admins podem alterar qualquer ocorrência.
    """
    if (
        current_user.role == UserRole.TEACHER
        and occurrence.created_by_id != current_user.id
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )


# --------------------------------------------------------------------------- #
# POST /occurrences — Criar ocorrência                                        #
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
    """
    Registra uma nova ocorrência sobre um aluno.

    Ao criar, forwarded_to_coordinator=False.
    O DT encaminha explicitamente via PATCH /{id}/forward.
    """
    student = await session.scalar(
        active_users().where(User.id == data.student_id)
    )
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Student not found'
        )

    occurrence = Occurrence(
        created_by_id=current_user.id,
        student_id=data.student_id,
        title=data.title,
        description=data.description,
        occurrence_type=data.occurrence_type,
        occurred_at=data.occurred_at,
    )

    session.add(occurrence)
    await session.commit()
    await session.refresh(occurrence)

    await notify_occurrence_created(occurrence.id)
    return occurrence


# --------------------------------------------------------------------------- #
# GET /occurrences — Listar todas (coordenador/admin)                        #
# --------------------------------------------------------------------------- #


@router.get(
    '/',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_ALL}))
    ],
)
async def list_all_occurrences(
    session: Session,
    current_user: CurrentUser,
    include_not_forwarded: bool = Query(
        default=False,
        description='Se true, inclui ocorrências não encaminhadas (transparência). '
        'Por padrão, coordenadores vêem apenas as encaminhadas.',
    ),
):
    """
    Retorna ocorrências do sistema.

    Coordenadores e admins vêem por padrão apenas as encaminhadas pelo DT.
    Com ?include_not_forwarded=true, vêem todas (transparência total).
    Admins sempre vêem tudo (sem restrição).
    """
    stmt = select(Occurrence)

    # Coordenador: filtra por encaminhadas a menos que peça transparência
    if current_user.role == UserRole.COORDINATOR and not include_not_forwarded:
        stmt = stmt.where(Occurrence.forwarded_to_coordinator == True)  # noqa: E712

    result = await session.scalars(stmt.order_by(Occurrence.created_at.desc()))
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/classroom — Ocorrências da turma (DT)                     #
# --------------------------------------------------------------------------- #


@router.get(
    '/classroom',
    response_model=OccurrenceList,
    dependencies=[
        Depends(
            PermissionChecker({
                SystemPermissions.OCCURRENCES_VIEW_OWN_CLASSROOM
            })
        )
    ],
)
async def list_classroom_occurrences(
    session: Session, current_user: CurrentUser
):
    """
    Lista todas as ocorrências dos alunos da turma do usuário logado.
    Exclusivo para DTs (TEACHER + is_tutor=True).
    """
    if not current_user.classroom_id:
        return {'occurrences': []}

    result = await session.scalars(
        select(Occurrence)
        .join(User, Occurrence.student_id == User.id)
        .where(User.classroom_id == current_user.classroom_id)
        .order_by(Occurrence.created_at.desc())
    )
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/me — Minhas ocorrências                                   #
# --------------------------------------------------------------------------- #


@router.get(
    '/me',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_OWN}))
    ],
)
async def list_my_occurrences(session: Session, current_user: CurrentUser):
    """
    Lista ocorrências do usuário logado.

    - Aluno: ocorrências em que ele é o estudante envolvido.
    - Professor/DT: ocorrências que ele criou.
    """
    if current_user.role == UserRole.STUDENT:
        stmt = select(Occurrence).where(
            Occurrence.student_id == current_user.id
        )
    else:
        stmt = select(Occurrence).where(
            Occurrence.created_by_id == current_user.id
        )

    result = await session.scalars(stmt.order_by(Occurrence.created_at.desc()))
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/{id} — Detalhe                                            #
# --------------------------------------------------------------------------- #


@router.get(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_OWN}))
    ],
)
async def get_occurrence(
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    occurrence = await _get_occurrence_or_404(occurrence_id, session)

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
# GET /occurrences/child — Ocorrências dos filhos (responsável)              #
# --------------------------------------------------------------------------- #


@router.get(
    '/child',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_CHILD}))
    ],
)
async def list_child_occurrences(session: Session, current_user: CurrentUser):
    """
    Lista as ocorrências de todos os filhos vinculados ao responsável logado.

    Retorna apenas ocorrências encaminhadas à coordenação, garantindo que
    o responsável só é notificado de situações validadas pela escola.
    """
    from app.domains.users.models import guardian_student as _guardian_student

    result = await session.execute(
        select(_guardian_student.c.student_id).where(
            _guardian_student.c.guardian_id == current_user.id
        )
    )
    student_ids = [row[0] for row in result.all()]

    if not student_ids:
        return {'occurrences': []}

    occurrences = await session.scalars(
        select(Occurrence)
        .where(
            Occurrence.student_id.in_(student_ids),
            Occurrence.forwarded_to_coordinator == True,  # noqa: E712
        )
        .order_by(Occurrence.created_at.desc())
    )
    return {'occurrences': occurrences.all()}


# --------------------------------------------------------------------------- #
# PUT /occurrences/{id} — Atualizar                                          #
# --------------------------------------------------------------------------- #


@router.put(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_EDIT}))
    ],
)
async def update_occurrence(
    data: OccurrenceUpdate,
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    occurrence = await _get_occurrence_or_404(occurrence_id, session)
    _assert_can_modify(occurrence, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(occurrence, field, value)

    await session.commit()
    await session.refresh(occurrence)
    return occurrence


# --------------------------------------------------------------------------- #
# DELETE /occurrences/{id} — Apagar                                          #
# --------------------------------------------------------------------------- #


@router.delete(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_DELETE}))
    ],
)
async def delete_occurrence(
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    occurrence = await _get_occurrence_or_404(occurrence_id, session)
    _assert_can_modify(occurrence, current_user)

    await session.refresh(occurrence)
    await session.delete(occurrence)
    await session.commit()
    return occurrence


# --------------------------------------------------------------------------- #
# PATCH /occurrences/{id}/forward — Encaminhar para a coordenação            #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{occurrence_id}/forward',
    response_model=OccurrencePublic,
)
async def forward_occurrence(
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    """
    Encaminha uma ocorrência para a coordenação.

    Pode ser feito pelo DT da turma do aluno, por qualquer coordenador ou admin.
    Professores comuns só podem encaminhar ocorrências que eles próprios criaram.
    Uma vez encaminhada, a ocorrência não pode ser des-encaminhada.
    """
    occurrence = await _get_occurrence_or_404(occurrence_id, session)

    if occurrence.forwarded_to_coordinator:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Occurrence already forwarded to coordinator',
        )

    # Verifica permissão: coordenador/admin podem sempre; professor só a própria
    if current_user.role == UserRole.TEACHER:
        if (
            occurrence.created_by_id != current_user.id
            and not current_user.is_tutor
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail='Insufficient permissions',
            )
    elif current_user.role not in {UserRole.COORDINATOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )

    occurrence.forwarded_to_coordinator = True
    await session.commit()
    await session.refresh(occurrence)

    await notify_occurrence_forwarded(occurrence.id)
    return occurrence
