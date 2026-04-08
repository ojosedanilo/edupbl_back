"""
Testes de occurrences/routers.py.

Endpoints:
  POST   /occurrences/      — criação
  GET    /occurrences/      — listagem (coordenador)
  GET    /occurrences/me    — ocorrências do próprio usuário
  GET    /occurrences/{id}  — detalhe
  PUT    /occurrences/{id}  — edição
  DELETE /occurrences/{id}  — deleção
"""

from http import HTTPStatus
from types import SimpleNamespace

import pytest_asyncio

from app.domains.occurrences.enums import OccurrenceTypeEnum
from app.domains.occurrences.models import Occurrence
from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


def _tok(user) -> str:
    return create_access_token(data={'sub': user.email})


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def other_teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def teacher2(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def student(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def student2(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def occurrence(client, teacher, student):
    """Cria via HTTP para garantir que session e client compartilhem o banco."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={
            'student_id': student.id,
            'title': 'Comportamento inadequado',
            'description': 'Detalhes da ocorrência.',
            # occurrence_type omitido — deve usar o default OUTROS
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    return SimpleNamespace(**resp.json())


@pytest_asyncio.fixture
async def occurrence_indisciplina(client, teacher, student):
    """Ocorrência com tipo explícito INDISCIPLINA."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={
            'student_id': student.id,
            'title': 'Briga em sala',
            'description': 'Detalhe.',
            'occurrence_type': OccurrenceTypeEnum.INDISCIPLINA.value,
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    return SimpleNamespace(**resp.json())


@pytest_asyncio.fixture
async def occurrence_db(session, teacher, student):
    """Cria diretamente no banco (para testes que não precisam do client)."""
    occ = Occurrence(
        created_by_id=teacher.id,
        student_id=student.id,
        title='Indisciplina',
        description='Detalhe',
        occurrence_type=OccurrenceTypeEnum.INDISCIPLINA,
    )
    session.add(occ)
    await session.commit()
    await session.refresh(occ)
    return occ


# ===========================================================================
# POST /occurrences/ — criação
# ===========================================================================


def test_create_occurrence_returns_full_object(client, teacher, student):
    """POST bem-sucedido → 201 com todos os campos, incluindo occurrence_type."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={
            'student_id': student.id,
            'title': 'Atraso',
            'description': 'Chegou atrasado.',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['id'] is not None
    assert data['student_id'] == student.id
    assert data['created_by_id'] == teacher.id
    assert data['title'] == 'Atraso'
    assert data['occurrence_type'] == OccurrenceTypeEnum.OUTROS.value


def test_create_occurrence_with_explicit_type(client, teacher, student):
    """POST com occurrence_type explícito → tipo salvo corretamente."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={
            'student_id': student.id,
            'title': 'Uso indevido',
            'description': 'Celular em prova.',
            'occurrence_type': OccurrenceTypeEnum.CELULAR.value,
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['occurrence_type'] == OccurrenceTypeEnum.CELULAR.value


def test_create_occurrence_default_type_is_outros(client, teacher, student):
    """POST sem occurrence_type → default é OUTROS."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={
            'student_id': student.id,
            'title': 'Ocorrência genérica',
            'description': 'Sem tipo específico.',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['occurrence_type'] == OccurrenceTypeEnum.OUTROS.value


def test_create_occurrence_all_types_accepted(client, teacher, student):
    """Todos os sete tipos são aceitos sem erro."""
    for occurrence_type in OccurrenceTypeEnum:
        resp = client.post(
            '/occurrences/',
            headers=_auth(teacher),
            json={
                'student_id': student.id,
                'title': f'Teste tipo {occurrence_type.value}',
                'description': 'Descrição.',
                'occurrence_type': occurrence_type.value,
            },
        )
        assert resp.status_code == HTTPStatus.CREATED, (
            f'Tipo {occurrence_type.value} foi rejeitado'
        )
        assert resp.json()['occurrence_type'] == occurrence_type.value


def test_create_occurrence_invalid_type_rejected(client, teacher, student):
    """occurrence_type inválido → 422 Unprocessable Entity."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={
            'student_id': student.id,
            'title': 'Título',
            'description': 'Desc.',
            'occurrence_type': 'tipo_inventado',
        },
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_occurrence_student_not_found(client, teacher):
    """student_id inexistente → 404 Student not found."""
    resp = client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={'student_id': 99999, 'title': 'Ghost', 'description': '?'},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {'detail': 'Student not found'}


async def test_create_occurrence_success_async(client, teacher, student):
    """POST (async fixture) → 201 com dados corretos."""
    resp = client.post(
        '/occurrences/',
        json={
            'student_id': student.id,
            'title': 'Briga',
            'description': 'Detalhes',
            'occurrence_type': OccurrenceTypeEnum.DESRESPEITO.value,
        },
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['title'] == 'Briga'
    assert body['created_by_id'] == teacher.id
    assert body['occurrence_type'] == OccurrenceTypeEnum.DESRESPEITO.value


# ===========================================================================
# GET /occurrences/
# ===========================================================================


def test_list_occurrences_coordinator(client, coordinator, occurrence):
    """Coordenador lista todas as ocorrências → 200 com a ocorrência criada."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence.id in ids


def test_list_occurrences_includes_occurrence_type(
    client, coordinator, occurrence, occurrence_indisciplina
):
    """Listagem retorna occurrence_type em cada item."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    occurrences = resp.json()['occurrences']
    assert all('occurrence_type' in o for o in occurrences)


def test_list_occurrences_empty(client, coordinator):
    """Banco vazio → lista vazia."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'occurrences': []}


def test_list_occurrences_teacher_forbidden(client, teacher, occurrence):
    """Professor não tem permissão de listar todas → 403."""
    resp = client.get('/occurrences/', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_list_occurrences_coordinator_async(
    client, coordinator, occurrence_db
):
    """Coordenador vê ocorrência criada via banco."""
    resp = client.get('/occurrences/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence_db.id in ids


# ===========================================================================
# GET /occurrences/me
# ===========================================================================


def test_student_me_sees_own_occurrences(
    client, teacher, student, student2, occurrence
):
    """Aluno vê apenas as próprias ocorrências."""
    client.post(
        '/occurrences/',
        headers=_auth(teacher),
        json={'student_id': student2.id, 'title': 'Outra', 'description': 'x'},
    )
    resp = client.get('/occurrences/me', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    occs = resp.json()['occurrences']
    assert len(occs) == 1
    assert all(o['student_id'] == student.id for o in occs)


def test_teacher_me_sees_own_created(
    client, teacher, teacher2, student, occurrence
):
    """Professor vê apenas as ocorrências que criou."""
    client.post(
        '/occurrences/',
        headers=_auth(teacher2),
        json={'student_id': student.id, 'title': 'T2', 'description': 'desc'},
    )
    resp = client.get('/occurrences/me', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.OK
    assert all(
        o['created_by_id'] == teacher.id for o in resp.json()['occurrences']
    )


async def test_student_me_async(client, student, occurrence_db):
    """GET /occurrences/me → aluno vê a ocorrência que lhe pertence."""
    resp = client.get('/occurrences/me', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence_db.id in ids


async def test_teacher_me_async(client, teacher, occurrence_db):
    """GET /occurrences/me → professor vê o que criou."""
    resp = client.get('/occurrences/me', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.OK
    ids = [o['id'] for o in resp.json()['occurrences']]
    assert occurrence_db.id in ids


# ===========================================================================
# GET /occurrences/{id}
# ===========================================================================


def test_get_occurrence_not_found(client, teacher):
    """ID inexistente → 404."""
    resp = client.get('/occurrences/99999', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {'detail': 'Occurrence not found'}


def test_get_occurrence_student_sees_own(client, student, occurrence):
    """Aluno pode ver a própria ocorrência → 200 com occurrence_type."""
    resp = client.get(f'/occurrences/{occurrence.id}', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['id'] == occurrence.id
    assert 'occurrence_type' in data


def test_get_occurrence_student_forbidden_other(client, student2, occurrence):
    """Aluno não vê ocorrência de outro aluno → 403."""
    resp = client.get(f'/occurrences/{occurrence.id}', headers=_auth(student2))
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_get_occurrence_teacher_sees_any(client, teacher, occurrence):
    """Professor acessa qualquer ocorrência → 200."""
    resp = client.get(f'/occurrences/{occurrence.id}', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == occurrence.title


def test_get_occurrence_returns_correct_type(
    client, teacher, occurrence_indisciplina
):
    """Detalhe retorna o tipo correto da ocorrência."""
    resp = client.get(
        f'/occurrences/{occurrence_indisciplina.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        resp.json()['occurrence_type'] == OccurrenceTypeEnum.INDISCIPLINA.value
    )


async def test_get_occurrence_coordinator_async(
    client, coordinator, occurrence_db
):
    """Coordenador pode ver qualquer ocorrência."""
    resp = client.get(
        f'/occurrences/{occurrence_db.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence_db.id


async def test_get_occurrence_student_own_async(
    client, student, occurrence_db
):
    """Aluno vê a própria ocorrência (async fixture)."""
    resp = client.get(
        f'/occurrences/{occurrence_db.id}', headers=_auth(student)
    )
    assert resp.status_code == HTTPStatus.OK


async def test_get_occurrence_student_other_forbidden_async(
    client, session, occurrence_db
):
    """Aluno não vê ocorrência de outro → 403."""
    other = await _make_user(session, role=UserRole.STUDENT)
    resp = client.get(f'/occurrences/{occurrence_db.id}', headers=_auth(other))
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# PUT /occurrences/{id}
# ===========================================================================


def test_update_occurrence_not_found(client, teacher):
    """ID inexistente → 404."""
    resp = client.put(
        '/occurrences/99999',
        headers=_auth(teacher),
        json={'title': 'X'},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {'detail': 'Occurrence not found'}


def test_update_occurrence_teacher_forbidden_other(
    client, other_teacher, occurrence
):
    """Professor não edita ocorrência de outro → 403."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        headers=_auth(other_teacher),
        json={'title': 'Invasão'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_update_occurrence_success(client, teacher, occurrence):
    """Professor edita a própria ocorrência → 200 com dados atualizados."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        headers=_auth(teacher),
        json={'title': 'Título novo', 'description': 'Descrição nova'},
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['title'] == 'Título novo'
    assert data['description'] == 'Descrição nova'
    # occurrence_type não foi enviado — deve permanecer inalterado
    assert data['occurrence_type'] == OccurrenceTypeEnum.OUTROS.value


def test_update_occurrence_type(client, teacher, occurrence):
    """Professor pode alterar o tipo da ocorrência → 200 com novo tipo."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        headers=_auth(teacher),
        json={'occurrence_type': OccurrenceTypeEnum.RENDIMENTO.value},
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        resp.json()['occurrence_type'] == OccurrenceTypeEnum.RENDIMENTO.value
    )


def test_update_occurrence_coordinator(client, coordinator, occurrence):
    """Coordenador edita qualquer ocorrência → 200."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        headers=_auth(coordinator),
        json={'description': 'Atualizado pelo coordenador'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['description'] == 'Atualizado pelo coordenador'


def test_update_occurrence_invalid_type_rejected(client, teacher, occurrence):
    """PUT com occurrence_type inválido → 422."""
    resp = client.put(
        f'/occurrences/{occurrence.id}',
        headers=_auth(teacher),
        json={'occurrence_type': 'tipo_inexistente'},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_update_occurrence_success_async(client, teacher, occurrence_db):
    """PUT (async fixture) → 200 com título atualizado."""
    resp = client.put(
        f'/occurrences/{occurrence_db.id}',
        json={'title': 'Atualizado'},
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['title'] == 'Atualizado'


async def test_update_occurrence_not_own_teacher_async(
    client, other_teacher, occurrence_db
):
    """Professor não edita a de outro (async fixture) → 403."""
    resp = client.put(
        f'/occurrences/{occurrence_db.id}',
        json={'title': 'Tentativa'},
        headers=_auth(other_teacher),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_update_occurrence_coordinator_async(
    client, coordinator, occurrence_db
):
    """Coordenador edita qualquer (async fixture) → 200."""
    resp = client.put(
        f'/occurrences/{occurrence_db.id}',
        json={'title': 'Editado pelo coord'},
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.OK


# ===========================================================================
# DELETE /occurrences/{id}
# ===========================================================================


def test_delete_occurrence_not_found(client, teacher):
    """ID inexistente → 404."""
    resp = client.delete('/occurrences/99999', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {'detail': 'Occurrence not found'}


def test_delete_occurrence_teacher_forbidden_other(
    client, other_teacher, occurrence
):
    """Professor não deleta ocorrência de outro → 403."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(other_teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_delete_occurrence_teacher_success(client, teacher, occurrence):
    """Professor deleta a própria ocorrência → 200 com dados do objeto."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['id'] == occurrence.id
    # Resposta do delete também deve conter occurrence_type
    assert 'occurrence_type' in data


def test_delete_occurrence_coordinator(client, coordinator, occurrence):
    """Coordenador deleta qualquer ocorrência → 200."""
    resp = client.delete(
        f'/occurrences/{occurrence.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence.id


async def test_delete_occurrence_success_async(client, teacher, occurrence_db):
    """DELETE (async fixture) → 200."""
    resp = client.delete(
        f'/occurrences/{occurrence_db.id}', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == occurrence_db.id


async def test_delete_occurrence_not_own_async(
    client, other_teacher, occurrence_db
):
    """Professor não deleta a de outro (async fixture) → 403."""
    resp = client.delete(
        f'/occurrences/{occurrence_db.id}', headers=_auth(other_teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_delete_occurrence_coordinator_async(
    client, coordinator, occurrence_db
):
    """Coordenador deleta qualquer (async fixture) → 200."""
    resp = client.delete(
        f'/occurrences/{occurrence_db.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
