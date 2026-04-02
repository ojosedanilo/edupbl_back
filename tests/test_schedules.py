"""
Testes da feature Schedules.

Organização:
  1. Unitários (sem banco) — períodos e helpers puros
  2. CRUD de slots         — criar, 409, editar, deletar
  3. Leitura de grade      — classroom, teacher
  4. Controle de acesso    — RBAC + regras secundárias por role
  5. Helper de integração  — get_current_teacher com banco
  6. Overrides             — criar, listar, deletar
"""

from datetime import date, time
from http import HTTPStatus
from unittest.mock import patch

import pytest
import pytest_asyncio

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
from app.domains.schedules.periods import PERIODS
from app.domains.schedules.schemas import Period, Weekday
from app.domains.users.models import Classroom
from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token

# =========================================================================== #
# Helpers de teste                                                            #
# =========================================================================== #


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# =========================================================================== #
# Fixtures de banco                                                           #
# =========================================================================== #


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
async def slot(session, classroom, teacher):
    """Slot de segunda-feira, período 1."""
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


# =========================================================================== #
# 1. UNITÁRIOS — períodos (sem banco)                                        #
# =========================================================================== #


# =========================================================================== #
# 1. UNITÁRIOS — períodos (sem banco)                                        #
# =========================================================================== #

LIST_PERIODS_TO_VERIFY = [
    ('class_period', 1, time(7, 30), time(8, 20)),
    ('class_period', 2, time(8, 20), time(9, 10)),
    # Intervalo da manhã
    ('snack_break', None, time(9, 10), time(9, 30)),
    ('class_period', 3, time(9, 30), time(10, 20)),
    ('class_period', 4, time(10, 20), time(11, 10)),
    ('class_period', 5, time(11, 10), time(12, 0)),
    # Almoço
    ('lunch_break', None, time(12, 0), time(13, 20)),
    ('class_period', 6, time(13, 20), time(14, 10)),
    ('class_period', 7, time(14, 10), time(15, 0)),
    # Intervalo da tarde
    ('snack_break', None, time(15, 0), time(15, 20)),
    ('class_period', 8, time(15, 20), time(16, 10)),
    ('class_period', 9, time(16, 10), time(17, 0)),
]


def build_periods(periods_raw):
    return [
        Period(
            type=p[0],
            period_number=p[1],
            start=p[2],
            end=p[3],
        )
        for p in periods_raw
    ]


PERIODS_TO_VERIFY = build_periods(LIST_PERIODS_TO_VERIFY)


def test_periods_exact_sequence():
    """Garante que TODOS os períodos estão corretos e na ordem certa."""
    assert PERIODS.periods == PERIODS_TO_VERIFY


def test_periods_have_9_class_periods():
    class_periods = [p for p in PERIODS.periods if p.type == 'class_period']
    assert len(class_periods) == 9


def test_no_class_period_during_lunch():
    for t in [time(12, 0), time(12, 30), time(13, 0), time(13, 19)]:
        period = get_current_period(t, PERIODS)
        is_class = period is not None and period.type == 'class_period'
        assert not is_class, f'Hora {t} não deveria ser aula'


def test_no_period_before_school():
    assert get_current_period(time(7, 0), PERIODS) is None
    assert get_current_period(time(6, 0), PERIODS) is None


def test_no_period_after_school():
    assert get_current_period(time(17, 0), PERIODS) is None


def test_is_time_at_class_period_true():
    assert is_time_at_class_period(time(7, 45), PERIODS) is True
    assert is_time_at_class_period(time(10, 0), PERIODS) is True
    assert is_time_at_class_period(time(14, 30), PERIODS) is True
    assert is_time_at_class_period(time(16, 30), PERIODS) is True


def test_is_time_at_class_period_false_on_break():
    assert is_time_at_class_period(time(9, 15), PERIODS) is False
    assert is_time_at_class_period(time(12, 30), PERIODS) is False
    assert is_time_at_class_period(time(15, 10), PERIODS) is False


def test_is_time_at_class_period_false_outside_hours():
    assert is_time_at_class_period(time(7, 0), PERIODS) is False
    assert is_time_at_class_period(time(17, 30), PERIODS) is False


# =========================================================================== #
# 2. CRUD de slots                                                            #
# =========================================================================== #


@pytest.mark.asyncio
async def test_create_slot(client, classroom, teacher, coordinator):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': 'class_period',
            'title': 'Física',
            'weekday': Weekday.TUESDAY,
            'period_number': 2,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['title'] == 'Física'
    assert body['weekday'] == Weekday.TUESDAY
    assert body['period_number'] == 2
    assert 'id' in body


@pytest.mark.asyncio
async def test_create_slot_duplicate_returns_409(client, slot, coordinator):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'type': slot.type,
            'title': 'Duplicado',
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_create_slot_without_teacher(client, classroom, coordinator):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': None,
            'type': 'class_period',
            'title': 'Vago',
            'weekday': Weekday.FRIDAY,
            'period_number': 9,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['teacher_id'] is None


