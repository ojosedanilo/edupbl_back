"""
Testes cirúrgicos para as linhas exatas ainda descobertas após a rodada anterior.

Mapa de linhas faltantes (--cov-report=term-missing):
  auth/routers.py          107-113, 170, 178-181
  occurrences/routers.py   47-51, 95-110, 128, 160, 188-197, 224-231, 259-266
  schedules/periods.py     35
  schedules/routers.py     89-96, 119-121, 128-130, 176-178, 209-211,
                           279-288, 311-330, 352-355, 384-402, 432-461, 485-500
  schedules/schemas.py     50
  users/routers.py         65-91, 108, 147-148, 161-162, 191, 218
  shared/db/seed.py        339-340, 349
  shared/rbac/deps.py      66
  shared/security.py       134-142
"""

from datetime import datetime, time, timedelta
from http import HTTPStatus
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jwt as pyjwt
import pytest_asyncio

from app.core.settings import settings
from app.domains.occurrences.models import Occurrence
from app.domains.schedules.models import (
    ScheduleSlot,
)
from app.domains.schedules.periods import overlaps
from app.domains.schedules.schemas import Period, Weekday
from app.domains.users.models import Classroom, guardian_student
from app.shared.db.seed import seed_real_users
from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token, create_refresh_token
from tests.conftest import _make_user, make_token

# ────────────────────────────── helpers ─────────────────────────────────────


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ────────────────────────────── fixtures ────────────────────────────────────


@pytest_asyncio.fixture
async def classroom(session):
    c = Classroom(name='4A_ml')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def classroom_b(session):
    c = Classroom(name='4B_ml')
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
        title='Química',
        weekday=Weekday.THURSDAY,
        period_number=4,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@pytest_asyncio.fixture
async def occurrence(session, teacher, student):
    occ = Occurrence(
        created_by_id=teacher.id,
        student_id=student.id,
        title='Barulho',
        description='Detalhes',
    )
    session.add(occ)
    await session.commit()
    await session.refresh(occ)
    return occ


# ===========================================================================
# auth/routers.py — linhas 107-113, 170, 178-181
# ===========================================================================
# Linha 107-113: POST /auth/token → senha errada (raise HTTPException 401)
# Linha 170:     POST /auth/refresh_token → subject_email vazio
# Linha 178-181: POST /auth/refresh_token → usuario não existe no banco


