"""
Testes de schedules/ — suite completa.

Organização:
  1. Unitários (sem banco)   — períodos, overlaps, Period.contains
  2. CRUD de slots           — criar, 409, editar, deletar
  3. Leitura de grade        — /classroom, /teacher, /current-teacher
  4. Controle de acesso      — RBAC + regras por role (guardian, student, porter)
  5. Helper get_current_teacher — integração com banco
  6. Overrides               — criar, listar (affects_all e específico), deletar
  7. Unitário de rota        — _check_classroom_access sem nenhuma permissão
"""

from datetime import date, time
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.domains.schedules.enums import PeriodTypeEnum, WeekdayEnum
from app.domains.schedules.helpers import (
    get_current_period,
    get_current_teacher,
    is_time_at_class_period,
)
from app.domains.schedules.models import (
    ScheduleOverride,
    ScheduleSlot,
    override_classrooms,
)
from app.domains.schedules.periods import PERIODS, overlaps
from app.domains.schedules.routers import _check_classroom_access
from app.domains.schedules.schemas import Period
from app.domains.users.models import Classroom, guardian_student
from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest_asyncio.fixture
async def classroom(session):
    c = Classroom(name='3A')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def classroom_b(session):
    c = Classroom(name='3B')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def other_teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def porter(session):
    return await _make_user(session, role=UserRole.PORTER)


@pytest_asyncio.fixture
async def student(session, classroom):
    return await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )


@pytest_asyncio.fixture
async def student_b(session, classroom_b):
    return await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom_b.id
    )


@pytest_asyncio.fixture
async def guardian(session, student):
    """Responsável com filho vinculado à classroom via guardian_student."""
    g = await _make_user(session, role=UserRole.GUARDIAN)
    await session.execute(
        guardian_student.insert().values(
            guardian_id=g.id, student_id=student.id
        )
    )
    await session.commit()
    await session.refresh(g)
    return g


