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

  GET    /schedules/teachers
         → SCHEDULES_VIEW_(OWN | CHILD | ALL)
         → VIEW_ALL → todos os professores ativos
         → VIEW_OWN (professor) → apenas o próprio perfil
         → VIEW_CHILD (responsável) → professores das turmas dos filhos

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
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedules.helpers import get_current_teacher
from app.domains.schedules.models import (
    ScheduleOverride,
    ScheduleSlot,
    override_classrooms,
)
from app.domains.schedules.periods import PERIODS
from app.domains.schedules.schemas import (
    BulkClassroomsResponse,
    BulkOverridesResponse,
    BulkTeachersResponse,
    OverrideCreate,
    OverrideList,
    OverridePublic,
    PeriodsList,
    SlotCreate,
    SlotList,
    SlotPublic,
    TeacherSummary,
    TeacherSummaryList,
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


@router.get(
    '/bulk/classrooms',
    response_model=BulkClassroomsResponse,
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
async def bulk_classroom_schedules(
    session: Session,
    current_user: CurrentUser,
    ids: list[int] = Query(
        ..., description='IDs das turmas separados por vírgula'
    ),
):
    """
    Retorna slots de múltiplas turmas em uma única query, agrupados por
    classroom_id. Aplica as mesmas regras de acesso do endpoint individual:

      - VIEW_ALL  → qualquer turma da lista
      - VIEW_OWN  → apenas a própria turma (filtra ids automaticamente)
      - VIEW_CHILD → apenas turmas com filho do responsável (filtra automaticamente)

    IDs não autorizados são silenciosamente ignorados — nunca dispara 403
    para o conjunto todo, apenas remove turmas sem acesso.
    """
    # 1. Determinar quais classroom_ids o usuário pode realmente ver
    if require_permission(current_user, SystemPermissions.SCHEDULES_VIEW_ALL):
        allowed_ids = ids

    elif require_permission(
        current_user, SystemPermissions.SCHEDULES_VIEW_OWN
    ):
        # Aluno/Professor só enxerga a própria turma
        allowed_ids = (
            [current_user.classroom_id]
            if current_user.classroom_id in ids
            else []
        )

    elif require_permission(
        current_user, SystemPermissions.SCHEDULES_VIEW_CHILD
    ):
        # Responsável: apenas turmas onde tem filho
        rows = await session.scalars(
            select(User.classroom_id)
            .join(
                guardian_student,
                (guardian_student.c.student_id == User.id)
                & (guardian_student.c.guardian_id == current_user.id),
            )
            .where(
                User.classroom_id.is_not(None),
                User.classroom_id.in_(ids),
            )
            .distinct()
        )
        allowed_ids = [cid for cid in rows.all() if cid is not None]

    else:
        raise HTTPException(403, 'Insufficient permissions')

    if not allowed_ids:
        return BulkClassroomsResponse(slots_by_classroom={})

    # 2. Uma única query para todos os slots
    result = await session.scalars(
        select(ScheduleSlot).where(ScheduleSlot.classroom_id.in_(allowed_ids))
    )

    slots_by_classroom: dict[int, list[SlotPublic]] = {
        cid: [] for cid in allowed_ids
    }
    for slot in result.all():
        slots_by_classroom[slot.classroom_id].append(
            SlotPublic.model_validate(slot)
        )

    return BulkClassroomsResponse(slots_by_classroom=slots_by_classroom)


# --------------------------------------------------------------------------- #
# GET /schedules/bulk/teachers                                                #
# --------------------------------------------------------------------------- #


@router.get(
    '/bulk/teachers',
    response_model=BulkTeachersResponse,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
            })
        )
    ],
)
async def bulk_teacher_schedules(
    session: Session,
    current_user: CurrentUser,
    ids: list[int] = Query(
        ..., description='IDs dos professores separados por vírgula'
    ),
):
    """
    Retorna slots de múltiplos professores em uma única query, agrupados por
    teacher_id. Regras de acesso:

      - Coordenadores/Admins (VIEW_ALL) → qualquer professor da lista
      - Professores (VIEW_OWN, mas com VIEW_ALL no RBAC): só o próprio id
        (outros ids são silenciosamente removidos)

    IDs não autorizados são silenciosamente ignorados.
    """
    if current_user.role == UserRole.TEACHER:
        # Professor só pode ver a própria grade
        allowed_ids = [current_user.id] if current_user.id in ids else []
    elif require_permission(
        current_user, SystemPermissions.SCHEDULES_VIEW_ALL
    ):
        allowed_ids = ids
    else:
        raise HTTPException(403, 'Insufficient permissions')

    if not allowed_ids:
        return BulkTeachersResponse(slots_by_teacher={})

    result = await session.scalars(
        select(ScheduleSlot).where(ScheduleSlot.teacher_id.in_(allowed_ids))
    )

    slots_by_teacher: dict[int, list[SlotPublic]] = {
        tid: [] for tid in allowed_ids
    }
    for slot in result.all():
        if slot.teacher_id in slots_by_teacher:
            slots_by_teacher[slot.teacher_id].append(
                SlotPublic.model_validate(slot)
            )

    return BulkTeachersResponse(slots_by_teacher=slots_by_teacher)


