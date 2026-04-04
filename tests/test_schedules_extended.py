"""
Testes de schedules/ — cobertura completa.

Cobre:
  schedules/routers.py   89-96, 119-121, 128-130, 176-178, 209-211,
                         279-288, 311-330, 352-355, 384-402, 432-461, 485-500
  schedules/periods.py   35
  schedules/schemas.py   50
"""

from datetime import time
from http import HTTPStatus
from unittest.mock import patch

import pytest_asyncio

from app.domains.schedules.models import ScheduleSlot
from app.domains.schedules.periods import overlaps
from app.domains.schedules.schemas import Period, Weekday
from app.domains.users.models import Classroom, guardian_student
from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def classroom(session):
    c = Classroom(name='3A_sched')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def classroom_b(session):
    c = Classroom(name='3B_sched')
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
async def student(session, classroom):
    return await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )


@pytest_asyncio.fixture
async def guardian(session, student):
    """Responsável com o aluno vinculado via guardian_student."""
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


# ===========================================================================
# schedules/periods.py — linha 35: cruzamento de meia-noite
# ===========================================================================


def test_overlaps_midnight_crossing_interval():
    """periods.py line 35: 23:00–01:00 sobrepõe 00:30–02:00."""
    result = overlaps(time(23, 0), time(1, 0), time(0, 30), time(2, 0))
    assert result is True


def test_overlaps_midnight_no_overlap():
    """periods.py line 35: 23:00–01:00 NÃO sobrepõe 02:00–04:00."""
    result = overlaps(time(23, 0), time(1, 0), time(2, 0), time(4, 0))
    assert result is False


# ===========================================================================
# schedules/schemas.py — linha 50: Period.contains() com meia-noite
# ===========================================================================


def test_period_contains_midnight_crossing_true():
    """schemas.py line 50: 23:00–01:00, 23:30 está contido."""
    p = Period(
        type='class_period', period_number=1, start=time(23, 0), end=time(1, 0)
    )
    assert p.contains(time(23, 30)) is True


def test_period_contains_midnight_crossing_early():
    """schemas.py line 50: 23:00–01:00, 00:30 está contido."""
    p = Period(
        type='class_period', period_number=1, start=time(23, 0), end=time(1, 0)
    )
    assert p.contains(time(0, 30)) is True


def test_period_contains_midnight_crossing_outside():
    """schemas.py line 50: 23:00–01:00, 02:00 NÃO está contido."""
    p = Period(
        type='class_period', period_number=1, start=time(23, 0), end=time(1, 0)
    )
    assert p.contains(time(2, 0)) is False


# ===========================================================================
# GET /schedules/periods
# ===========================================================================


async def test_list_periods_authenticated(client, session):
    """GET /schedules/periods → qualquer logado pode ver."""
    user = await _make_user(session)
    resp = client.get('/schedules/periods', headers=_auth(user))
    assert resp.status_code == HTTPStatus.OK
    assert 'periods' in resp.json()


async def test_list_periods_unauthenticated(client):
    """GET /schedules/periods sem token → 401."""
    resp = client.get('/schedules/periods')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# GET /schedules/classroom/{id} — _check_classroom_access (lines 89-96)
# ===========================================================================


async def test_classroom_access_guardian_with_student_in_class(
    client, guardian, classroom
):
    """lines 89-94: guardian com filho na turma → 200 (bug fix: selectinload)."""
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(guardian)
    )
    assert resp.status_code == HTTPStatus.OK


async def test_classroom_access_guardian_without_student_in_class(
    client, session, classroom_b
):
    """lines 89-93: guardian sem filhos na turma → 403."""
    guardian_no_kids = await _make_user(session, role=UserRole.GUARDIAN)
    resp = client.get(
        f'/schedules/classroom/{classroom_b.id}',
        headers=_auth(guardian_no_kids),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_classroom_access_student_own_class(client, session, classroom):
    """Aluno vê a grade da própria turma → 200."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(stud)
    )
    assert resp.status_code == HTTPStatus.OK


async def test_classroom_access_student_other_class_forbidden(
    client, session, classroom, classroom_b
):
    """Aluno não vê a grade de outra turma → 403."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    resp = client.get(
        f'/schedules/classroom/{classroom_b.id}', headers=_auth(stud)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_classroom_access_no_schedule_permission(client, session):
    """line 96: aluno sem classroom_id tenta acessar turma → 403."""
    orphan = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=None
    )
    c = Classroom(name='TurmaOrfa_sched')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    resp = client.get(f'/schedules/classroom/{c.id}', headers=_auth(orphan))
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_classroom_access_coordinator(client, coordinator, classroom, slot):
    """Coordenador vê qualquer turma → 200."""
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1


