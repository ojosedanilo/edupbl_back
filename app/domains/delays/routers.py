"""
Rotas de atrasos de alunos.

Restrição de horário para porteiro:
  Porteiro só pode REGISTRAR e APROVAR atrasos durante os intervalos
  (SNACK_BREAK e LUNCH_BREAK) + tolerância de PORTER_DELAY_WINDOW_MINUTES.
  Coordenador pode registrar e aprovar a qualquer momento.
  A restrição de janela de datas (3 dias) se aplica a ambos.

Regras de autorização por endpoint:
  POST   /delays              → requer DELAYS_CREATE (porteiro, coordenador)
  GET    /delays              → requer DELAYS_VIEW_ALL (porteiro/coordenador/admin)
  GET    /delays/pending      → requer DELAYS_REVIEW (coordenador/admin)
  GET    /delays/me           → requer DELAYS_VIEW_OWN (aluno)
  GET    /delays/{id}         → requer pelo menos uma permissão de visualização
  PATCH  /delays/{id}/approve → requer DELAYS_REVIEW (coordenador/admin) OU porteiro em intervalo
  PATCH  /delays/{id}/reject  → requer DELAYS_REVIEW (coordenador/admin)
  PATCH  /delays/{id}/undo    → requer DELAYS_REVIEW — desfaz dentro da janela
"""

from datetime import date, datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.delays.enums import DelayStatusEnum
from app.domains.delays.models import Delay
from app.domains.delays.periods import UNDO_WINDOW_MINUTES, get_expected_time
from app.domains.delays.schemas import (
    DelayCreate,
    DelayList,
    DelayPublic,
    DelayReject,
)
from app.domains.delays.window import is_within_porter_window
from app.domains.users.models import User, active_users, guardian_student
from app.shared.db.database import get_session
from app.shared.notifications.dispatcher import (
    notify_delay_approved,
    notify_delay_registered,
    notify_delay_rejected,
)
from app.shared.rbac.dependencies import (
    AnyPermissionChecker,
    PermissionChecker,
)
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user

router = APIRouter(prefix='/delays', tags=['delays'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def _get_delay_or_404(delay_id: int, session: AsyncSession) -> Delay:
    delay = await session.scalar(select(Delay).where(Delay.id == delay_id))
    if not delay:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Delay not found'
        )
    return delay


def _assert_porter_window(current_user: User) -> None:
    """
    Se o usuário for porteiro, verifica se está dentro da janela de intervalo.
    Coordenadores e admins passam direto.
    """
    if current_user.role == UserRole.PORTER and not is_within_porter_window():
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Porteiros só podem registrar/aprovar atrasos durante os intervalos.',
        )


# --------------------------------------------------------------------------- #
# GET /delays/pending                                                          #
# --------------------------------------------------------------------------- #


@router.get(
    '/pending',
    response_model=DelayList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_REVIEW}))
    ],
)
async def list_pending_delays(session: Session):
    result = await session.scalars(
        select(Delay)
        .where(Delay.status == DelayStatusEnum.PENDING)
        .order_by(Delay.created_at.asc())
    )
    return {'delays': result.all()}


# --------------------------------------------------------------------------- #
# GET /delays/me                                                               #
# --------------------------------------------------------------------------- #


@router.get(
    '/me',
    response_model=DelayList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_VIEW_OWN}))
    ],
)
async def list_my_delays(session: Session, current_user: CurrentUser):
    result = await session.scalars(
        select(Delay).where(Delay.student_id == current_user.id)
    )
    return {'delays': result.all()}


# --------------------------------------------------------------------------- #
# POST /delays — Registrar atraso                                             #
# --------------------------------------------------------------------------- #


@router.post(
    '/',
    status_code=HTTPStatus.CREATED,
    response_model=DelayPublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_CREATE}))
    ],
)
async def create_delay(
    data: DelayCreate,
    session: Session,
    current_user: CurrentUser,
):
    """
    Registra um novo atraso para um aluno.

    Porteiro: só pode registrar durante os intervalos.
    Coordenador: pode registrar a qualquer momento.
    """
    # Verificação de janela horária (porteiro)
    _assert_porter_window(current_user)

    student = await session.scalar(
        active_users().where(User.id == data.student_id)
    )
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Student not found'
        )

    if student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='User is not a student',
        )

    target_date = (
        data.delay_date if data.delay_date is not None else date.today()
    )
    min_date = date.today() - timedelta(days=3)
    if target_date < min_date or target_date > date.today():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='delay_date must be between 3 days ago and today',
        )

    existing = await session.scalar(
        select(Delay).where(
            Delay.student_id == data.student_id,
            Delay.delay_date == target_date,
        )
    )
    if existing:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Delay already registered for this student today',
        )

    expected = get_expected_time(data.arrival_time)

    arrival_dt = datetime.combine(target_date, data.arrival_time)
    expected_dt = datetime.combine(target_date, expected)
    delay_minutes = max(
        0, int((arrival_dt - expected_dt).total_seconds() // 60)
    )

    delay = Delay(
        student_id=data.student_id,
        recorded_by_id=current_user.id,
        delay_date=target_date,
        arrival_time=data.arrival_time,
        delay_minutes=delay_minutes,
        reason=data.reason,
    )
    delay.expected_time = expected

    session.add(delay)
    await session.commit()
    await session.refresh(delay)

    await notify_delay_registered(delay.id)
    return delay


# --------------------------------------------------------------------------- #
# GET /delays — Listar todos                                                  #
# --------------------------------------------------------------------------- #


@router.get(
    '/',
    response_model=DelayList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_VIEW_ALL}))
    ],
)
async def list_all_delays(
    session: Session,
    status: Optional[DelayStatusEnum] = Query(default=None),
    date_filter: Optional[date] = Query(default=None, alias='date'),
):
    stmt = select(Delay)

    if status:
        stmt = stmt.where(Delay.status == status)
    if date_filter:
        stmt = stmt.where(Delay.delay_date == date_filter)

    result = await session.scalars(stmt)
    return {'delays': result.all()}