# --------------------------------------------------------------------------- #
# GET /schedules/bulk/overrides                                               #
# --------------------------------------------------------------------------- #


@router.get(
    '/bulk/overrides',
    response_model=BulkOverridesResponse,
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
async def bulk_overrides(
    session: Session,
    classroom_ids: list[int] = Query(
        default=[],
        description='Turmas de interesse (opcional)',
    ),
    teacher_ids: list[int] = Query(
        default=[],
        description='Professores de interesse (opcional)',
    ),
):
    """
    Retorna todos os overrides relevantes para o conjunto de turmas/professores
    informado, em uma única query:

      - Sempre inclui overrides com affects_all=True (impactam toda a escola)
      - Inclui overrides vinculados a qualquer classroom_id da lista
      - Inclui overrides vinculados a qualquer teacher_id da lista

    Pelo menos um dos parâmetros (classroom_ids ou teacher_ids) deve ser
    fornecido; se ambos forem omitidos, retorna apenas overrides affects_all.
    """

    # Subquery: override tem pelo menos uma das classroom_ids pedidas
    classroom_filter = (
        exists().where(
            override_classrooms.c.override_id == ScheduleOverride.id,
            override_classrooms.c.classroom_id.in_(classroom_ids),
        )
        if classroom_ids
        else None
    )

    # Filtro direto por teacher_id
    teacher_filter = (
        ScheduleOverride.teacher_id.in_(teacher_ids) if teacher_ids else None
    )

    # Monta condição: affects_all OU classroom match OU teacher match
    conditions = [ScheduleOverride.affects_all.is_(True)]
    if classroom_filter is not None:
        conditions.append(classroom_filter)
    if teacher_filter is not None:
        conditions.append(teacher_filter)

    result = await session.scalars(
        select(ScheduleOverride)
        .where(or_(*conditions))
        .order_by(ScheduleOverride.override_date.desc())
    )
    overrides = list(result.all())

    # Popula classroom_ids de cada override a partir da tabela de associação
    # Uma única query usando IN para evitar N+1
    non_all_ids = [ov.id for ov in overrides if not ov.affects_all]
    classroom_map: dict[int, list[int]] = {}
    if non_all_ids:
        assoc_rows = await session.execute(
            select(
                override_classrooms.c.override_id,
                override_classrooms.c.classroom_id,
            ).where(override_classrooms.c.override_id.in_(non_all_ids))
        )
        for override_id, classroom_id in assoc_rows.all():
            classroom_map.setdefault(override_id, []).append(classroom_id)

    output: list[OverridePublic] = []
    for ov in overrides:
        pub = OverridePublic.model_validate(ov)
        cids = None if ov.affects_all else classroom_map.get(ov.id, [])
        output.append(pub.model_copy(update={'classroom_ids': cids}))

    return BulkOverridesResponse(overrides=output)


# --------------------------------------------------------------------------- #
# GET /schedules/guardian — Turmas e horários dos filhos do responsável      #
# --------------------------------------------------------------------------- #


@router.get(
    '/guardian',
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_CHILD,
                SystemPermissions.SCHEDULES_VIEW_ALL,
            })
        )
    ],
)
async def list_guardian_schedules(
    session: Session,
    current_user: CurrentUser,
):
    """
    Retorna um dicionário { classroom_id: [slots] } com os horários de todas
    as turmas que têm pelo menos um aluno do qual o usuário logado é responsável.

    Acessível por:
      - Responsáveis (SCHEDULES_VIEW_CHILD) → apenas turmas dos seus filhos
      - Admins/Coordenadores (SCHEDULES_VIEW_ALL) → idem (escopo de responsável)
    """
    # 1. Descobrir quais classroom_ids o responsável tem acesso
    rows = await session.scalars(
        select(User.classroom_id)
        .join(
            guardian_student,
            (guardian_student.c.student_id == User.id)
            & (guardian_student.c.guardian_id == current_user.id),
        )
        .where(User.classroom_id.is_not(None))
        .distinct()
    )
    classroom_ids: list[int] = [cid for cid in rows.all() if cid is not None]

    if not classroom_ids:
        return {}

    # 2. Buscar todos os slots de uma vez
    result = await session.scalars(
        select(ScheduleSlot).where(
            ScheduleSlot.classroom_id.in_(classroom_ids)
        )
    )
    slots = result.all()

    # 3. Agrupar por classroom_id
    grouped: dict[int, list] = {cid: [] for cid in classroom_ids}
    for slot in slots:
        grouped[slot.classroom_id].append(
            SlotPublic.model_validate(slot).model_dump()
        )

    return grouped