async def test_classroom_access_porter_allowed(client, session, classroom):
    """Porteiro tem SCHEDULES_VIEW_ALL → 200."""
    porter = await _make_user(session, role=UserRole.PORTER)
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(porter)
    )
    assert resp.status_code == HTTPStatus.OK


# ===========================================================================
# GET /schedules/classroom/{id} → lista slots (lines 176-178)
# ===========================================================================


async def test_list_classroom_schedule_returns_slots(
    client, coordinator, slot, classroom
):
    """lines 176-178: retorna lista de slots da turma."""
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1
    assert resp.json()['slots'][0]['id'] == slot.id


# ===========================================================================
# GET /schedules/teacher/{id} (lines 209-211)
# ===========================================================================


async def test_list_teacher_schedule_own(client, teacher, slot):
    """Professor vê a própria grade."""
    resp = client.get(
        f'/schedules/teacher/{teacher.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1


async def test_list_teacher_schedule_other_teacher_forbidden(
    client, other_teacher, teacher, slot
):
    """Professor não vê grade de outro professor → 403."""
    resp = client.get(
        f'/schedules/teacher/{teacher.id}', headers=_auth(other_teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_list_teacher_schedule_coordinator(
    client, coordinator, teacher, slot
):
    """lines 209-211: coordenador vê grade de qualquer professor."""
    resp = client.get(
        f'/schedules/teacher/{teacher.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1


async def test_list_teacher_schedule_student_forbidden(
    client, session, teacher, classroom, slot
):
    """Aluno não pode ver grade de professor pelo id → 403."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    resp = client.get(f'/schedules/teacher/{teacher.id}', headers=_auth(stud))
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# GET /schedules/current-teacher/{classroom_id}
# ===========================================================================


async def test_get_current_teacher_not_found(client, coordinator, classroom):
    """GET /schedules/current-teacher/{id} sem slot → 404."""
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = None
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(coordinator),
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_get_current_teacher_coordinator(
    client, coordinator, classroom, teacher, slot
):
    """Coordenador consulta professor atual da turma."""
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = teacher
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(coordinator),
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == teacher.id


async def test_get_current_teacher_student_own_class(
    client, session, classroom, teacher, slot
):
    """Aluno consulta professor da própria turma."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = teacher
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(stud),
        )
    assert resp.status_code == HTTPStatus.OK


async def test_get_current_teacher_student_other_class_forbidden(
    client, session, classroom, classroom_b
):
    """Aluno não pode consultar professor de outra turma → 403."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    resp = client.get(
        f'/schedules/current-teacher/{classroom_b.id}',
        headers=_auth(stud),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# POST /schedules/slots (lines 279-288)
# ===========================================================================


async def test_create_slot_success(client, coordinator, classroom, teacher):
    """lines 279-288: POST /slots → 201 criado."""
    resp = client.post(
        '/schedules/slots',
        json={
            'type': 'class_period',
            'title': 'Física',
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'weekday': Weekday.TUESDAY,
            'period_number': 2,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['title'] == 'Física'


async def test_create_slot_conflict_409(client, coordinator, slot):
    """lines 279-288: POST /slots com duplicado → 409."""
    resp = client.post(
        '/schedules/slots',
        json={
            'type': slot.type,
            'title': slot.title,
            'classroom_id': slot.classroom_id,
            'teacher_id': slot.teacher_id,
            'weekday': slot.weekday,
            'period_number': slot.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert 'already exists' in resp.json()['detail']


async def test_create_slot_student_forbidden(client, session, classroom):
    """Aluno não pode criar slot → 403."""
    stud = await _make_user(session, role=UserRole.STUDENT)
    resp = client.post(
        '/schedules/slots',
        json={
            'type': 'class_period',
            'title': 'X',
            'classroom_id': classroom.id,
            'teacher_id': None,
            'weekday': Weekday.MONDAY,
            'period_number': 1,
        },
        headers=_auth(stud),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# _get_slot_or_404 (lines 119-121)
# ===========================================================================


async def test_get_slot_404(client, coordinator):
    """lines 119-121: slot não encontrado → 404."""
    resp = client.put(
        '/schedules/slots/99999',
        json={
            'type': 'class_period',
            'title': 'X',
            'classroom_id': 1,
            'teacher_id': None,
            'weekday': Weekday.MONDAY,
            'period_number': 1,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'ScheduleSlot not found'


async def test_delete_slot_404(client, coordinator):
    """lines 119-121: DELETE slot inexistente → 404."""
    resp = client.delete('/schedules/slots/99999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND


# ===========================================================================
# PUT /schedules/slots/{id} (lines 311-330)
# ===========================================================================


async def test_update_slot_success(client, coordinator, slot, classroom, teacher):
    """lines 311-330: PUT /slots/{id} → atualiza com sucesso."""
    resp = client.put(
        f'/schedules/slots/{slot.id}',
        json={
            'type': 'class_period',
            'title': 'Física Atualizada',
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'weekday': Weekday.WEDNESDAY,
            'period_number': 3,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Física Atualizada'


async def test_update_slot_conflict_409(client, session, coordinator, classroom, teacher):
    """lines 311-330: PUT /slots/{id} → conflito com outro slot → 409."""
    s1 = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Slot A',
        weekday=Weekday.MONDAY,
        period_number=7,
    )
    s2 = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Slot B',
        weekday=Weekday.TUESDAY,
        period_number=8,
    )
    session.add_all([s1, s2])
    await session.commit()
    await session.refresh(s1)
    await session.refresh(s2)

    resp = client.put(
        f'/schedules/slots/{s1.id}',
        json={
            'type': s2.type,
            'title': s2.title,
            'classroom_id': s2.classroom_id,
            'teacher_id': s2.teacher_id,
            'weekday': s2.weekday,
            'period_number': s2.period_number,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


# ===========================================================================
# DELETE /schedules/slots/{id} (lines 352-355)
# ===========================================================================


async def test_delete_slot_success(client, coordinator, slot):
    """lines 352-355: DELETE /slots/{id} → 200 com slot deletado."""
    resp = client.delete(
        f'/schedules/slots/{slot.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == slot.id


# ===========================================================================
# _get_override_or_404 (lines 128-130)
# ===========================================================================


async def test_get_override_404(client, coordinator):
    """lines 128-130: override não encontrado → 404."""
    resp = client.delete(
        '/schedules/overrides/99999', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'ScheduleOverride not found'


# ===========================================================================
# GET /schedules/overrides (lines 384-402)
# ===========================================================================


async def test_list_overrides_affects_all(client, coordinator):
    """lines 384-402: override affects_all → classroom_ids=None."""
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Feriado',
            'override_date': '2026-10-12',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    all_overrides = [o for o in resp.json()['overrides'] if o['affects_all']]
    assert len(all_overrides) >= 1
    assert all_overrides[0]['classroom_ids'] is None


async def test_list_overrides_specific_classroom(client, coordinator, classroom):
    """lines 384-402: override específico → classroom_ids preenchido."""
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Evento',
            'override_date': '2026-11-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [classroom.id],
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    specific = [o for o in resp.json()['overrides'] if not o['affects_all']]
    assert len(specific) >= 1
    assert classroom.id in specific[0]['classroom_ids']


# ===========================================================================
# POST /schedules/overrides (lines 432-461)
# ===========================================================================


async def test_create_override_affects_all_success(client, coordinator):
    """lines 432-461: POST /overrides → affects_all=True → 201."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Greve',
            'override_date': '2026-12-01',
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


async def test_create_override_specific_classroom(
    client, coordinator, classroom
):
    """lines 432-461: POST /overrides → affects_all=False com turma."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Simulado',
            'override_date': '2027-01-10',
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


async def test_create_override_affects_false_no_classrooms_400(
    client, coordinator
):
    """lines 432-461: affects_all=False sem turmas → 400."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Erro',
            'override_date': '2027-02-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [],
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


async def test_create_override_porter_forbidden(client, session):
    """Porter não tem SCHEDULES_MANAGE → 403."""
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


# ===========================================================================
# DELETE /schedules/overrides/{id} (lines 485-500)
# ===========================================================================


async def test_delete_override_affects_all(client, coordinator):
    """lines 485-500: DELETE override affects_all → classroom_ids=None."""
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Para deletar',
            'override_date': '2027-03-01',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    oid = r.json()['id']
    resp = client.delete(
        f'/schedules/overrides/{oid}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['classroom_ids'] is None


async def test_delete_override_specific_classroom(
    client, coordinator, classroom
):
    """lines 485-500: DELETE override específico → classroom_ids preenchido."""
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Para deletar específico',
            'override_date': '2027-04-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [classroom.id],
        },
        headers=_auth(coordinator),
    )
    oid = r.json()['id']
    resp = client.delete(
        f'/schedules/overrides/{oid}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert classroom.id in resp.json()['classroom_ids']