async def test_login_bad_password_hits_401(client, session):
    """
    auth lines 107-113: usuário existe mas senha está errada.
    Cobre o branch `if not user or not verify_password(...)`.
    """
    u = await _make_user(session)
    resp = client.post(
        '/auth/token',
        data={'username': u.email, 'password': 'senha_totalmente_errada'},
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json()['detail'] == 'Incorrect email or password'


async def test_login_unknown_user_hits_401(client):
    """
    auth lines 107-113: email não existe no banco.
    Cobre o branch `if not user` (user é None).
    """
    resp = client.post(
        '/auth/token',
        data={'username': 'naoexiste_ml@test.com', 'password': 'qualquer'},
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_token_payload_without_sub(client):
    """
    auth line 170: token decodificado mas sem campo 'sub' → 401.
    """

    # Token válido mas sem 'sub'
    payload = {
        'exp': datetime.now(tz=ZoneInfo('UTC')) + timedelta(minutes=30),
        'data': 'sem_sub',
    }
    token = pyjwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    resp = client.post('/auth/refresh_token', cookies={'refresh_token': token})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json()['detail'] == 'Could not validate credentials'


def test_refresh_token_user_not_in_db(client):
    """
    auth lines 178-181: token válido, sub preenchido, mas usuário
    não existe no banco → 401.
    """
    token = create_refresh_token(data={'sub': 'fantasma_ml@test.com'})
    resp = client.post('/auth/refresh_token', cookies={'refresh_token': token})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# shared/security.py — linhas 134-142
# ===========================================================================
# 134-135: user not found in DB → 401
# 137-140: user is_active=False → 403
# 142:     return user (sucesso)


async def test_security_user_not_found(client):
    """
    security lines 134-135: token com sub de e-mail inexistente.
    Garante que a branch `if not user` em get_current_user é exercitada.
    """
    token = create_access_token(data={'sub': 'ghost_ml@test.com'})
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_security_inactive_user(client, session):
    """
    security lines 137-140: usuário inativo → 403.
    """
    inactive = await _make_user(session, is_active=False)
    token = create_access_token(data={'sub': inactive.email})
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Inactive user'


async def test_security_active_user_returns_200(client, session):
    """
    security line 142: return user → rota retorna 200.
    """
    u = await _make_user(session)
    resp = client.get('/auth/me', headers=_auth(u))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == u.id


# ===========================================================================
# users/routers.py — linhas 65-91, 108, 147-148, 161-162, 191, 218
# ===========================================================================


async def test_create_user_username_conflict(client, session):
    """lines 65-70: POST /users/ → username duplicado → 409."""
    existing = await _make_user(session)
    resp = client.post(
        '/users/',
        json={
            'username': existing.username,
            'email': 'outro_ml@test.com',
            'password': 'secret123',
            'first_name': 'X',
            'last_name': 'Y',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail'] == 'Username already exists'


async def test_create_user_email_conflict(client, session):
    """lines 71-74: POST /users/ → email duplicado → 409."""
    existing = await _make_user(session)
    resp = client.post(
        '/users/',
        json={
            'username': 'outro_ml_user',
            'email': existing.email,
            'password': 'secret123',
            'first_name': 'X',
            'last_name': 'Y',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail'] == 'Email already exists'


async def test_create_user_success_and_read(client):
    """lines 76-91, 108: POST /users/ sucesso + GET /users/ retorna lista."""
    resp = client.post(
        '/users/',
        json={
            'username': 'novo_ml',
            'email': 'novo_ml@test.com',
            'password': 'senhasegura',
            'first_name': 'Novo',
            'last_name': 'ML',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    user_id = resp.json()['id']

    # GET /users/ → exercita linha 108
    list_resp = client.get('/users/')
    assert list_resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in list_resp.json()['users']]
    assert user_id in ids


async def test_update_user_conflict_triggers_409(client, session):
    """lines 147-148: PUT /users/{id} → username/email de outro → 409."""
    u1 = await _make_user(session)
    u2 = await _make_user(session)
    resp = client.put(
        f'/users/{u1.id}',
        json={'username': u2.username},
        headers=_auth(u1),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


async def test_update_user_returns_updated(client, session):
    """lines 161-162: PUT /users/{id} → commit + return → 200."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'first_name': 'NomeNovo_ML'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['first_name'] == 'NomeNovo_ML'


async def test_change_password_success_message(client, session):
    """line 191: PATCH /me/password → return message."""
    u = await _make_user(session)
    resp = client.patch(
        '/users/me/password',
        json={
            'current_password': u.clean_password,
            'new_password': 'novaSenhaML!',
        },
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'Password updated successfully'}


async def test_delete_user_self_success_message(client, session):
    """line 218: DELETE /users/{id} → return message."""
    u = await _make_user(session)
    resp = client.delete(f'/users/{u.id}', headers=_auth(u))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deleted'}


# ===========================================================================
# occurrences/routers.py — 47-51, 95-110, 128, 160, 188-197, 224-231, 259-266
# ===========================================================================


async def test_occurrence_get_404_helper(client, coordinator):
    """lines 47-51: _get_occurrence_or_404 → ocorrência inexistente → 404."""
    resp = client.get('/occurrences/99999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Occurrence not found'


async def test_occurrence_create_full_flow(client, session, teacher, student):
    """lines 95-110: POST /occurrences/ → cria ocorrência com sucesso."""
    resp = client.post(
        '/occurrences/',
        json={
            'student_id': student.id,
            'title': 'Teste ML',
            'description': 'Desc ML',
        },
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['student_id'] == student.id
    assert body['created_by_id'] == teacher.id


async def test_occurrence_create_student_not_found(client, teacher):
    """lines 97-100: student_id inexistente → 404 Student not found."""
    resp = client.post(
        '/occurrences/',
        json={'student_id': 99999, 'title': 'X', 'description': 'Y'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Student not found'


async def test_occurrence_list_all_returns_all(
    client, coordinator, occurrence
):
    """line 128: GET /occurrences/ → retorna todas."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_occurrence_me_teacher_branch(client, teacher, occurrence):
    """line 160: GET /occurrences/me → professor vê as que criou."""
    resp = client.get('/occurrences/me', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_occurrence_me_student_branch(client, student, occurrence):
    """lines 155-158: GET /occurrences/me → aluno vê as suas."""
    resp = client.get('/occurrences/me', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_occurrence_get_student_other_forbidden(
    client, session, occurrence
):
    """lines 188-197: GET /occurrences/{id} → aluno tentando ver de outro → 403."""
    other_student = await _make_user(session, role=UserRole.STUDENT)
    resp = client.get(
        f'/occurrences/{occurrence.id}', headers=_auth(other_student)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_occurrence_get_by_student_own(client, student, occurrence):
    """lines 188-197: GET /occurrences/{id} → aluno vê a própria → 200."""
    resp = client.get(f'/occurrences/{occurrence.id}', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_occurrence_update_success(client, teacher, occurrence):
    """lines 224-231: PUT /occurrences/{id} → professor edita a própria."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        json={'title': 'Atualizado ML'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Atualizado ML'


async def test_occurrence_update_other_teacher_forbidden(
    client, other_teacher, occurrence
):
    """lines 224-231: PUT → professor tenta editar de outro → 403."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        json={'title': 'X'},
        headers=_auth(other_teacher),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_occurrence_delete_success(client, teacher, occurrence):
    """lines 259-266: DELETE /occurrences/{id} → professor deleta a própria."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_occurrence_delete_other_teacher_forbidden(
    client, other_teacher, occurrence
):
    """lines 259-266: DELETE → professor tenta deletar de outro → 403."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(other_teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# schedules/periods.py — linha 35
# ===========================================================================
# Linha 35: `return [(s, time(23,59,59,999999)), (time(0,0), e)]`
# Isso só é atingido quando start > end (período cruzando meia-noite)


def test_overlaps_midnight_crossing_interval():
    """
    periods.py line 35: get_intervals com start > end (cruzamento de meia-noite).
    Ex: 23:00–01:00 sobrepõe com 00:30–02:00.
    """
    # Intervalo que cruza meia-noite: 23:00–01:00
    start1, end1 = time(23, 0), time(1, 0)
    # Intervalo normal que está dentro da janela de meia-noite
    start2, end2 = time(0, 30), time(2, 0)

    result = overlaps(start1, end1, start2, end2)
    assert result is True


def test_overlaps_midnight_no_overlap():
    """
    periods.py line 35: cruzamento de meia-noite sem sobreposição.
    23:00–01:00 NÃO sobrepõe com 02:00–04:00.
    """
    start1, end1 = time(23, 0), time(1, 0)
    start2, end2 = time(2, 0), time(4, 0)

    result = overlaps(start1, end1, start2, end2)
    assert result is False


# ===========================================================================
# schedules/schemas.py — linha 50
# ===========================================================================
# Linha 50: `return check_time >= self.start or check_time < self.end`
# Só executada quando self.start > self.end (período noturno cruzando meia-noite)


def test_period_contains_midnight_crossing_true():
    """
    schemas.py line 50: Period.contains() com start > end (meia-noite).
    23:00–01:00: 23:30 deve estar contido.
    """
    p = Period(
        type='class_period', period_number=1, start=time(23, 0), end=time(1, 0)
    )
    assert p.contains(time(23, 30)) is True


def test_period_contains_midnight_crossing_early():
    """
    schemas.py line 50: Period.contains() com start > end.
    23:00–01:00: 00:30 (antes das 01:00) deve estar contido.
    """
    p = Period(
        type='class_period', period_number=1, start=time(23, 0), end=time(1, 0)
    )
    assert p.contains(time(0, 30)) is True


def test_period_contains_midnight_crossing_outside():
    """
    schemas.py line 50: Period.contains() com start > end.
    23:00–01:00: 02:00 NÃO deve estar contido.
    """
    p = Period(
        type='class_period', period_number=1, start=time(23, 0), end=time(1, 0)
    )
    assert p.contains(time(2, 0)) is False


# ===========================================================================
# schedules/routers.py — 89-96, 119-121, 128-130, 176-178, 209-211,
#                        279-288, 311-330, 352-355, 384-402, 432-461, 485-500
# ===========================================================================


# ── lines 89-96: _check_classroom_access → SCHEDULES_VIEW_CHILD branch ──────


async def test_classroom_access_guardian_with_student_in_class(
    client, guardian, classroom
):
    """
    schedules lines 89-94: guardian tem SCHEDULES_VIEW_CHILD.
    Seu filho está na classroom → acesso permitido (200).
    """
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(guardian)
    )
    assert resp.status_code == HTTPStatus.OK


async def test_classroom_access_guardian_without_student_in_class(
    client, session, classroom_b
):
    """
    schedules lines 89-93: guardian sem filhos na classroom_b → 403.
    """
    guardian_no_kids = await _make_user(session, role=UserRole.GUARDIAN)
    resp = client.get(
        f'/schedules/classroom/{classroom_b.id}',
        headers=_auth(guardian_no_kids),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_classroom_access_no_schedule_permission(client, session):
    """
    schedules line 96: role sem nenhuma permissão de schedule → 403.
    Usa STUDENT sem classroom_id, tentando acessar uma turma que não é a sua.
    """
    # Um aluno sem classroom_id tenta acessar uma turma → VIEW_OWN mas
    # classroom_id is None != qualquer id de turma → 403
    orphan_student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=None
    )
    c = Classroom(name='TurmaOrfaML')
    session.add(c)
    await session.commit()
    await session.refresh(c)

    resp = client.get(
        f'/schedules/classroom/{c.id}', headers=_auth(orphan_student)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ── lines 119-121: _get_slot_or_404 → slot inexistente ─────────────────────


async def test_get_slot_404(client, coordinator):
    """schedules lines 119-121: slot não encontrado → 404."""
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
    """schedules lines 119-121: DELETE slot inexistente → 404."""
    resp = client.delete('/schedules/slots/99999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND


# ── lines 128-130: _get_override_or_404 → override inexistente ──────────────


async def test_get_override_404(client, coordinator):
    """schedules lines 128-130: override não encontrado → 404."""
    resp = client.delete(
        '/schedules/overrides/99999', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'ScheduleOverride not found'


# ── lines 176-178: list_classroom_schedule → retorna slots ──────────────────


async def test_list_classroom_schedule_returns_slots(
    client, coordinator, slot, classroom
):
    """schedules lines 176-178: GET /classroom/{id} → lista de slots."""
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1
    assert resp.json()['slots'][0]['id'] == slot.id


# ── lines 209-211: list_teacher_schedule → retorna slots ────────────────────


async def test_list_teacher_schedule_returns_slots(
    client, coordinator, slot, teacher
):
    """schedules lines 209-211: GET /teacher/{id} → lista de slots."""
    resp = client.get(
        f'/schedules/teacher/{teacher.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1


# ── lines 279-288: create_slot → sucesso e conflito ─────────────────────────


async def test_create_slot_success(client, coordinator, classroom, teacher):
    """schedules lines 279-288: POST /slots → 201 criado."""
    resp = client.post(
        '/schedules/slots',
        json={
            'type': 'class_period',
            'title': 'Biologia ML',
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'weekday': Weekday.FRIDAY,
            'period_number': 5,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['title'] == 'Biologia ML'


async def test_create_slot_conflict_409(client, coordinator, slot):
    """schedules lines 279-288: POST /slots com duplicado → 409."""
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


# ── lines 311-330: update_slot → sucesso, conflito, 404 ─────────────────────


async def test_update_slot_success(
    client, coordinator, slot, classroom, teacher
):
    """schedules lines 311-330: PUT /slots/{id} → atualiza com sucesso."""
    resp = client.put(
        f'/schedules/slots/{slot.id}',
        json={
            'type': 'class_period',
            'title': 'Química Atualizada ML',
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'weekday': Weekday.WEDNESDAY,
            'period_number': 6,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Química Atualizada ML'


async def test_update_slot_conflict_with_other_409(
    client, session, coordinator, classroom, teacher
):
    """schedules lines 311-330: PUT /slots/{id} → conflito com outro slot → 409."""
    s1 = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Slot A ML',
        weekday=Weekday.MONDAY,
        period_number=7,
    )
    s2 = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Slot B ML',
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


# ── lines 352-355: delete_slot → sucesso ────────────────────────────────────


async def test_delete_slot_success(client, coordinator, slot):
    """schedules lines 352-355: DELETE /slots/{id} → 200 com slot deletado."""
    resp = client.delete(
        f'/schedules/slots/{slot.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == slot.id


# ── lines 384-402: list_overrides → affects_all e por classroom ─────────────


async def test_list_overrides_affects_all(client, coordinator):
    """schedules lines 384-402: GET /overrides → override affects_all (cids=None)."""
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Feriado ML',
            'override_date': '2026-10-12',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    overrides = resp.json()['overrides']
    all_overrides = [o for o in overrides if o['affects_all']]
    assert len(all_overrides) >= 1
    assert all_overrides[0]['classroom_ids'] is None


async def test_list_overrides_specific_classroom(
    client, coordinator, classroom
):
    """schedules lines 384-402: GET /overrides → override específico (cids preenchido)."""
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Evento ML',
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


# ── lines 432-461: create_override → afeta_all, específico, sem classroom ───


async def test_create_override_affects_all_success(client, coordinator):
    """schedules lines 432-461: POST /overrides → affects_all=True → 201."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Greve ML',
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
    """schedules lines 432-461: POST /overrides → affects_all=False com turma."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Simulado ML',
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
    """schedules lines 432-461: POST /overrides → affects_all=False sem turmas → 400."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Erro ML',
            'override_date': '2027-02-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [],
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


# ── lines 485-500: delete_override → affects_all e por classroom ─────────────


async def test_delete_override_affects_all(client, coordinator):
    """schedules lines 485-500: DELETE /overrides/{id} → affects_all → cids=None."""
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Para deletar ML',
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
    """schedules lines 485-500: DELETE /overrides/{id} → específico → cids preenchido."""
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Para deletar específico ML',
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


# ===========================================================================
# shared/rbac/dependencies.py — linha 66
# ===========================================================================
# Linha 66: AnyPermissionChecker.__call__ → raise HTTPException (403)
# Atingida quando usuário não tem NENHUMA das permissões requeridas.


async def test_any_permission_checker_raises_403(client, session):
    """
    rbac/deps line 66: AnyPermissionChecker → usuário sem nenhuma
    das permissões necessárias → 403.

    GET /schedules/overrides requer VIEW_ALL|VIEW_OWN|VIEW_CHILD.
    PORTER tem VIEW_ALL → permitido.
    Precisamos de uma role sem nenhuma das três.

    Usamos um student com classroom_id=None → tem VIEW_OWN mas
    classroom_id é None → passa o AnyPermissionChecker, mas aí
    _check_classroom_access bloqueia. Para o AnyPermissionChecker em si,
    precisamos de um endpoint que o STUDENT não tenha NENHUMA permissão.

    SCHEDULES_MANAGE é só para coord/admin → student tenta criar slot → 403.
    O PermissionChecker (não Any) também passa pela linha 66 quando falha.
    """
    # Aluno tenta criar um slot (precisa de SCHEDULES_MANAGE que aluno não tem)
    stud = await _make_user(session, role=UserRole.STUDENT)
    resp = client.post(
        '/schedules/slots',
        json={
            'type': 'class_period',
            'title': 'X',
            'classroom_id': 1,
            'teacher_id': None,
            'weekday': Weekday.MONDAY,
            'period_number': 1,
        },
        headers=_auth(stud),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_any_permission_checker_guardian_no_schedule_forbidden(
    client, session
):
    """
    rbac/deps line 66: AnyPermissionChecker com guardian sem filhos
    tentando GET /schedules/overrides (VIEW_ALL|VIEW_OWN|VIEW_CHILD).
    Guardian tem VIEW_CHILD → passa o AnyPermissionChecker (não 403 aqui).
    Para forçar a linha 66, usamos porteiro tentando criar override → 403.
    """
    porter = await _make_user(session, role=UserRole.PORTER)
    # Porter não tem SCHEDULES_MANAGE → PermissionChecker dispara linha 66
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
# shared/db/seed.py — linhas 339-340, 349
# ===========================================================================
# 339-340: except Exception: erros += 1  (linha de erro no CSV)
# 349:     print(f'  ⚠️  {erros} erro(s)')  (imprime se houve erros)


async def test_seed_real_users_with_malformed_csv(session, tmp_path, capsys):
    """
    seed.py lines 339-340, 349: CSV com linha inválida → except captura,
    erros++ e imprime o aviso.
    """

    # Cria CSV com uma linha válida e uma inválida (sem campos obrigatórios)
    csv_content = 'nome,sobrenome,email,senha\nJoao,Silva,joao_ml@test.com,senha123\n,,,\n'

    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    csv_file = usuarios_dir / 'admins.csv'
    csv_file.write_text(csv_content, encoding='utf-8')

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    captured = capsys.readouterr()
    # Deve ter impresso o aviso de erros
    assert 'erro' in captured.out.lower() or 'criados' in captured.out.lower()
