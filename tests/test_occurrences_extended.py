"""
Testes de occurrences/routers.py — cobertura completa.

Cobre:
  occurrences/routers.py  47-51, 95-110, 128, 160, 188-197, 224-231, 259-266
"""

from http import HTTPStatus

import pytest_asyncio

from app.domains.occurrences.models import Occurrence
from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ===========================================================================
# _get_occurrence_or_404
# ===========================================================================


async def test_occurrence_get_404(client, coordinator):
    """lines 47-51: ocorrência inexistente → 404."""
    resp = client.get('/occurrences/99999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Occurrence not found'


# ===========================================================================
# POST /occurrences/
# ===========================================================================


async def test_create_occurrence_student_not_found(client, teacher):
    """lines 97-100: student_id inexistente → 404 Student not found."""
    resp = client.post(
        '/occurrences/',
        json={'student_id': 9999, 'title': 'Teste', 'description': 'Desc'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Student not found'


async def test_create_occurrence_success(client, teacher, student):
    """lines 95-110: POST /occurrences/ → cria ocorrência com sucesso."""
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
    assert body['student_id'] == student.id


# ===========================================================================
# GET /occurrences/
# ===========================================================================


async def test_list_all_occurrences_coordinator(client, coordinator, occurrence):
    """line 128: GET /occurrences/ → coordenador vê todas."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_list_all_occurrences_teacher_forbidden(client, teacher, occurrence):
    """GET /occurrences/ → professor não tem acesso → 403."""
    resp = client.get('/occurrences/', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# GET /occurrences/me
# ===========================================================================


async def test_list_my_occurrences_as_student(client, student, occurrence):
    """GET /occurrences/me → aluno vê as próprias ocorrências."""
    resp = client.get('/occurrences/me', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


async def test_occurrence_me_teacher_branch(client, teacher, occurrence):
    """line 160: GET /occurrences/me → professor vê as que criou."""
    resp = client.get('/occurrences/me', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


# ===========================================================================
# GET /occurrences/{id}
# ===========================================================================


async def test_get_occurrence_by_id_coordinator(client, coordinator, occurrence):
    """Coordenador pode ver qualquer ocorrência."""
    resp = client.get(
        f'/occurrences/{occurrence.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_get_occurrence_by_id_student_own(client, student, occurrence):
    """lines 188-197: aluno vê a própria ocorrência → 200."""
    resp = client.get(f'/occurrences/{occurrence.id}', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK


async def test_get_occurrence_by_id_student_other_forbidden(
    client, session, occurrence
):
    """lines 188-197: aluno não pode ver ocorrência de outro aluno → 403."""
    other_student = await _make_user(session, role=UserRole.STUDENT)
    resp = client.get(
        f'/occurrences/{occurrence.id}', headers=_auth(other_student)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# PUT /occurrences/{id}
# ===========================================================================


async def test_update_occurrence_success(client, teacher, occurrence):
    """lines 224-231: professor edita a própria ocorrência."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        json={'title': 'Atualizado'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Atualizado'


async def test_update_occurrence_not_own_teacher(client, other_teacher, occurrence):
    """lines 224-231: professor não pode editar ocorrência de outro → 403."""
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


# ===========================================================================
# DELETE /occurrences/{id}
# ===========================================================================


async def test_delete_occurrence_success(client, teacher, occurrence):
    """lines 259-266: professor deleta a própria → 200."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_delete_occurrence_not_own_teacher(client, other_teacher, occurrence):
    """lines 259-266: professor não pode deletar ocorrência de outro → 403."""
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