@pytest_asyncio.fixture
async def slot(session, classroom, teacher):
    """Slot de segunda-feira, período 1."""
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@pytest_asyncio.fixture
async def override_specific(client, coordinator, classroom):
    """Override com affects_all=False vinculado a classroom."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Override Específico',
            'override_date': '2099-01-15',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [classroom.id],
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    return resp.json()


# ===========================================================================
# 1. Unitários — períodos e helpers puros (sem banco)
# ===========================================================================

LIST_PERIODS_TO_VERIFY = [
    (PeriodTypeEnum.CLASS_PERIOD, 1, time(7, 30), time(8, 20)),
    (PeriodTypeEnum.CLASS_PERIOD, 2, time(8, 20), time(9, 10)),
    (PeriodTypeEnum.SNACK_BREAK, None, time(9, 10), time(9, 30)),
    (PeriodTypeEnum.CLASS_PERIOD, 3, time(9, 30), time(10, 20)),
    (PeriodTypeEnum.CLASS_PERIOD, 4, time(10, 20), time(11, 10)),
    (PeriodTypeEnum.CLASS_PERIOD, 5, time(11, 10), time(12, 0)),
    (PeriodTypeEnum.LUNCH_BREAK, None, time(12, 0), time(13, 20)),
    (PeriodTypeEnum.CLASS_PERIOD, 6, time(13, 20), time(14, 10)),
    (PeriodTypeEnum.CLASS_PERIOD, 7, time(14, 10), time(15, 0)),
    (PeriodTypeEnum.SNACK_BREAK, None, time(15, 0), time(15, 20)),
    (PeriodTypeEnum.CLASS_PERIOD, 8, time(15, 20), time(16, 10)),
    (PeriodTypeEnum.CLASS_PERIOD, 9, time(16, 10), time(17, 0)),
]
PERIODS_TO_VERIFY = [
    Period(type=p[0], period_number=p[1], start=p[2], end=p[3])
    for p in LIST_PERIODS_TO_VERIFY
]


def test_periods_exact_sequence():
    """Todos os períodos estão corretos e na ordem certa."""
    assert PERIODS.periods == PERIODS_TO_VERIFY


def test_periods_have_9_class_periods():
    class_periods = [p for p in PERIODS.periods if p.type.requires_teacher]
    assert len(class_periods) == 9


def test_no_class_period_during_lunch():
    for t in [time(12, 0), time(12, 30), time(13, 0), time(13, 19)]:
        period = get_current_period(t, PERIODS)
        assert not (
            period is not None and period.type == PeriodTypeEnum.CLASS_PERIOD
        )


def test_no_period_before_school():
    assert get_current_period(time(7, 0), PERIODS) is None
    assert get_current_period(time(6, 0), PERIODS) is None


def test_no_period_after_school():
    assert get_current_period(time(17, 0), PERIODS) is None


def test_is_time_at_class_period_true():
    assert is_time_at_class_period(time(7, 45), PERIODS) is True
    assert is_time_at_class_period(time(10, 0), PERIODS) is True
    assert is_time_at_class_period(time(16, 30), PERIODS) is True


def test_is_time_at_class_period_false_on_break():
    assert is_time_at_class_period(time(9, 15), PERIODS) is False
    assert is_time_at_class_period(time(12, 30), PERIODS) is False
    assert is_time_at_class_period(time(15, 10), PERIODS) is False


def test_is_time_at_class_period_false_outside_hours():
    assert is_time_at_class_period(time(7, 0), PERIODS) is False
    assert is_time_at_class_period(time(17, 30), PERIODS) is False


def test_overlaps_midnight_crossing_true():
    """23:00–01:00 sobrepõe 00:30–02:00."""
    assert overlaps(time(23, 0), time(1, 0), time(0, 30), time(2, 0)) is True


def test_overlaps_midnight_crossing_false():
    """23:00–01:00 NÃO sobrepõe 02:00–04:00."""
    assert overlaps(time(23, 0), time(1, 0), time(2, 0), time(4, 0)) is False


def test_period_contains_midnight_true():
    p = Period(
        type=PeriodTypeEnum.CLASS_PERIOD,
        period_number=1,
        start=time(23, 0),
        end=time(1, 0),
    )
    assert p.contains(time(23, 30)) is True
    assert p.contains(time(0, 30)) is True


def test_period_contains_midnight_false():
    p = Period(
        type=PeriodTypeEnum.CLASS_PERIOD,
        period_number=1,
        start=time(23, 0),
        end=time(1, 0),
    )
    assert p.contains(time(2, 0)) is False


# ===========================================================================
# 2. CRUD de slots
# ===========================================================================


@pytest.mark.asyncio
async def test_create_slot(client, classroom, teacher, coordinator):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'Física',
            'weekday': WeekdayEnum.TUESDAY,
            'period_number': 2,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['title'] == 'Física'


@pytest.mark.asyncio
async def test_create_slot_without_teacher(client, classroom, coordinator):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': None,
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'Vago',
            'weekday': WeekdayEnum.FRIDAY,
            'period_number': 9,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['teacher_id'] is None


@pytest.mark.asyncio
async def test_create_slot_duplicate_returns_409(client, slot, coordinator):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'type': slot.type.value,
            'title': 'Duplicado',
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_create_slot_student_forbidden(client, session, classroom):
    stud = await _make_user(session, role=UserRole.STUDENT)
    resp = client.post(
        '/schedules/slots',
        json={
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'X',
            'classroom_id': classroom.id,
            'teacher_id': None,
            'weekday': WeekdayEnum.MONDAY,
            'period_number': 1,
        },
        headers=_auth(stud),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_update_slot_title(client, slot, coordinator):
    resp = client.put(
        f'/schedules/slots/{slot.id}',
        json={
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'type': slot.type.value,
            'title': 'Química Atualizada',
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Química Atualizada'


@pytest.mark.asyncio
async def test_update_slot_self_no_409(client, slot, coordinator):
    resp = client.put(
        f'/schedules/slots/{slot.id}',
        json={
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'type': slot.type.value,
            'title': 'Novo Nome',
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_update_slot_conflict_with_other_returns_409(
    client, slot, classroom, teacher, coordinator
):
    r = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'Biologia',
            'weekday': WeekdayEnum.MONDAY,
            'period_number': 2,
        },
        headers=_auth(coordinator),
    )
    second_id = r.json()['id']
    resp = client.put(
        f'/schedules/slots/{second_id}',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'Biologia',
            'weekday': WeekdayEnum.MONDAY,
            'period_number': 1,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_update_slot_not_found(client, coordinator):
    resp = client.put(
        '/schedules/slots/9999',
        json={
            'classroom_id': 1,
            'teacher_id': None,
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'X',
            'weekday': WeekdayEnum.MONDAY,
            'period_number': 1,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'ScheduleSlot not found'


@pytest.mark.asyncio
async def test_delete_slot(client, slot, coordinator):
    resp = client.delete(
        f'/schedules/slots/{slot.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == slot.id


@pytest.mark.asyncio
async def test_delete_slot_not_found(client, coordinator):
    resp = client.delete('/schedules/slots/9999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'ScheduleSlot not found'


# ===========================================================================
# 3. Leitura de grade
# ===========================================================================


@pytest.mark.asyncio
async def test_list_periods_authenticated(client, coordinator):
    resp = client.get('/schedules/periods', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    class_periods = [
        p
        for p in resp.json()['periods']
        if p['type'] == PeriodTypeEnum.CLASS_PERIOD.value
    ]
    assert len(class_periods) == 9


@pytest.mark.asyncio
async def test_list_periods_unauthenticated(client):
    resp = client.get('/schedules/periods')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_list_classroom_schedule_returns_slots(
    client, slot, coordinator
):
    resp = client.get(
        f'/schedules/classroom/{slot.classroom_id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert any(s['id'] == slot.id for s in resp.json()['slots'])


@pytest.mark.asyncio
async def test_list_teacher_schedule_returns_slots(client, slot, coordinator):
    resp = client.get(
        f'/schedules/teacher/{slot.teacher_id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert any(s['id'] == slot.id for s in resp.json()['slots'])


@pytest.mark.asyncio
async def test_get_current_teacher_found(
    client, coordinator, classroom, teacher
):
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = teacher
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(coordinator),
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == teacher.id


@pytest.mark.asyncio
async def test_get_current_teacher_not_found(client, coordinator, classroom):
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = None
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(coordinator),
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'No teacher in class at this time'


@pytest.mark.asyncio
async def test_get_current_teacher_guardian_own_class(
    client, guardian, classroom, teacher
):
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = teacher
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(guardian),
        )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_current_teacher_guardian_other_class_forbidden(
    client, guardian, classroom_b
):
    resp = client.get(
        f'/schedules/current-teacher/{classroom_b.id}', headers=_auth(guardian)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# 4. Controle de acesso — RBAC + regras secundárias
# ===========================================================================


@pytest.mark.asyncio
async def test_student_sees_own_classroom(client, slot, student):
    resp = client.get(
        f'/schedules/classroom/{student.classroom_id}', headers=_auth(student)
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_student_cannot_see_other_classroom(
    client, slot, student_b, classroom
):
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(student_b)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_teacher_sees_any_classroom(client, slot, teacher):
    resp = client.get(
        f'/schedules/classroom/{slot.classroom_id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_teacher_sees_own_grade(client, slot, teacher):
    resp = client.get(
        f'/schedules/teacher/{teacher.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_teacher_cannot_see_other_teacher_grade(
    client, slot, other_teacher
):
    resp = client.get(
        f'/schedules/teacher/{slot.teacher_id}', headers=_auth(other_teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_student_cannot_see_teacher_grade(client, slot, student):
    resp = client.get(
        f'/schedules/teacher/{slot.teacher_id}', headers=_auth(student)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_porter_sees_classroom(client, slot, porter):
    resp = client.get(
        f'/schedules/classroom/{slot.classroom_id}', headers=_auth(porter)
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_porter_can_view_overrides(client, porter):
    resp = client.get('/schedules/overrides', headers=_auth(porter))
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_porter_cannot_create_slot(client, classroom, teacher, porter):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': PeriodTypeEnum.CLASS_PERIOD.value,
            'title': 'X',
            'weekday': WeekdayEnum.WEDNESDAY,
            'period_number': 3,
        },
        headers=_auth(porter),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_student_cannot_delete_slot(client, slot, student):
    resp = client.delete(f'/schedules/slots/{slot.id}', headers=_auth(student))
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_student_cannot_create_override(client, student):
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'X',
            'override_date': '2026-06-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': True,
        },
        headers=_auth(student),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# --- Guardian access (_check_classroom_access CHILD branch) ---


@pytest.mark.asyncio
async def test_guardian_with_child_in_class_gets_schedule(
    client, guardian, classroom
):
    """Guardian com filho na turma → 200 (JOIN em guardian_student retorna resultado)."""
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(guardian)
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_guardian_without_child_in_class_forbidden(
    client, session, classroom
):
    """Guardian sem filhos na turma → 403."""
    guardian_no_kids = await _make_user(session, role=UserRole.GUARDIAN)
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(guardian_no_kids)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Insufficient permissions'


@pytest.mark.asyncio
async def test_guardian_child_in_other_class_forbidden(
    client, session, classroom, classroom_b
):
    """Guardian com filho em B tentando acessar A → 403."""
    student_b = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom_b.id
    )
    guardian_b = await _make_user(session, role=UserRole.GUARDIAN)
    await session.execute(
        guardian_student.insert().values(
            guardian_id=guardian_b.id, student_id=student_b.id
        )
    )
    await session.commit()
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(guardian_b)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# --- AnyPermissionChecker → 403 ---


@pytest.mark.asyncio
async def test_any_permission_checker_403(client, session):
    """
    Guardian tem SCHEDULES_VIEW_CHILD mas não VIEW_ALL nem VIEW_OWN →
    AnyPermissionChecker lança 403 em GET /schedules/teacher/{id}.
    """
    guardian = await _make_user(session, role=UserRole.GUARDIAN)
    tok = create_access_token(data={'sub': guardian.email})
    resp = client.get(
        '/schedules/teacher/1',
        headers={'Authorization': f'Bearer {tok}'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Insufficient permissions'


# ===========================================================================
# 5. Helper get_current_teacher — integração com banco
# ===========================================================================

# 2026-03-30 = segunda-feira → weekday Python = 0 → nosso WeekdayEnum = 2 (MONDAY)
_MONDAY = date(2026, 3, 30)


@pytest.mark.asyncio
async def test_helper_returns_teacher_during_class(
    session, classroom, teacher
):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is not None
    assert result.id == teacher.id


@pytest.mark.asyncio
async def test_helper_returns_none_on_break(session, classroom, teacher):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(9, 20), session)

    assert result is None


@pytest.mark.asyncio
async def test_helper_returns_none_before_school(session, classroom, teacher):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(6, 0), session)

    assert result is None


@pytest.mark.asyncio
async def test_helper_returns_none_no_slot(session, classroom):
    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is None


@pytest.mark.asyncio
async def test_helper_returns_none_slot_without_teacher(session, classroom):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=None,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Vago',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is None


@pytest.mark.asyncio
async def test_helper_affects_all_override_blocks(session, classroom, teacher):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    override = ScheduleOverride(
        title='Simulado ENEM',
        override_date=_MONDAY,
        starts_at=time(7, 0),
        ends_at=time(12, 0),
        affects_all=True,
    )
    session.add(override)
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is None


@pytest.mark.asyncio
async def test_helper_specific_override_does_not_affect_other_class(
    session, classroom, classroom_b, teacher
):
    """Override afetando só turma B não bloqueia turma A."""
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    override = ScheduleOverride(
        title='Reunião 3B',
        override_date=_MONDAY,
        starts_at=time(7, 0),
        ends_at=time(12, 0),
        affects_all=False,
    )
    session.add(override)
    await session.flush()
    await session.execute(
        override_classrooms.insert(),
        [{'override_id': override.id, 'classroom_id': classroom_b.id}],
    )
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is not None
    assert result.id == teacher.id


@pytest.mark.asyncio
async def test_helper_specific_override_blocks_target_class(
    session, classroom, teacher
):
    """Override afetando turma A bloqueia turma A."""
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type=PeriodTypeEnum.CLASS_PERIOD,
        title='Matemática',
        weekday=WeekdayEnum.MONDAY,
        period_number=1,
    )
    session.add(s)
    override = ScheduleOverride(
        title='Evento 3A',
        override_date=_MONDAY,
        starts_at=time(7, 0),
        ends_at=time(12, 0),
        affects_all=False,
    )
    session.add(override)
    await session.flush()
    await session.execute(
        override_classrooms.insert(),
        [{'override_id': override.id, 'classroom_id': classroom.id}],
    )
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is None


# ===========================================================================
# 6. Overrides — criar, listar, deletar via HTTP
# ===========================================================================


@pytest.mark.asyncio
async def test_create_override_affects_all(client, coordinator):
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Feriado Municipal',
            'override_date': '2026-06-24',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['affects_all'] is True
    assert body['classroom_ids'] is None


@pytest.mark.asyncio
async def test_create_override_specific_classroom(
    client, coordinator, classroom
):
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Simulado 3A',
            'override_date': '2026-05-10',
            'starts_at': '07:30:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [classroom.id],
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['affects_all'] is False
    assert classroom.id in body['classroom_ids']


@pytest.mark.asyncio
async def test_create_override_affects_false_no_classrooms_400(
    client, coordinator
):
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Sem turma',
            'override_date': '2026-05-10',
            'starts_at': '07:30:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [],
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_create_override_porter_forbidden(client, session):
    porter = await _make_user(session, role=UserRole.PORTER)
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'X',
            'override_date': '2027-05-01',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(porter),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_create_override_with_teacher_id(client, coordinator, teacher):
    """Override com teacher_id válido → 201 com teacher_id preenchido."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Substituição',
            'override_date': '2026-06-01',
            'starts_at': '07:30:00',
            'ends_at': '12:00:00',
            'affects_all': True,
            'teacher_id': teacher.id,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['teacher_id'] == teacher.id


