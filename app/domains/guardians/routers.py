"""
Rotas do domínio de guardiões (pais/responsáveis).

Todos os endpoints são read-only. Guardiões visualizam dados dos filhos;
qualquer operação de escrita permanece nos domínios originais.

Regras de autorização:
  GET /guardians/me/children                          → DELAYS_VIEW_CHILD
  GET /guardians/me/children/{student_id}/delays      → DELAYS_VIEW_CHILD
  GET /guardians/me/children/{student_id}/occurrences → OCCURRENCES_VIEW_CHILD
"""

from datetime import date
from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.delays.models import Delay
from app.domains.delays.schemas import DelayList, DelayPublic
from app.domains.guardians.schemas import ChildBasic, ChildrenListResponse
from app.domains.occurrences.models import Occurrence
from app.domains.occurrences.schemas import OccurrenceList, OccurrencePublic
from app.domains.users.models import User, guardian_student
from app.shared.db.database import get_session
from app.shared.rbac.dependencies import AnyPermissionChecker
from app.shared.rbac.permissions import SystemPermissions
from app.shared.security import get_current_user

router = APIRouter(prefix='/guardians', tags=['guardians'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def _assert_is_child(
    guardian: User, student_id: int, session: AsyncSession
) -> User:
    """
    Verifica que student_id é filho do guardian logado.
    Retorna o aluno ou lança 403 (não 404) para não vazar existência de IDs.
    """
    student = await session.scalar(
        select(User)
        .join(
            guardian_student,
            (guardian_student.c.student_id == User.id)
            & (guardian_student.c.guardian_id == guardian.id),
        )
        .where(User.id == student_id)
    )
    if student is None:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Aluno não vinculado a este responsável',
        )
    return student


# --------------------------------------------------------------------------- #
# GET /guardians/me/children                                                  #
# --------------------------------------------------------------------------- #


@router.get(
    '/me/children',
    response_model=ChildrenListResponse,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.DELAYS_VIEW_CHILD,
                SystemPermissions.OCCURRENCES_VIEW_CHILD,
            })
        )
    ],
)
async def list_my_children(
    session: Session,
    current_user: CurrentUser,
) -> ChildrenListResponse:
    """
    Retorna a lista de filhos vinculados ao responsável logado.

    Acessível por guardiões (DELAYS_VIEW_CHILD | OCCURRENCES_VIEW_CHILD).
    Lista vazia é retornada sem erro quando não há filhos cadastrados.
    """
    rows = await session.scalars(
        select(User)
        .join(
            guardian_student,
            (guardian_student.c.student_id == User.id)
            & (guardian_student.c.guardian_id == current_user.id),
        )
        .order_by(User.first_name, User.last_name)
    )
    children = [ChildBasic.model_validate(u) for u in rows.all()]
    return ChildrenListResponse(children=children)


# --------------------------------------------------------------------------- #
# GET /guardians/me/children/{student_id}/delays                              #
# --------------------------------------------------------------------------- #


@router.get(
    '/me/children/{student_id}/delays',
    response_model=DelayList,
    dependencies=[
        Depends(AnyPermissionChecker({SystemPermissions.DELAYS_VIEW_CHILD}))
    ],
)
async def list_child_delays(
    session: Session,
    current_user: CurrentUser,
    student_id: int = Path(alias='student_id'),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> DelayList:
    """
    Retorna os atrasos paginados de um filho do responsável logado.

    Query params opcionais:
      start_date  — filtra por delay_date >= start_date
      end_date    — filtra por delay_date <= end_date
      status      — filtra por status exato (pending | approved | rejected)
      skip / limit — paginação (padrão: 0 / 50)
    """
    await _assert_is_child(current_user, student_id, session)

    stmt = select(Delay).where(Delay.student_id == student_id)

    if start_date:
        stmt = stmt.where(Delay.delay_date >= start_date)
    if end_date:
        stmt = stmt.where(Delay.delay_date <= end_date)
    if status:
        stmt = stmt.where(Delay.status == status)

    stmt = stmt.order_by(Delay.delay_date.desc()).offset(skip).limit(limit)

    rows = await session.scalars(stmt)
    delays = [DelayPublic.model_validate(d) for d in rows.all()]
    return DelayList(delays=delays)


# --------------------------------------------------------------------------- #
# GET /guardians/me/children/{student_id}/occurrences                         #
# --------------------------------------------------------------------------- #


@router.get(
    '/me/children/{student_id}/occurrences',
    response_model=OccurrenceList,
    dependencies=[
        Depends(
            AnyPermissionChecker({SystemPermissions.OCCURRENCES_VIEW_CHILD})
        )
    ],
)
async def list_child_occurrences(
    session: Session,
    current_user: CurrentUser,
    student_id: int = Path(alias='student_id'),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> OccurrenceList:
    """
    Retorna as ocorrências paginadas de um filho do responsável logado.

    Query params opcionais:
      start_date / end_date — filtra por occurred_at (data, sem hora)
      skip / limit          — paginação (padrão: 0 / 50)
    """
    await _assert_is_child(current_user, student_id, session)

    stmt = select(Occurrence).where(Occurrence.student_id == student_id)

    if start_date:
        stmt = stmt.where(Occurrence.occurred_at >= start_date)
    if end_date:
        from datetime import timedelta

        next_day = date(
            end_date.year, end_date.month, end_date.day
        ) + timedelta(days=1)
        stmt = stmt.where(Occurrence.occurred_at < next_day)

    stmt = (
        stmt
        .order_by(Occurrence.occurred_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
    )

    rows = await session.scalars(stmt)
    occurrences = [OccurrencePublic.model_validate(o) for o in rows.all()]
    return OccurrenceList(occurrences=occurrences)