# --------------------------------------------------------------------------- #
# GET /schedules/teachers — Lista reduzida de professores (sem dados sensíveis)#
# --------------------------------------------------------------------------- #


@router.get(
    '/teachers',
    response_model=TeacherSummaryList,
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
async def list_schedule_teachers(
    session: Session,
    current_user: CurrentUser,
) -> TeacherSummaryList:
    """
    Retorna perfis mínimos de professores (id, nome, classroom_id) para
    exibição nos cabeçalhos da grade de horários. Sem dados sensíveis.

    Regras de visibilidade por papel:
      - SCHEDULES_VIEW_ALL (coordenador/admin) → todos os professores ativos
      - SCHEDULES_VIEW_OWN (professor)         → apenas o próprio perfil
      - SCHEDULES_VIEW_CHILD (responsável)     → apenas professores que
          ministram aula em turmas onde o responsável tem filho matriculado
    """
    if require_permission(current_user, SystemPermissions.SCHEDULES_VIEW_ALL):
        # Todos os professores ativos
        rows = await session.scalars(
            select(User)
            .where(User.role == UserRole.TEACHER, User.is_active.is_(True))
            .order_by(User.first_name, User.last_name)
        )
        teachers = list(rows.all())

    elif require_permission(
        current_user, SystemPermissions.SCHEDULES_VIEW_OWN
    ):
        # Professor vê apenas a si mesmo
        teachers = [current_user]

    else:
        # Responsável: professores das turmas dos filhos
        # 1. Descobrir classroom_ids acessíveis
        cid_rows = await session.scalars(
            select(User.classroom_id)
            .join(
                guardian_student,
                (guardian_student.c.student_id == User.id)
                & (guardian_student.c.guardian_id == current_user.id),
            )
            .where(User.classroom_id.is_not(None))
            .distinct()
        )
        classroom_ids = [cid for cid in cid_rows.all() if cid is not None]

        if not classroom_ids:
            return TeacherSummaryList(teachers=[])

        # 2. Professores referenciados por slots dessas turmas
        teacher_id_rows = await session.scalars(
            select(ScheduleSlot.teacher_id)
            .where(
                ScheduleSlot.classroom_id.in_(classroom_ids),
                ScheduleSlot.teacher_id.is_not(None),
            )
            .distinct()
        )
        teacher_ids = [tid for tid in teacher_id_rows.all() if tid is not None]

        if not teacher_ids:
            return TeacherSummaryList(teachers=[])

        rows = await session.scalars(
            select(User)
            .where(User.id.in_(teacher_ids), User.is_active.is_(True))
            .order_by(User.first_name, User.last_name)
        )
        teachers = list(rows.all())

    return TeacherSummaryList(
        teachers=[TeacherSummary.model_validate(t) for t in teachers]
    )
