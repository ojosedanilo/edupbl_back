"""
Rotas de horários/agendamentos.

Regras de autorização por endpoint:

  GET    /schedules/periods
         → qualquer logado

  GET    /schedules/classroom/{classroom_id}
         → SCHEDULES_VIEW_(OWN | CHILD | ALL)
         → validação secundária por contexto (turma)

  GET    /schedules/teacher/{user_id}
         → SCHEDULES_VIEW_(OWN | ALL)
         → professor só pode ver a própria grade

  GET    /schedules/current-teacher/{classroom_id}
         → SCHEDULES_VIEW_(OWN | CHILD | ALL)
         → validação secundária por contexto (turma)

  POST   /schedules/slots
  PUT    /schedules/slots/{slot_id}
  DELETE /schedules/slots/{slot_id}
         → SCHEDULES_MANAGE

  GET    /schedules/overrides
         → SCHEDULES_VIEW_(OWN | CHILD | ALL)

  POST   /schedules/overrides
  DELETE /schedules/overrides/{override_id}
         → SCHEDULES_MANAGE
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedules.helpers import get_current_teacher
from app.domains.schedules.models import (
    ScheduleOverride,
    ScheduleSlot,
    override_classrooms,
)
from app.domains.schedules.periods import PERIODS
from app.domains.schedules.schemas import (
    OverrideCreate,
    OverrideList,
    OverridePublic,
    PeriodsList,
    SlotCreate,
    SlotList,
    SlotPublic,
)
from app.domains.users.models import User, guardian_student
from app.domains.users.routers import get_current_user
from app.domains.users.schemas import UserPublic
from app.shared.db.database import get_session
from app.shared.rbac.dependencies import (
    AnyPermissionChecker,
    PermissionChecker,
    require_permission,
)
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole

router = APIRouter(prefix='/schedules', tags=['schedules'])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# --------------------------------------------------------------------------- #
# HELPERS DE AUTORIZAÇÃO (ABAC leve sobre RBAC)                               #
# --------------------------------------------------------------------------- #


async def _check_classroom_access(
    user: User, classroom_id: int, session: AsyncSession
):
    if require_permission(user, SystemPermissions.SCHEDULES_VIEW_ALL):
        return

    if require_permission(user, SystemPermissions.SCHEDULES_VIEW_OWN):
        if user.classroom_id != classroom_id:
            raise HTTPException(403, 'Insufficient permissions')
        return

    if require_permission(user, SystemPermissions.SCHEDULES_VIEW_CHILD):
        # user.students usa lazy='noload' — nunca usar diretamente.
        # Verificamos via JOIN direto: guardian → guardian_student → aluno com classroom_id certo.
        student_in_class = await session.scalar(
            select(User.id)
            .join(
                guardian_student,
                (guardian_student.c.student_id == User.id)
                & (guardian_student.c.guardian_id == user.id),
            )
            .where(User.classroom_id == classroom_id)
            .limit(1)
        )
        if student_in_class is None:
            raise HTTPException(403, 'Insufficient permissions')
        return

    raise HTTPException(403, 'Insufficient permissions')


def _check_teacher_access(user: User, teacher_id: int):
    # Professores têm SCHEDULES_VIEW_ALL, mas só podem ver a própria grade
    if user.role == UserRole.TEACHER:
        if user.id != teacher_id:
            raise HTTPException(403, 'Insufficient permissions')
        return

    # Coordenadores e admins têm acesso total (SCHEDULES_VIEW_ALL)
    if require_permission(user, SystemPermissions.SCHEDULES_VIEW_ALL):
        return

    # Qualquer outra role (aluno, responsável, porteiro, etc.) não pode
    # acessar a grade de um professor específico
    raise HTTPException(403, 'Insufficient permissions')


async def _get_slot_or_404(slot_id: int, session: AsyncSession):
    slot = await session.scalar(
        select(ScheduleSlot).where(ScheduleSlot.id == slot_id)
    )
    if not slot:
        raise HTTPException(404, 'ScheduleSlot not found')
    return slot


async def _get_override_or_404(override_id: int, session: AsyncSession):
    override = await session.scalar(
        select(ScheduleOverride).where(ScheduleOverride.id == override_id)
    )
    if not override:
        raise HTTPException(404, 'ScheduleOverride not found')
    return override


# --------------------------------------------------------------------------- #
# GET /schedules/periods                                                      #
# --------------------------------------------------------------------------- #


@router.get(
    '/periods',
    response_model=PeriodsList,
    dependencies=[Depends(get_current_user)],
)
async def list_periods():
    return PERIODS


# --------------------------------------------------------------------------- #
# GET /schedules/classroom/{classroom_id}                                     #
# --------------------------------------------------------------------------- #


@router.get(
    '/classroom/{classroom_id}',
    response_model=SlotList,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
                SystemPermissions.SCHEDULES_VIEW_CHILD,
            })
        )
    ],
)
async def list_classroom_schedule(
    session: Session,
    current_user: CurrentUser,
    classroom_id: int = Path(alias='classroom_id'),
):
    await _check_classroom_access(current_user, classroom_id, session)

    result = await session.scalars(
        select(ScheduleSlot).where(ScheduleSlot.classroom_id == classroom_id)
    )

    slots = result.all()

    return SlotList(slots=[SlotPublic.model_validate(slot) for slot in slots])


# --------------------------------------------------------------------------- #
# GET /schedules/teacher/{user_id}                                            #
# --------------------------------------------------------------------------- #


@router.get(
    '/teacher/{user_id}',
    response_model=SlotList,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
            })
        )
    ],
)
async def list_teacher_schedule(
    session: Session,
    current_user: CurrentUser,
    user_id: int = Path(alias='user_id'),
):
    _check_teacher_access(current_user, user_id)

    result = await session.scalars(
        select(ScheduleSlot).where(ScheduleSlot.teacher_id == user_id)
    )

    slots = result.all()

    return SlotList(slots=[SlotPublic.model_validate(slot) for slot in slots])


# --------------------------------------------------------------------------- #
# GET /schedules/current-teacher/{classroom_id}                               #
# --------------------------------------------------------------------------- #


@router.get(
    '/current-teacher/{classroom_id}',
    response_model=UserPublic,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
                SystemPermissions.SCHEDULES_VIEW_CHILD,
            })
        )
    ],
)
async def get_current_teacher_by_classroom(
    session: Session,
    current_user: CurrentUser,
    classroom_id: int = Path(alias='classroom_id'),
):
    await _check_classroom_access(current_user, classroom_id, session)

    current_teacher = await get_current_teacher(
        classroom_id, datetime.now().time(), session
    )

    if not current_teacher:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            'No teacher in class at this time',
        )

    return current_teacher


# --------------------------------------------------------------------------- #
# POST /schedules/slots                                                       #
# --------------------------------------------------------------------------- #


@router.post(
    '/slots',
    response_model=SlotPublic,
    status_code=HTTPStatus.CREATED,
    dependencies=[
        Depends(get_current_user),
        Depends(PermissionChecker({SystemPermissions.SCHEDULES_MANAGE})),
    ],
)
async def create_slot(
    data: SlotCreate,
    session: Session,
):
    existing = await session.scalar(
        select(ScheduleSlot).where(
            ScheduleSlot.classroom_id == data.classroom_id,
            ScheduleSlot.weekday == data.weekday,
            ScheduleSlot.period_number == data.period_number,
            ScheduleSlot.type == data.type,
        )
    )

    if existing:
        raise HTTPException(409, 'Schedule slot already exists')

    slot = ScheduleSlot(**data.model_dump())
    session.add(slot)

    await session.commit()
    await session.refresh(slot)

    return slot


# --------------------------------------------------------------------------- #
# PUT /schedules/slots/{slot_id}                                              #
# --------------------------------------------------------------------------- #


@router.put(
    '/slots/{slot_id}',
    response_model=SlotPublic,
    dependencies=[
        Depends(get_current_user),
        Depends(PermissionChecker({SystemPermissions.SCHEDULES_MANAGE})),
    ],
)
async def update_slot(
    data: SlotCreate,
    session: Session,
    slot_id: int = Path(alias='slot_id'),
):
    slot = await _get_slot_or_404(slot_id, session)

    existing = await session.scalar(
        select(ScheduleSlot).where(
            ScheduleSlot.classroom_id == data.classroom_id,
            ScheduleSlot.weekday == data.weekday,
            ScheduleSlot.period_number == data.period_number,
            ScheduleSlot.type == data.type,
            ScheduleSlot.id != slot_id,
        )
    )

    if existing:
        raise HTTPException(409, 'Schedule slot already exists')

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)

    await session.commit()
    await session.refresh(slot)

    return slot


# --------------------------------------------------------------------------- #
# DELETE /schedules/slots/{slot_id}                                           #
# --------------------------------------------------------------------------- #


@router.delete(
    '/slots/{slot_id}',
    response_model=SlotPublic,
    dependencies=[
        Depends(get_current_user),
        Depends(PermissionChecker({SystemPermissions.SCHEDULES_MANAGE})),
    ],
)
async def delete_slot(
    session: Session,
    slot_id: int = Path(alias='slot_id'),
):
    slot = await _get_slot_or_404(slot_id, session)

    await session.delete(slot)
    await session.commit()

    return slot


# --------------------------------------------------------------------------- #
# GET /schedules/overrides                                                    #
# --------------------------------------------------------------------------- #


@router.get(
    '/overrides',
    response_model=OverrideList,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
                SystemPermissions.SCHEDULES_VIEW_CHILD,
            })
        ),
    ],
)
async def list_overrides(
    session: Session,
):
    result = await session.scalars(
        select(ScheduleOverride).order_by(
            ScheduleOverride.override_date.desc()
        )
    )
    overrides = list(result.all())

    # Popula classroom_ids a partir da tabela de associação
    output = []
    for ov in overrides:
        if not ov.affects_all:
            rows = await session.scalars(
                select(override_classrooms.c.classroom_id).where(
                    override_classrooms.c.override_id == ov.id
                )
            )
            cids = list(rows.all())
        else:
            cids = None
        pub = OverridePublic.model_validate(ov)
        pub = pub.model_copy(update={'classroom_ids': cids})
        output.append(pub)

    return OverrideList(overrides=output)


# --------------------------------------------------------------------------- #
# POST /schedules/overrides                                                   #
# --------------------------------------------------------------------------- #


@router.post(
    '/overrides',
    response_model=OverridePublic,
    status_code=HTTPStatus.CREATED,
    dependencies=[
        Depends(get_current_user),
        Depends(PermissionChecker({SystemPermissions.SCHEDULES_MANAGE})),
    ],
)
async def create_override(
    data: OverrideCreate,
    session: Session,
):
    # 1. Validar teacher_id se fornecido
    if data.teacher_id is not None:
        from app.domains.users.models import User as _User

        teacher_user = await session.get(_User, data.teacher_id)
        if not teacher_user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail='Teacher not found',
            )

    # 2. Criar override (sem classroom_ids, pois é tabela de associação)
    override = ScheduleOverride(**data.model_dump(exclude={'classroom_ids'}))

    session.add(override)

    # flush para obter override.id antes de inserir relações
    await session.flush()

    # 2. Inserir relações (override_classrooms) se necessário
    if not data.affects_all:
        # Se não afeta toda a escola, precisa de pelo menos uma turma
        if not data.classroom_ids:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='classroom_ids must be provided when affects_all=False',
            )

        await session.execute(
            override_classrooms.insert(),
            [
                {
                    'override_id': override.id,
                    'classroom_id': classroom_id,
                }
                for classroom_id in data.classroom_ids
            ],
        )

    # 3. Persistir e retornar
    await session.commit()
    await session.refresh(override)

    pub = OverridePublic.model_validate(override)
    cids = (
        list(data.classroom_ids)
        if (not data.affects_all and data.classroom_ids)
        else None
    )
    return pub.model_copy(update={'classroom_ids': cids})


# --------------------------------------------------------------------------- #
# DELETE /schedules/overrides/{override_id}                                   #
# --------------------------------------------------------------------------- #


@router.delete(
    '/overrides/{override_id}',
    response_model=OverridePublic,
    dependencies=[
        Depends(get_current_user),
        Depends(PermissionChecker({SystemPermissions.SCHEDULES_MANAGE})),
    ],
)
async def delete_override(
    session: Session,
    override_id: int = Path(alias='override_id'),
):
    override = await _get_override_or_404(override_id, session)

    # Carrega classroom_ids antes do delete
    # - CASCADE vai limpar a tabela de associação
    if not override.affects_all:
        rows = await session.scalars(
            select(override_classrooms.c.classroom_id).where(
                override_classrooms.c.override_id == override.id
            )
        )
        cids: list[int] | None = list(rows.all())
    else:
        cids = None

    await session.refresh(override)
    await session.delete(override)
    await session.commit()

    pub = OverridePublic.model_validate(override)
    return pub.model_copy(update={'classroom_ids': cids})


'''
# --------------------------------------------------------------------------- #
# GET /schedules/current-lesson — Aula atual do professor logado             #
# --------------------------------------------------------------------------- #


@router.get(
    '/current-lesson',
    response_model=dict,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
            })
        )
    ],
)
async def get_current_lesson(
    session: Session,
    current_user: CurrentUser,
):
    """
    Retorna informações da aula atual do professor logado.
    Inclui turma, horário, etc., se estiver em período de aula.
    """
    from datetime import datetime

    now = datetime.now().time()
    teacher = await get_current_teacher(current_user.id, now, session)

    if not teacher:
        return {'in_class': False}

    # Buscar o slot atual
    current_period = get_current_period(now, PERIODS)
    weekday = WeekdayEnum((date.today().weekday() + 1) % 7 + 1)

    # Verificar override primeiro
    schedule_override = await session.scalar(
        select(ScheduleOverride)
        .join(override_classrooms)
        .where(
            ScheduleOverride.date == date.today(),
            ScheduleOverride.start_time <= now,
            ScheduleOverride.end_time > now,
            ScheduleOverride.teacher_id == current_user.id,
        )
    )

    if schedule_override:
        classroom_id = await session.scalar(
            select(override_classrooms.c.classroom_id).where(
                override_classrooms.c.override_id == schedule_override.id
            )
        )
        return {
            'in_class': True,
            'classroom_id': classroom_id,
            'period': current_period.dict() if current_period else None,
            'weekday': weekday.value,
        }

    # Slot regular
    slot = await session.scalar(
        select(ScheduleSlot).where(
            ScheduleSlot.teacher_id == current_user.id,
            ScheduleSlot.weekday == weekday,
            ScheduleSlot.start_time <= now,
            ScheduleSlot.end_time > now,
        )
    )

    if slot:
        return {
            'in_class': True,
            'classroom_id': slot.classroom_id,
            'period': current_period.dict() if current_period else None,
            'weekday': weekday.value,
        }

    return {'in_class': False}
'''