@pytest.mark.asyncio
async def test_create_override_with_invalid_teacher_id_404(
    client, coordinator
):
    """teacher_id inexistente → 404."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'X',
            'override_date': '2026-06-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': True,
            'teacher_id': 99999,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Teacher not found'


@pytest.mark.asyncio
async def test_create_override_without_teacher_id_is_null(client, coordinator):
    """teacher_id omitido → campo None na resposta."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Genérico',
            'override_date': '2026-06-02',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['teacher_id'] is None


@pytest.mark.asyncio
async def test_list_overrides_affects_all_classroom_ids_null(
    client, coordinator
):
    """Override affects_all=True → classroom_ids=None na listagem."""
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Feriado Nacional',
            'override_date': '2099-09-07',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    all_ovs = [o for o in resp.json()['overrides'] if o['affects_all']]
    assert len(all_ovs) >= 1
    assert all_ovs[0]['classroom_ids'] is None


@pytest.mark.asyncio
async def test_list_overrides_specific_populates_classroom_ids(
    client, coordinator, classroom, override_specific
):
    """Override affects_all=False → classroom_ids preenchido na listagem."""
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    specific = [o for o in resp.json()['overrides'] if not o['affects_all']]
    assert len(specific) >= 1
    assert classroom.id in specific[0]['classroom_ids']


