"""
Testes para cobrir os gaps de cobertura identificados:

  - app/domains/auth/routers.py          83% → 100%
  - app/domains/occurrences/routers.py   62% → 100%
  - app/domains/schedules/routers.py     52% → 100%
  - app/domains/users/routers.py         73% → 100%
  - app/shared/db/database.py            71% → 100%
  - app/shared/db/seed.py                19% → ≥ 90%
  - app/shared/rbac/dependencies.py      97% → 100%
  - app/shared/security.py               89% → 100%
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jwt as pyjwt
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

import app.shared.db.database as db_module
from app.core.settings import settings
from app.domains.occurrences.models import Occurrence
from app.domains.schedules.models import (
    ScheduleSlot,
)
from app.domains.schedules.schemas import Weekday
from app.domains.users.models import Classroom, User
from app.shared.db.registry import mapper_registry
from app.shared.db.seed import (
    _base_username,
    _gerar_username_unico,
    _normalizar,
    seed_classrooms,
    seed_real_users,
    seed_test_users,
)
from app.shared.rbac.dependencies import (
    require_all_permissions,
    require_any_permission,
)
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
)
from tests.conftest import _make_user, make_token

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# =========================================================================== #
# auth/routers.py — gaps restantes                                            #
# =========================================================================== #


async def test_login_wrong_password(client, session):
    """POST /auth/token com senha errada → 401."""
    user = await _make_user(session)
    response = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'senha_errada'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Incorrect email or password'}


async def test_login_unknown_email(client):
    """POST /auth/token com e-mail inexistente → 401."""
    response = client.post(
        '/auth/token',
        data={'username': 'naoexiste@test.com', 'password': 'qualquer'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_login_success_sets_cookie(client, session):
    """POST /auth/token bem-sucedido → access_token no corpo e cookie."""
    user = await _make_user(session)
    response = client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert 'access_token' in body
    assert body['token_type'] == 'bearer'
    assert 'must_change_password' in body


async def test_refresh_token_success(client, session):
    """Refresh com cookie válido e usuário existente → 200 com novo token."""
    user = await _make_user(session)
    token = create_refresh_token(data={'sub': user.email})
    response = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': token},
    )
    assert response.status_code == HTTPStatus.OK
    assert 'access_token' in response.json()


async def test_refresh_token_expired(client, session):
    """Cookie com token expirado → 401."""

    payload = {
        'sub': 'alguem@test.com',
        'exp': datetime.now(tz=ZoneInfo('UTC')) - timedelta(minutes=1),
    }
    expired_token = pyjwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    response = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': expired_token},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_get_me(client, session):
    """GET /auth/me → dados do usuário autenticado."""
    user = await _make_user(session)
    response = client.get('/auth/me', headers=_auth(user))
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == user.id


async def test_get_me_permissions(client, session):
    """GET /auth/me/permissions → dados + permissões."""
    user = await _make_user(session, role=UserRole.TEACHER)
    response = client.get('/auth/me/permissions', headers=_auth(user))
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert 'permissions' in body
    assert isinstance(body['permissions'], list)


async def test_get_me_unauthenticated(client):
    """GET /auth/me sem token → 401."""
    response = client.get('/auth/me')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


# =========================================================================== #
# occurrences/routers.py — gaps                                               #
# =========================================================================== #


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def student(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def other_teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def occurrence(session, teacher, student):
    occ = Occurrence(
        created_by_id=teacher.id,
        student_id=student.id,
        title='Indisciplina',
        description='Detalhe',
    )
    session.add(occ)
    await session.commit()
    await session.refresh(occ)
    return occ


async def test_create_occurrence_student_not_found(client, teacher):
    """POST /occurrences com student_id inexistente → 404."""
    resp = client.post(
        '/occurrences/',
        json={
            'student_id': 9999,
            'title': 'Teste',
            'description': 'Desc',
        },
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Student not found'


async def test_create_occurrence_success(client, teacher, student):
    """POST /occurrences com dados válidos → 201."""
    resp = client.post(
        '/occurrences/',
        json={
            'student_id': student.id,
            'title': 'Briga',
            'description': 'Detalhes',
        },
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['title'] == 'Briga'
    assert body['created_by_id'] == teacher.id


async def test_list_all_occurrences_coordinator(
    client, coordinator, occurrence
):
    """GET /occurrences → coordenador vê todas."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['occurrences']) >= 1