# --------------------------------------------------------------------------- #
# GET /delays/{id}                                                            #
# --------------------------------------------------------------------------- #


@router.get(
    '/{delay_id}',
    response_model=DelayPublic,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.DELAYS_VIEW_ALL,
                SystemPermissions.DELAYS_VIEW_OWN,
                SystemPermissions.DELAYS_VIEW_CHILD,
                SystemPermissions.DELAYS_VIEW_OWN_CLASSROOM,
            })
        )
    ],
)
async def get_delay(
    session: Session,
    current_user: CurrentUser,
    delay_id: int = Path(alias='delay_id'),
):
    delay = await _get_delay_or_404(delay_id, session)

    if current_user.role in {UserRole.COORDINATOR, UserRole.ADMIN, UserRole.PORTER}:
        return delay

    if current_user.role == UserRole.STUDENT:
        if delay.student_id != current_user.id:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions')
        return delay

    if current_user.role == UserRole.GUARDIAN:
        link = await session.execute(
            select(guardian_student).where(
                guardian_student.c.guardian_id == current_user.id,
                guardian_student.c.student_id == delay.student_id,
            )
        )
        if not link.first():
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions')
        return delay

    if current_user.role == UserRole.TEACHER and current_user.is_tutor:
        student = await session.get(User, delay.student_id)
        if not student or student.classroom_id != current_user.classroom_id:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions')
        return delay

    raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions')


# --------------------------------------------------------------------------- #
# PATCH /delays/{id}/approve                                                  #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{delay_id}/approve',
    response_model=DelayPublic,
)
async def approve_delay(
    session: Session,
    current_user: CurrentUser,
    delay_id: int = Path(alias='delay_id'),
):
    """
    Aprova a entrada de um aluno atrasado.

    Porteiro: só pode aprovar durante os intervalos (mesma janela do registro).
    Coordenador/Admin: pode aprovar a qualquer momento.
    """
    # Porteiro precisa de DELAYS_CREATE; coordenador de DELAYS_REVIEW
    from app.shared.rbac.helpers import user_has_any_permission

    if current_user.role == UserRole.PORTER:
        if not user_has_any_permission(current_user, {SystemPermissions.DELAYS_CREATE}):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions')
        _assert_porter_window(current_user)
    elif not user_has_any_permission(current_user, {SystemPermissions.DELAYS_REVIEW}):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions')

    delay = await _get_delay_or_404(delay_id, session)

    if delay.status != DelayStatusEnum.PENDING:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail='Delay already decided')

    delay.status = DelayStatusEnum.APPROVED
    delay.approved_by_id = current_user.id

    await session.commit()
    await session.refresh(delay)

    await notify_delay_approved(delay.id)
    return delay


# --------------------------------------------------------------------------- #
# PATCH /delays/{id}/reject                                                   #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{delay_id}/reject',
    response_model=DelayPublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_REVIEW}))
    ],
)
async def reject_delay(
    data: DelayReject,
    session: Session,
    current_user: CurrentUser,
    delay_id: int = Path(alias='delay_id'),
):
    delay = await _get_delay_or_404(delay_id, session)

    if delay.status != DelayStatusEnum.PENDING:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail='Delay already decided')

    delay.status = DelayStatusEnum.REJECTED
    delay.approved_by_id = current_user.id
    delay.rejection_reason = data.rejection_reason

    await session.commit()
    await session.refresh(delay)

    await notify_delay_rejected(delay.id)
    return delay


# --------------------------------------------------------------------------- #
# PATCH /delays/{id}/undo                                                     #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{delay_id}/undo',
    response_model=DelayPublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_REVIEW}))
    ],
)
async def undo_delay_decision(
    session: Session,
    delay_id: int = Path(alias='delay_id'),
):
    delay = await _get_delay_or_404(delay_id, session)

    if delay.status == DelayStatusEnum.PENDING:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail='Delay has not been decided yet')

    window_limit = datetime.utcnow() - timedelta(minutes=UNDO_WINDOW_MINUTES)
    if delay.updated_at < window_limit:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f'Undo window of {UNDO_WINDOW_MINUTES} minutes has expired',
        )

    delay.status = DelayStatusEnum.PENDING
    delay.approved_by_id = None
    delay.rejection_reason = None

    await session.commit()
    await session.refresh(delay)
    return delay