@pytest.mark.asyncio
async def test_delete_override_affects_all(client, coordinator):
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Para Deletar',
            'override_date': '2026-07-01',
            'starts_at': '07:00:00',
            'ends_at': '17:00:00',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    oid = r.json()['id']
    resp = client.delete(
        f'/schedules/overrides/{oid}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == oid
    assert resp.json()['classroom_ids'] is None


@pytest.mark.asyncio
async def test_delete_override_specific_returns_classroom_ids(
    client, coordinator, classroom, override_specific
):
    """DELETE override affects_all=False → classroom_ids na resposta."""
    oid = override_specific['id']
    resp = client.delete(
        f'/schedules/overrides/{oid}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body['affects_all'] is False
    assert body['classroom_ids'] is not None
    assert classroom.id in body['classroom_ids']


@pytest.mark.asyncio
async def test_delete_override_not_found(client, coordinator):
    resp = client.delete(
        '/schedules/overrides/9999', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'ScheduleOverride not found'


# ===========================================================================
# 7. Unitário de rota — _check_classroom_access raise final (linha 108)
# ===========================================================================


@pytest.mark.asyncio
async def test_check_classroom_access_no_permission_raises_403(session):
    """
    Usuário sem VIEW_ALL, VIEW_OWN nem VIEW_CHILD → raise final → 403.

    Não atingível via HTTP (AnyPermissionChecker bloqueia antes);
    testado chamando _check_classroom_access diretamente com role inexistente.
    """
    user = MagicMock()
    user.role = 'role_sem_permissoes'
    user.is_tutor = False
    user.classroom_id = None

    with pytest.raises(HTTPException) as exc_info:
        await _check_classroom_access(user, classroom_id=1, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == 'Insufficient permissions'
