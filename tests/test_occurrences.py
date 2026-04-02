"""
Testes adicionais para cobertura de occurrences/routers.py.

Gaps cobertos:
- POST /occurrences/ → aluno não encontrado (404), retorno completo
- GET  /occurrences/ → retorno da lista (fluxo completo)
- GET  /occurrences/me → aluno vê as próprias, professor vê as que criou
- GET  /occurrences/{id} → não encontrado (404), aluno vê a sua,
  aluno bloqueado
- PUT  /occurrences/{id} → não encontrado, professor bloqueado,
  coordenador ok, retorno
- DELETE /occurrences/{id} → não encontrado, professor bloqueado,
  coordenador ok, retorno
"""

from http import HTTPStatus
from types import SimpleNamespace

import pytest_asyncio

from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token
from tests.conftest import _make_user

# --------------------------------------------------------------------------- #
# Fixtures                                                                   #
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def student(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def student2(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def teacher2(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


def tok(user):
    return create_access_token(data={'sub': user.email})


# Cria a ocorrência via HTTP para garantir que session e client
# compartilhem o mesmo estado no banco in-memory (StaticPool).
# Inserção direta via session em paralelo com client pode gerar
# NOT NULL constraint errors por dessincronização de conexão.
@pytest_asyncio.fixture
async def occurrence(client, teacher, student):

    response = client.post(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
        json={
            'student_id': student.id,
            'title': 'Comportamento inadequado',
            'description': 'Detalhes da ocorrência.',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    return SimpleNamespace(**response.json())


# --------------------------------------------------------------------------- #
# POST /occurrences/ — retorno completo e 404                               #
# --------------------------------------------------------------------------- #


def test_create_occurrence_returns_full_object(client, teacher, student):
    """POST /occurrences/ → cobre linhas 60-61 (refresh + return)."""
    response = client.post(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
        json={
            'student_id': student.id,
            'title': 'Atraso',
            'description': 'Chegou atrasado.',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['id'] is not None
    assert data['student_id'] == student.id
    assert data['created_by_id'] == teacher.id
    assert data['title'] == 'Atraso'
    assert data['description'] == 'Chegou atrasado.'


def test_create_occurrence_student_not_found(client, teacher):
    """POST /occurrences/ com student_id inválido → 404."""
    response = client.post(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
        json={
            'student_id': 99999,
            'title': 'Ghost',
            'description': '?',
        },
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Student not found'}


# --------------------------------------------------------------------------- #
# GET /occurrences/ — fluxo completo                                        #
# --------------------------------------------------------------------------- #


def test_list_all_occurrences_returns_data(client, coordinator, occurrence):
    """GET /occurrences/ → cobre linhas 75-76 (scalars + return)."""
    response = client.get(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(coordinator)}'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert 'occurrences' in data
    assert len(data['occurrences']) == 1
    assert data['occurrences'][0]['id'] == occurrence.id


def test_list_all_occurrences_empty(client, coordinator):
    """GET /occurrences/ com banco vazio → lista vazia."""
    response = client.get(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(coordinator)}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'occurrences': []}


# --------------------------------------------------------------------------- #
# GET /occurrences/me — aluno e professor                                   #
# --------------------------------------------------------------------------- #


def test_student_me_returns_own_occurrences(
    client, teacher, student, student2, occurrence
):
    """
    GET /occurrences/me como aluno → cobre branch STUDENT (linhas 93-95)
    e retorno (linhas 102-103).
    """
    # Cria ocorrência sobre student2 — não deve aparecer para student
    client.post(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
        json={'student_id': student2.id, 'title': 'Outra', 'description': 'x'},
    )

    response = client.get(
        '/occurrences/me',
        headers={'Authorization': f'Bearer {tok(student)}'},
    )
    assert response.status_code == HTTPStatus.OK
    occs = response.json()['occurrences']
    assert len(occs) == 1
    assert all(o['student_id'] == student.id for o in occs)


def test_teacher_me_returns_own_occurrences(
    client, teacher, teacher2, student, occurrence
):
    """
    GET /occurrences/me como professor → cobre branch else (linhas 97-99)
    e retorno.
    """
    # teacher2 cria uma ocorrência própria
    client.post(
        '/occurrences/',
        headers={'Authorization': f'Bearer {tok(teacher2)}'},
        json={'student_id': student.id, 'title': 'T2', 'description': 'desc'},
    )

    response = client.get(
        '/occurrences/me',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
    )
    assert response.status_code == HTTPStatus.OK
    occs = response.json()['occurrences']
    assert all(o['created_by_id'] == teacher.id for o in occs)


# --------------------------------------------------------------------------- #
# GET /occurrences/{id}                                                      #
# --------------------------------------------------------------------------- #


def test_get_occurrence_not_found(client, teacher):
    """GET /occurrences/99999 → 404 (linhas 122-124)."""
    response = client.get(
        '/occurrences/99999',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Occurrence not found'}


def test_get_occurrence_student_can_see_own(client, student, occurrence):
    """
    Aluno pode ver a própria ocorrência (linhas 128-137, branch não-raise).
    """
    response = client.get(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(student)}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == occurrence.id


def test_get_occurrence_student_forbidden_other(client, student2, occurrence):
    """Aluno não pode ver ocorrência de outro aluno → 403 (linhas 128-133)."""
    response = client.get(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(student2)}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_get_occurrence_teacher_returns_full_object(
    client, teacher, occurrence
):
    """Professor acessa ocorrência → cobre (return)."""
    response = client.get(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['id'] == occurrence.id
    assert data['title'] == occurrence.title


# --------------------------------------------------------------------------- #
# PUT /occurrences/{id}                                                      #
# --------------------------------------------------------------------------- #


def test_update_occurrence_not_found(client, teacher):
    """PUT /occurrences/99999 → 404 (linhas 157-159)."""
    response = client.put(
        '/occurrences/99999',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
        json={'title': 'X'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Occurrence not found'}


def test_update_occurrence_teacher_forbidden_other(
    client, teacher2, occurrence
):
    """Professor não pode editar ocorrência de outro → 403 (linhas 163-167)."""
    response = client.put(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(teacher2)}'},
        json={'title': 'Invasão'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_update_occurrence_returns_updated_data(client, teacher, occurrence):
    """
    PUT cobre linhas 172-178 (model_dump, setattr, commit, refresh, return).
    """
    response = client.put(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
        json={'title': 'Título novo', 'description': 'Descrição nova'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['title'] == 'Título novo'
    assert data['description'] == 'Descrição nova'
    assert data['id'] == occurrence.id


def test_update_occurrence_coordinator_success(
    client, coordinator, occurrence
):
    """Coordenador pode editar qualquer ocorrência (linhas 163-178)."""
    response = client.put(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(coordinator)}'},
        json={'description': 'Atualizado pelo coordenador'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['description'] == 'Atualizado pelo coordenador'


# --------------------------------------------------------------------------- #
# DELETE /occurrences/{id}                                                   #
# --------------------------------------------------------------------------- #


def test_delete_occurrence_not_found(client, teacher):
    """DELETE /occurrences/99999 → 404 (linhas 197-199)."""
    response = client.delete(
        '/occurrences/99999',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Occurrence not found'}


def test_delete_occurrence_teacher_forbidden_other(
    client, teacher2, occurrence
):
    """Professor não pode deletar ocorrência de outro → 403."""
    response = client.delete(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(teacher2)}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_delete_occurrence_teacher_success(client, teacher, occurrence):
    """Professor deleta a própria ocorrência → cobre linhas 212-214."""
    response = client.delete(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(teacher)}'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['id'] == occurrence.id


def test_delete_occurrence_coordinator_success(
    client, coordinator, occurrence
):
    """Coordenador pode deletar qualquer ocorrência → cobre linhas 212-214."""
    response = client.delete(
        f'/occurrences/{occurrence.id}',
        headers={'Authorization': f'Bearer {tok(coordinator)}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == occurrence.id