@pytest.mark.asyncio
async def test_update_slot_title(client, slot, coordinator):
    resp = client.put(
        f'/schedules/slots/{slot.id}',
        json={
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'type': slot.type,
            'title': 'Química Atualizada',
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Química Atualizada'


@pytest.mark.asyncio
async def test_update_slot_conflict_with_other_returns_409(
    client, slot, classroom, teacher, coordinator
):
    # Cria segundo slot em período diferente
    r = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': 'class_period',
            'title': 'Biologia',
            'weekday': Weekday.MONDAY,
            'period_number': 2,
        },
        headers=_auth(coordinator),
    )
    second_id = r.json()['id']

    # Tenta mover para o período do `slot` original
    resp = client.put(
        f'/schedules/slots/{second_id}',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': 'class_period',
            'title': 'Biologia',
            'weekday': Weekday.MONDAY,
            'period_number': 1,  # já ocupado
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_update_slot_self_no_409(client, slot, coordinator):
    resp = client.put(
        f'/schedules/slots/{slot.id}',
        json={
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'type': slot.type,
            'title': 'Novo Nome',
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_update_slot_not_found(client, coordinator):
    resp = client.put(
        '/schedules/slots/9999',
        json={
            'classroom_id': 1,
            'teacher_id': None,
            'type': 'class_period',
            'title': 'X',
            'weekday': Weekday.MONDAY,
            'period_number': 1,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


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


# =========================================================================== #
# 3. Leitura de grade                                                         #
# =========================================================================== #


@pytest.mark.asyncio
async def test_list_periods(client, coordinator):
    resp = client.get('/schedules/periods', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'periods' in body
    class_periods = [p for p in body['periods'] if p['type'] == 'class_period']
    assert len(class_periods) == 9


@pytest.mark.asyncio
async def test_list_classroom_schedule_returns_slots(
    client, slot, coordinator
):
    resp = client.get(
        f'/schedules/classroom/{slot.classroom_id}',
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'slots' in body
    assert any(s['id'] == slot.id for s in body['slots'])


@pytest.mark.asyncio
async def test_list_teacher_schedule_returns_slots(client, slot, coordinator):
    resp = client.get(
        f'/schedules/teacher/{slot.teacher_id}',
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'slots' in body
    assert any(s['id'] == slot.id for s in body['slots'])


# =========================================================================== #
# 4. Controle de acesso                                                       #
# =========================================================================== #


@pytest.mark.asyncio
async def test_student_sees_own_classroom(client, slot, student):
    resp = client.get(
        f'/schedules/classroom/{student.classroom_id}',
        headers=_auth(student),
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_student_cannot_see_other_classroom(
    client, slot, student_b, classroom
):
    resp = client.get(
        f'/schedules/classroom/{classroom.id}',
        headers=_auth(student_b),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_teacher_sees_any_classroom(client, slot, teacher):
    resp = client.get(
        f'/schedules/classroom/{slot.classroom_id}',
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_teacher_sees_own_grade(client, slot, teacher):
    resp = client.get(
        f'/schedules/teacher/{teacher.id}',
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_teacher_cannot_see_other_teacher_grade(
    client, slot, other_teacher
):
    resp = client.get(
        f'/schedules/teacher/{slot.teacher_id}',
        headers=_auth(other_teacher),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_student_cannot_see_teacher_grade(client, slot, student):
    resp = client.get(
        f'/schedules/teacher/{slot.teacher_id}',
        headers=_auth(student),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_porter_sees_classroom(client, slot, porter):
    resp = client.get(
        f'/schedules/classroom/{slot.classroom_id}',
        headers=_auth(porter),
    )
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_porter_cannot_create_slot(client, classroom, teacher, porter):
    resp = client.post(
        '/schedules/slots',
        json={
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'type': 'class_period',
            'title': 'X',
            'weekday': Weekday.WEDNESDAY,
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
async def test_unauthenticated_cannot_access_periods(client):
    resp = client.get('/schedules/periods')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# =========================================================================== #
# 5. Helper get_current_teacher — integração com banco                        #
# =========================================================================== #

# 2026-03-30 = segunda-feira → weekday Python = 0 → nosso Weekday = 2 (MONDAY)
_MONDAY = date(2026, 3, 30)


@pytest.mark.asyncio
async def test_helper_returns_teacher_during_class(
    session, classroom, teacher
):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
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
async def test_helper_returns_none_on_morning_break(
    session, classroom, teacher
):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
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
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
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
        type='class_period',
        title='Vago',
        weekday=Weekday.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()

    with patch('app.domains.schedules.helpers.date') as mock_d:
        mock_d.today.return_value = _MONDAY
        result = await get_current_teacher(classroom.id, time(7, 45), session)

    assert result is None


@pytest.mark.asyncio
async def test_helper_returns_none_with_affects_all_override(
    session, classroom, teacher
):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
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
async def test_helper_override_specific_classroom_does_not_affect_other(
    session, classroom, classroom_b, teacher
):
    """Override afetando só turma B não deve bloquear turma A."""
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
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
async def test_helper_override_specific_classroom_blocks_that_classroom(
    session, classroom, teacher
):
    """Override afetando só turma A deve bloquear turma A."""
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática',
        weekday=Weekday.MONDAY,
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


# =========================================================================== #
# 6. Overrides — CRUD via HTTP                                                #
# =========================================================================== #


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
    assert body['title'] == 'Feriado Municipal'
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
async def test_create_override_affects_false_no_classrooms_returns_400(
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
async def test_list_overrides_returns_wrapper(client, coordinator):
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Evento Teste',
            'override_date': '2026-06-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'overrides' in body
    assert len(body['overrides']) >= 1


@pytest.mark.asyncio
async def test_delete_override(client, coordinator):
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


@pytest.mark.asyncio
async def test_delete_override_not_found(client, coordinator):
    resp = client.delete(
        '/schedules/overrides/9999', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


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


@pytest.mark.asyncio
async def test_porter_can_view_overrides(client, porter):
    resp = client.get('/schedules/overrides', headers=_auth(porter))
    assert resp.status_code == HTTPStatus.OK
