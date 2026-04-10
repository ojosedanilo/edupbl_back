"""
Rotas de atrasos de alunos.

Regras de autorização por endpoint:
  POST   /delays              → requer DELAYS_CREATE (porteiro, coordenador)
  GET    /delays              → requer DELAYS_VIEW_ALL (porteiro/coordenador/admin)
  GET    /delays/pending      → requer DELAYS_REVIEW (coordenador/admin)
  GET    /delays/me           → requer DELAYS_VIEW_OWN (aluno)
  GET    /delays/{id}         → requer pelo menos uma permissão de visualização
  PATCH  /delays/{id}/approve → requer DELAYS_REVIEW (coordenador/admin)
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
    """Busca o atraso pelo id ou lança 404 se não existir."""
    delay = await session.scalar(select(Delay).where(Delay.id == delay_id))
    if not delay:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Delay not found'
        )
    return delay


# --------------------------------------------------------------------------- #
# GET /delays/pending — Listar pendentes (antes de /{id})                     #
# --------------------------------------------------------------------------- #


@router.get(
    '/pending',
    response_model=DelayList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_REVIEW}))
    ],
)
async def list_pending_delays(session: Session):
    """
    Retorna todos os atrasos com status PENDING, ordenados por data de criação.
    Atalho para a tela de aprovação da coordenação.
    """
    result = await session.scalars(
        select(Delay)
        .where(Delay.status == DelayStatusEnum.PENDING)
        .order_by(Delay.created_at.asc())
    )
    return {'delays': result.all()}


# --------------------------------------------------------------------------- #
# GET /delays/me — Meus atrasos (antes de /{id})                             #
# --------------------------------------------------------------------------- #


@router.get(
    '/me',
    response_model=DelayList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_VIEW_OWN}))
    ],
)
async def list_my_delays(session: Session, current_user: CurrentUser):
    """Retorna os atrasos do aluno logado."""
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

    O porteiro informa student_id, arrival_time e reason (opcional).
    expected_time é calculado automaticamente com base no período vigente
    no momento da chegada (derivado da configuração de schedules).
    """
    # Verifica se o aluno existe e está ativo
    student = await session.scalar(
        active_users().where(User.id == data.student_id)
    )
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Student not found'
        )

    # Apenas usuários com role STUDENT podem ter atrasos registrados
    if student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='User is not a student',
        )

    # Data do atraso: usa a fornecida ou hoje como padrão; limita a 3 dias no passado
    target_date = (
        data.delay_date if data.delay_date is not None else date.today()
    )
    min_date = date.today() - timedelta(days=3)
    if target_date < min_date or target_date > date.today():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='delay_date must be between 3 days ago and today',
        )

    # Impede atraso duplicado no mesmo dia para o mesmo aluno
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

    # Determina o horário esperado com base no período vigente
    expected = get_expected_time(data.arrival_time)

    # Calcula o atraso em minutos
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
    # expected_time é init=False no model; precisa ser atribuído manualmente
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
    """
    Retorna todos os atrasos do sistema. Acesso restrito a porteiros,
    coordenadores e admins.

    Filtros opcionais:
      ?status=PENDING|APPROVED|REJECTED
      ?date=YYYY-MM-DD
    """
    stmt = select(Delay)

    if status:
        stmt = stmt.where(Delay.status == status)
    if date_filter:
        stmt = stmt.where(Delay.delay_date == date_filter)

    result = await session.scalars(stmt)
    return {'delays': result.all()}


# --------------------------------------------------------------------------- #
# GET /delays/{id} — Detalhe de um atraso                                    #
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
    """
    Retorna o detalhe de um atraso específico.

    Após a verificação de permissão, aplica regra de ownership conforme o role:
      - Coordenador / Admin / Porteiro : acesso irrestrito (têm DELAYS_VIEW_ALL)
      - Aluno                          : só o próprio atraso
      - Responsável                    : só atrasos dos seus filhos
      - Professor DT                   : só atrasos da própria turma
    """
    delay = await _get_delay_or_404(delay_id, session)

    # Coordenador, Admin e Porteiro têm DELAYS_VIEW_ALL — sem restrição adicional
    if current_user.role in {
        UserRole.COORDINATOR,
        UserRole.ADMIN,
        UserRole.PORTER,
    }:
        return delay

    # Aluno só pode ver o próprio atraso
    if current_user.role == UserRole.STUDENT:
        if delay.student_id != current_user.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail='Insufficient permissions',
            )
        return delay

    # Responsável só vê atraso de filho registrado em sua tutela
    if current_user.role == UserRole.GUARDIAN:
        link = await session.execute(
            select(guardian_student).where(
                guardian_student.c.guardian_id == current_user.id,
                guardian_student.c.student_id == delay.student_id,
            )
        )
        if not link.first():
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail='Insufficient permissions',
            )
        return delay

    # Professor DT só vê atrasos da própria turma
    if current_user.role == UserRole.TEACHER and current_user.is_tutor:
        student = await session.get(User, delay.student_id)
        if not student or student.classroom_id != current_user.classroom_id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail='Insufficient permissions',
            )
        return delay
    raise HTTPException(
        status_code=HTTPStatus.FORBIDDEN,
        detail='Insufficient permissions',
    )


# --------------------------------------------------------------------------- #
# PATCH /delays/{id}/approve — Aprovar entrada                               #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{delay_id}/approve',
    response_model=DelayPublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.DELAYS_REVIEW}))
    ],
)
async def approve_delay(
    session: Session,
    current_user: CurrentUser,
    delay_id: int = Path(alias='delay_id'),
):
    """
    Aprova a entrada de um aluno atrasado.
    Só é possível aprovar atrasos com status PENDING — status é final.
    Use /undo dentro de 5 minutos para reverter uma decisão equivocada.
    """
    delay = await _get_delay_or_404(delay_id, session)

    # Status é final após a primeira decisão
    if delay.status != DelayStatusEnum.PENDING:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Delay already decided',
        )

    delay.status = DelayStatusEnum.APPROVED
    delay.approved_by_id = current_user.id

    await session.commit()
    await session.refresh(delay)

    await notify_delay_approved(delay.id)
    return delay


# --------------------------------------------------------------------------- #
# PATCH /delays/{id}/reject — Rejeitar entrada                               #
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
    """
    Rejeita a entrada de um aluno atrasado.
    Só é possível rejeitar atrasos com status PENDING — status é final.
    Use /undo dentro de 5 minutos para reverter uma decisão equivocada.
    """
    delay = await _get_delay_or_404(delay_id, session)

    # Status é final após a primeira decisão
    if delay.status != DelayStatusEnum.PENDING:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Delay already decided',
        )

    delay.status = DelayStatusEnum.REJECTED
    delay.approved_by_id = current_user.id
    delay.rejection_reason = data.rejection_reason

    await session.commit()
    await session.refresh(delay)

    await notify_delay_rejected(delay.id)
    return delay


# --------------------------------------------------------------------------- #
# PATCH /delays/{id}/undo — Desfazer decisão                                 #
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
    """
    Desfaz uma decisão de aprovação ou rejeição, revertendo o atraso para PENDING.

    Só é possível desfazer dentro da janela configurada (UNDO_WINDOW_MINUTES).
    Após esse prazo, o status é considerado permanente.
    Requer a mesma permissão DELAYS_REVIEW do approve/reject.
    """
    delay = await _get_delay_or_404(delay_id, session)

    # Só faz sentido desfazer algo que já foi decidido
    if delay.status == DelayStatusEnum.PENDING:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Delay has not been decided yet',
        )

    # Verifica a janela de tempo usando updated_at como proxy do momento da decisão
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