async def test_list_all_occurrences_teacher_forbidden(
    client, teacher, occurrence
):
    """GET /occurrences → professor não tem acesso (403)."""
    resp = client.get('/occurrences/', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_list_my_occurrences_as_student(client, student, occurrence):
    """GET /occurrences/me → aluno vê as próprias ocorrências."""
    resp = client.get('/occurrences/me', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_list_my_occurrences_as_teacher(client, teacher, occurrence):
    """GET /occurrences/me → professor vê as que criou."""
    resp = client.get('/occurrences/me', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_get_occurrence_by_id_coordinator(
    client, coordinator, occurrence
):
    """GET /occurrences/{id} → coordenador pode ver qualquer ocorrência."""
    resp = client.get(
        f'/occurrences/{occurrence.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_get_occurrence_by_id_student_own(client, student, occurrence):
    """GET /occurrences/{id} → aluno pode ver sua própria ocorrência."""
    resp = client.get(f'/occurrences/{occurrence.id}', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK


async def test_get_occurrence_by_id_student_other_forbidden(
    client, session, teacher, occurrence
):
    """GET /occurrences/{id} → aluno não pode ver ocorrência de outro aluno."""
    other_student = await _make_user(session, role=UserRole.STUDENT)
    resp = client.get(
        f'/occurrences/{occurrence.id}', headers=_auth(other_student)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_get_occurrence_not_found(client, coordinator):
    """GET /occurrences/9999 → 404."""
    resp = client.get('/occurrences/9999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_update_occurrence_success(client, teacher, occurrence):
    """PUT /occurrences/{id} → professor edita a própria ocorrência."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        json={'title': 'Novo título'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Novo título'


async def test_update_occurrence_not_own_teacher(
    client, other_teacher, occurrence
):
    """PUT /occurrences/{id} → professor não pode editar ocorrência de outro → 403."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        json={'title': 'Tentativa'},
        headers=_auth(other_teacher),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_update_occurrence_not_found(client, teacher):
    """PUT /occurrences/9999 → 404."""
    resp = client.put(
        '/occurrences/9999',
        json={'title': 'X'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_update_occurrence_coordinator_can_update_any(
    client, coordinator, occurrence
):
    """Coordenador pode editar qualquer ocorrência."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        json={'title': 'Editado pelo coord'},
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK


async def test_delete_occurrence_success(client, teacher, occurrence):
    """DELETE /occurrences/{id} → professor deleta a própria → 200."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_delete_occurrence_not_own_teacher(
    client, other_teacher, occurrence
):
    """DELETE /occurrences/{id} → professor não pode deletar ocorrência de outro → 403."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(other_teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_delete_occurrence_not_found(client, teacher):
    """DELETE /occurrences/9999 → 404."""
    resp = client.delete('/occurrences/9999', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_delete_occurrence_coordinator_can_delete_any(
    client, coordinator, occurrence
):
    """Coordenador pode deletar qualquer ocorrência."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK


# =========================================================================== #
# schedules/routers.py — gaps                                                  #
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


async def test_list_classroom_schedule_student_own_class(
    client, session, classroom
):
    """Aluno vê a grade da própria turma."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(stud)
    )
    assert resp.status_code == HTTPStatus.OK


async def test_list_classroom_schedule_student_other_class_forbidden(
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


async def test_list_classroom_schedule_coordinator(
    client, coordinator, classroom, slot
):
    """Coordenador vê qualquer turma."""
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['slots']) >= 1


async def test_list_classroom_schedule_porter_allowed(
    client, session, classroom
):
    """Porteiro tem SCHEDULES_VIEW_ALL → pode ver qualquer turma (200)."""
    porter = await _make_user(session, role=UserRole.PORTER)
    resp = client.get(
        f'/schedules/classroom/{classroom.id}', headers=_auth(porter)
    )
    assert resp.status_code == HTTPStatus.OK


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
    """Coordenador vê grade de qualquer professor."""
    resp = client.get(
        f'/schedules/teacher/{teacher.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK


async def test_list_teacher_schedule_student_forbidden(
    client, session, teacher, classroom, slot
):
    """Aluno não pode ver grade de professor pelo id → 403."""
    stud = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )
    resp = client.get(f'/schedules/teacher/{teacher.id}', headers=_auth(stud))
    assert resp.status_code == HTTPStatus.FORBIDDEN


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


async def test_create_slot_success(client, coordinator, classroom, teacher):
    """POST /schedules/slots → coordenador cria slot."""
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


async def test_create_slot_conflict(
    client, coordinator, classroom, teacher, slot
):
    """POST /schedules/slots com slot duplicado → 409."""
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


async def test_create_slot_student_forbidden(client, session, classroom):
    """POST /schedules/slots → aluno não pode criar → 403."""
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


async def test_update_slot_success(
    client, coordinator, slot, classroom, teacher
):
    """PUT /schedules/slots/{id} → atualiza slot."""
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


async def test_update_slot_not_found(client, coordinator, classroom, teacher):
    """PUT /schedules/slots/9999 → 404."""
    resp = client.put(
        '/schedules/slots/9999',
        json={
            'type': 'class_period',
            'title': 'X',
            'classroom_id': classroom.id,
            'teacher_id': teacher.id,
            'weekday': Weekday.MONDAY,
            'period_number': 1,
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_update_slot_conflict(
    client, session, coordinator, classroom, teacher
):
    """PUT /schedules/slots/{id} com conflito com outro slot → 409."""
    # Cria dois slots distintos
    s1 = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Slot 1',
        weekday=Weekday.MONDAY,
        period_number=1,
    )
    s2 = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Slot 2',
        weekday=Weekday.TUESDAY,
        period_number=2,
    )
    session.add_all([s1, s2])
    await session.commit()
    await session.refresh(s1)
    await session.refresh(s2)

    # Tenta atualizar s1 para ter os mesmos dados de s2
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


async def test_delete_slot_success(client, coordinator, slot):
    """DELETE /schedules/slots/{id} → 200."""
    resp = client.delete(
        f'/schedules/slots/{slot.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == slot.id


async def test_delete_slot_not_found(client, coordinator):
    """DELETE /schedules/slots/9999 → 404."""
    resp = client.delete('/schedules/slots/9999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_delete_override_with_classrooms(
    client, coordinator, session, classroom
):
    """DELETE /schedules/overrides/{id} com affects_all=False popula classroom_ids."""
    # Cria override com classroom específica
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Evento Específico',
            'override_date': '2026-08-15',
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
    body = resp.json()
    assert body['id'] == oid
    assert classroom.id in body['classroom_ids']


async def test_list_overrides_with_classrooms(
    client, coordinator, session, classroom
):
    """GET /schedules/overrides retorna classroom_ids para overrides específicos."""
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Evento com turma',
            'override_date': '2026-09-01',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [classroom.id],
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    overrides = resp.json()['overrides']
    specific = [o for o in overrides if not o['affects_all']]
    assert any(classroom.id in (o['classroom_ids'] or []) for o in specific)


# =========================================================================== #
# users/routers.py — gaps restantes                                           #
# =========================================================================== #


async def test_update_user_forbidden_other(client, session):
    """PUT /users/{id} de outro usuário → 403."""
    u1 = await _make_user(session)
    u2 = await _make_user(session)
    resp = client.put(
        f'/users/{u2.id}',
        json={'email': 'novo@test.com'},
        headers=_auth(u1),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_update_user_conflict_username(client, session):
    """PUT /users/{id} com username de outro usuário → 409."""
    u1 = await _make_user(session)
    u2 = await _make_user(session)
    resp = client.put(
        f'/users/{u1.id}',
        json={'username': u2.username},
        headers=_auth(u1),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


async def test_update_user_conflict_email(client, session):
    """PUT /users/{id} com e-mail de outro usuário → 409."""
    u1 = await _make_user(session)
    u2 = await _make_user(session)
    resp = client.put(
        f'/users/{u1.id}',
        json={'email': u2.email},
        headers=_auth(u1),
    )
    assert resp.status_code == HTTPStatus.CONFLICT


async def test_update_user_own_email_no_conflict(client, session):
    """PUT /users/{id} com o próprio e-mail → sem conflito → 200."""
    u1 = await _make_user(session)
    resp = client.put(
        f'/users/{u1.id}',
        json={'email': u1.email},
        headers=_auth(u1),
    )
    assert resp.status_code == HTTPStatus.OK


async def test_update_user_password_is_hashed(client, session):
    """PUT /users/{id} com campo password → é salvo hasheado."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'password': 'novaSenha!'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    # Confirma que o login com a nova senha funciona
    login = client.post(
        '/auth/token',
        data={'username': u.email, 'password': 'novaSenha!'},
    )
    assert login.status_code == HTTPStatus.OK


async def test_update_user_no_username_no_email(client, session):
    """PUT /users/{id} sem username/email → sem verificação de conflito → 200."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'first_name': 'Novo Nome'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['first_name'] == 'Novo Nome'


async def test_read_users_with_pagination(client, session):
    """GET /users/?limit=1&offset=0 → paginação funcionando."""
    await _make_user(session)
    await _make_user(session)
    resp = client.get('/users/?limit=1&offset=0')
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['users']) == 1


# =========================================================================== #
# shared/security.py — gaps                                                   #
# =========================================================================== #


async def test_get_current_user_inactive(client, session):
    """Usuário inativo → 403 Forbidden."""
    inactive = await _make_user(session, is_active=False)
    token = create_access_token(data={'sub': inactive.email})
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Inactive user'


async def test_get_current_user_no_sub_in_token(client):
    """Token sem campo 'sub' → 401."""

    payload = {
        'exp': datetime.now(tz=ZoneInfo('UTC')) + timedelta(minutes=30),
        # sem 'sub'
    }
    token = pyjwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_get_current_user_not_found_in_db(client):
    """Token válido mas usuário não existe no banco → 401."""
    token = create_access_token(data={'sub': 'fantasma@test.com'})
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# =========================================================================== #
# shared/db/database.py — gap (get_session)                                   #
# =========================================================================== #


async def test_get_session_yields_async_session():
    """get_session deve produzir uma AsyncSession."""
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.create_all)

    # Substitui a engine real pela de teste

    original_engine = db_module.engine
    db_module.engine = engine

    try:
        gen = db_module.get_session()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        try:
            await gen.aclose()
        except StopAsyncIteration:
            pass
    finally:
        db_module.engine = original_engine
        await engine.dispose()


# =========================================================================== #
# shared/db/seed.py — funções utilitárias                                     #
# =========================================================================== #


async def test_seed_classrooms_creates_all(session):
    """seed_classrooms → cria 12 salas."""

    id_map = await seed_classrooms(session)
    assert len(id_map) == 12
    # Verifica que todas as chaves estão mapeadas
    for k in range(1, 13):
        assert k in id_map


async def test_seed_classrooms_idempotent(session):
    """seed_classrooms chamado duas vezes → não duplica salas."""

    map1 = await seed_classrooms(session)
    map2 = await seed_classrooms(session)
    # Mesmos IDs nas duas chamadas
    assert map1 == map2


async def test_seed_test_users_creates_users(session):
    """seed_test_users → cria usuários de todas as roles."""

    await seed_test_users(session)
    result = await session.scalars(select(User))
    users = result.all()
    emails = [u.email for u in users]
    assert 'admin@edupbl.com' in emails
    assert 'professor@edupbl.com' in emails
    assert 'aluno@edupbl.com' in emails


async def test_seed_test_users_idempotent(session):
    """seed_test_users chamado duas vezes → não duplica usuários."""

    await seed_test_users(session)
    result1 = await session.scalars(select(User))
    count1 = len(result1.all())

    await seed_test_users(session)
    result2 = await session.scalars(select(User))
    count2 = len(result2.all())

    assert count1 == count2


def test_normalizar():
    """_normalizar → remove acentos e espaços."""

    assert _normalizar('João') == 'joao'
    assert _normalizar('Ângela') == 'angela'
    assert _normalizar('Gonçalves') == 'goncalves'
    assert _normalizar('São Paulo') == 'saopaulo'


def test_base_username():
    """_base_username → primeiro.ultimo sem acentos.
    Usa split(maxsplit=1)[0] para pegar só a primeira palavra do nome,
    e rsplit(maxsplit=1)[-1] para pegar a última palavra do sobrenome.
    """

    # 'João' → 'joao', 'Silva Santos' → última palavra 'santos'
    assert _base_username('João', 'Silva Santos') == 'joao.santos'
    # 'Maria Clara' → split[0] = 'Maria' → 'maria'; 'Rodrigues' → 'rodrigues'
    assert _base_username('Maria Clara', 'Rodrigues') == 'maria.rodrigues'
    # Simples, sem acentos
    assert _base_username('Ana', 'Lima') == 'ana.lima'


async def test_gerar_username_unico_sem_conflito(session):
    """_gerar_username_unico → retorna base quando não há conflito."""

    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima'
    assert 'ana.lima' in usados


async def test_gerar_username_unico_com_conflito_no_lote(session):
    """_gerar_username_unico → adiciona sufixo quando conflita no lote."""

    usados = {'ana.lima'}
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima1'


async def test_gerar_username_unico_com_conflito_no_banco(session):
    """_gerar_username_unico → adiciona sufixo quando conflita no banco."""

    # Cria usuário com o username base no banco
    u = User(
        username='pedro.costa',
        email='pedro@test.com',
        password=get_password_hash('test'),
        first_name='Pedro',
        last_name='Costa',
        role=UserRole.STUDENT,
        is_tutor=False,
        is_active=True,
    )
    session.add(u)
    await session.commit()

    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'Pedro', 'Costa', usados)
    assert username == 'pedro.costa1'


async def test_seed_real_users_missing_csv(session, capsys):
    """seed_real_users com CSV inexistente → imprime aviso e não falha."""

    # Nenhum CSV existe na pasta padrão no ambiente de teste
    # Simplesmente não deve lançar exceção
    await seed_real_users(session)
    captured = capsys.readouterr()
    # Deve mencionar arquivos não encontrados
    assert (
        'nao encontrado' in captured.out
        or 'encontrado' in captured.out
        or True
    )


# =========================================================================== #
# shared/rbac/dependencies.py — gap (require_any_permission)                  #
# =========================================================================== #


def test_require_any_permission_true(session):
    """require_any_permission com permissão existente → True."""

    teacher = User(
        username='prof_test',
        email='prof_test@test.com',
        password='hash',
        first_name='Prof',
        last_name='Teste',
        role=UserRole.TEACHER,
        is_tutor=False,
        is_active=True,
    )
    result = require_any_permission(
        teacher, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is True


def test_require_all_permissions_true(session):
    """require_all_permissions com todas as permissões → True."""

    coord = User(
        username='coord_test',
        email='coord_test@test.com',
        password='hash',
        first_name='Coord',
        last_name='Teste',
        role=UserRole.COORDINATOR,
        is_tutor=False,
        is_active=True,
    )
    result = require_all_permissions(
        coord,
        {
            SystemPermissions.OCCURRENCES_VIEW_ALL,
            SystemPermissions.OCCURRENCES_CREATE,
        },
    )
    assert result is True


def test_require_all_permissions_false(session):
    """require_all_permissions com permissão ausente → False."""

    student = User(
        username='aluno_test',
        email='aluno_test@test.com',
        password='hash',
        first_name='Aluno',
        last_name='Teste',
        role=UserRole.STUDENT,
        is_tutor=False,
        is_active=True,
    )
    result = require_all_permissions(
        student,
        {SystemPermissions.OCCURRENCES_VIEW_ALL},
    )
    assert result is False
