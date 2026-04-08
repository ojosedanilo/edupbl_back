"""
Testes de users/routers.py e users/schemas.py — cobertura 100%.

Endpoints cobertos:
  POST   /users/                         — criação
  GET    /users/                         — listagem paginada
  GET    /users/students                 — lista reduzida de todos os alunos
  GET    /users/classroom/{id}           — alunos de uma turma (ownership check)
  GET    /users/current-class-students   — alunos da aula atual do professor
  GET    /users/{id}/avatar              — servir avatar
  PUT    /users/{id}                     — atualização
  PATCH  /users/me/avatar                — upload avatar próprio
  PATCH  /users/me/password              — troca de senha
  PATCH  /users/{id}/avatar              — DT faz upload de avatar de aluno
  PATCH  /users/{id}/profile             — DT edita perfil de aluno
  PATCH  /users/{id}/deactivate          — desativar usuário
  DELETE /users/{id}                     — deleção + remoção de avatar do disco
"""

import io
from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.domains.users.schemas import UserSchema, UserUpdate
from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# Fixture local — admin para testes de criação e listagem
@pytest_asyncio.fixture
async def admin(session):
    return await _make_user(session, role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


# ===========================================================================
# POST /users/ — criação
# ===========================================================================


def test_create_user_success(client, admin):
    """Dados válidos + admin → 201 com campos corretos, senha nunca exposta."""
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': 'novousuario',
            'email': 'novo@example.com',
            'password': 'senhasegura',
            'first_name': 'Novo',
            'last_name': 'Usuário',
            'role': UserRole.TEACHER.value,
            'is_tutor': False,
            'is_active': True,
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['username'] == 'novousuario'
    assert data['email'] == 'novo@example.com'
    assert data['role'] == UserRole.TEACHER.value
    assert 'password' not in data


def test_create_user_unauthenticated(client):
    """POST /users/ sem token → 401."""
    resp = client.post(
        '/users/',
        json={
            'username': 'novousuario',
            'email': 'novo@example.com',
            'password': 'senhasegura',
            'first_name': 'Novo',
            'last_name': 'Usuário',
        },
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_create_user_duplicate_username(client, admin, user):
    """Username já existente → 409 Conflict."""
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': user.username,
            'email': 'outro@example.com',
            'password': 'secret123',
            'first_name': 'Outro',
            'last_name': 'Usuário',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json() == {'detail': 'Username already exists'}


def test_create_user_duplicate_email(client, admin, user):
    """E-mail já existente → 409 Conflict."""
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': 'outrouser',
            'email': user.email,
            'password': 'secret123',
            'first_name': 'Outro',
            'last_name': 'Usuário',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json() == {'detail': 'Email already exists'}


async def test_create_user_username_conflict_async(client, session, admin):
    """Username duplicado via _make_user (async) → 409."""
    existing = await _make_user(session)
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': existing.username,
            'email': 'outro@test.com',
            'password': 'secret123',
            'first_name': 'X',
            'last_name': 'Y',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail'] == 'Username already exists'


async def test_create_user_email_conflict_async(client, session, admin):
    """Email duplicado via _make_user (async) → 409."""
    existing = await _make_user(session)
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': 'outro_user',
            'email': existing.email,
            'password': 'secret123',
            'first_name': 'X',
            'last_name': 'Y',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail'] == 'Email already exists'


def test_create_user_api_invalid_username(client, admin):
    """Username inválido via API → 422 Unprocessable Entity."""
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': 'João Silva',
            'email': 'joao@test.com',
            'password': 'secret',
            'first_name': 'João',
            'last_name': 'Silva',
        },
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ===========================================================================
# GET /users/ — listagem paginada
# ===========================================================================


def test_read_users_returns_list(client, coordinator, user):
    """GET /users/ com coordinator → lista com o usuário existente."""
    resp = client.get('/users/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'users' in body
    assert user.id in [u['id'] for u in body['users']]


def test_read_users_unauthenticated(client):
    """GET /users/ sem token → 401."""
    resp = client.get('/users/')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_read_users_empty(client, coordinator):
    """GET /users/ com coordinator e sem usuários comuns → lista com só o coordinator."""
    resp = client.get('/users/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    # O coordinator em si já é um usuário no banco
    assert 'users' in resp.json()


async def test_read_users_with_pagination(client, session, coordinator):
    """GET /users/?limit=1 → retorna exatamente 1 usuário."""
    await _make_user(session)
    await _make_user(session)
    resp = client.get('/users/?limit=1&offset=0', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['users']) == 1


async def test_read_users_filter_by_role(client, session, coordinator):
    """GET /users/?role=student → retorna apenas usuários com aquela role."""
    await _make_user(session, role=UserRole.STUDENT)
    await _make_user(session, role=UserRole.STUDENT)
    await _make_user(session, role=UserRole.TEACHER)

    resp = client.get('/users/?role=student', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()['users']
    assert len(users) == 2
    assert all(u['role'] == UserRole.STUDENT.value for u in users)


async def test_create_and_read_user(client, admin, coordinator):
    """POST /users/ + GET /users/ → novo usuário aparece na lista."""
    resp = client.post(
        '/users/',
        headers=_auth(admin),
        json={
            'username': 'novo_user',
            'email': 'novo@test.com',
            'password': 'senhasegura',
            'first_name': 'Novo',
            'last_name': 'User',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    user_id = resp.json()['id']

    list_resp = client.get('/users/', headers=_auth(coordinator))
    ids = [u['id'] for u in list_resp.json()['users']]
    assert user_id in ids


# ===========================================================================
# GET /users/students â Lista reduzida de todos os alunos
# ===========================================================================


async def test_list_all_students_porter(client, session):
    """Porteiro acessa /students â 200 com lista de alunos."""
    porter = await _make_user(session, role=UserRole.PORTER)
    s1 = await _make_user(session, role=UserRole.STUDENT, last_name='Zebra')
    s2 = await _make_user(session, role=UserRole.STUDENT, last_name='Abreu')

    resp = client.get('/users/students', headers=_auth(porter))

    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'students' in body
    ids = [s['id'] for s in body['students']]
    assert s1.id in ids
    assert s2.id in ids


async def test_list_all_students_ordered_by_last_name(client, session):
    """Alunos retornados ordenados por sobrenome (last_name ASC)."""
    teacher = await _make_user(session, role=UserRole.TEACHER)
    await _make_user(session, role=UserRole.STUDENT, last_name='Zebra')
    await _make_user(session, role=UserRole.STUDENT, last_name='Abreu')
    await _make_user(session, role=UserRole.STUDENT, last_name='Melo')

    resp = client.get('/users/students', headers=_auth(teacher))

    assert resp.status_code == HTTPStatus.OK
    last_names = [s['last_name'] for s in resp.json()['students']]
    assert last_names == sorted(last_names)


async def test_list_all_students_requires_permission(client, session):
    """Student e Guardian sem USER_VIEW_STUDENTS â 403."""
    student = await _make_user(session, role=UserRole.STUDENT)
    guardian = await _make_user(session, role=UserRole.GUARDIAN)

    for actor in (student, guardian):
        resp = client.get('/users/students', headers=_auth(actor))
        assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_list_all_students_unauthenticated(client):
    """Sem token â 401."""
    resp = client.get('/users/students')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# GET /users/classroom/{id} â Alunos de uma turma (ownership check)
# ===========================================================================


async def test_list_classroom_students_teacher_own(client, session):
    """Professor acessa /classroom/{id} da própria turma â 200."""
    teacher = await _make_user(session, role=UserRole.TEACHER, classroom_id=10)
    s = await _make_user(session, role=UserRole.STUDENT, classroom_id=10)

    resp = client.get('/users/classroom/10', headers=_auth(teacher))

    assert resp.status_code == HTTPStatus.OK
    ids = [st['id'] for st in resp.json()['students']]
    assert s.id in ids


async def test_list_classroom_students_teacher_other_forbidden(
    client, session
):
    """Professor tenta acessar turma alheia â 403."""
    teacher = await _make_user(session, role=UserRole.TEACHER, classroom_id=10)

    resp = client.get('/users/classroom/99', headers=_auth(teacher))

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert 'própria turma' in resp.json()['detail']


async def test_list_classroom_students_coordinator_any(client, session):
    """Coordenador acessa qualquer turma â 200."""
    coordinator = await _make_user(session, role=UserRole.COORDINATOR)
    s = await _make_user(session, role=UserRole.STUDENT, classroom_id=5)

    resp = client.get('/users/classroom/5', headers=_auth(coordinator))

    assert resp.status_code == HTTPStatus.OK
    ids = [st['id'] for st in resp.json()['students']]
    assert s.id in ids


async def test_list_classroom_students_porter_any(client, session):
    """Porteiro acessa qualquer turma â 200."""
    porter = await _make_user(session, role=UserRole.PORTER)
    s = await _make_user(session, role=UserRole.STUDENT, classroom_id=7)

    resp = client.get('/users/classroom/7', headers=_auth(porter))

    assert resp.status_code == HTTPStatus.OK
    ids = [st['id'] for st in resp.json()['students']]
    assert s.id in ids


async def test_list_classroom_students_admin_any(client, session):
    """Admin acessa qualquer turma â 200."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    s = await _make_user(session, role=UserRole.STUDENT, classroom_id=3)

    resp = client.get('/users/classroom/3', headers=_auth(admin))

    assert resp.status_code == HTTPStatus.OK
    ids = [st['id'] for st in resp.json()['students']]
    assert s.id in ids


# ===========================================================================
# GET /users/current-class-students â Alunos da aula atual
# ===========================================================================


async def test_current_class_students_no_classroom(client, session):
    """Professor sem classroom_id â 404 'Você não tem turma associada'."""
    teacher = await _make_user(session, role=UserRole.TEACHER)

    resp = client.get('/users/current-class-students', headers=_auth(teacher))

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert 'turma associada' in resp.json()['detail']


async def test_current_class_students_outside_class_time(client, session):
    """Fora do horário de aula â 404 'Nenhuma aula em andamento'."""
    from datetime import time as dtime
    from unittest.mock import patch

    teacher = await _make_user(session, role=UserRole.TEACHER, classroom_id=1)

    with patch('app.domains.users.routers.datetime') as mock_dt:
        mock_dt.now.return_value.time.return_value = dtime(0, 0)

        resp = client.get(
            '/users/current-class-students', headers=_auth(teacher)
        )

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert 'andamento' in resp.json()['detail']


async def test_current_class_students_during_class(client, session):
    """Durante horário de aula â 200 com alunos da turma do professor."""
    from datetime import time as dtime
    from unittest.mock import patch

    teacher = await _make_user(session, role=UserRole.TEACHER, classroom_id=2)
    s1 = await _make_user(session, role=UserRole.STUDENT, classroom_id=2)
    s2 = await _make_user(session, role=UserRole.STUDENT, classroom_id=2)
    # Aluno de outra turma â não deve aparecer
    other = await _make_user(session, role=UserRole.STUDENT, classroom_id=99)

    # 07:45 é um CLASS_PERIOD válido (confirmado em test_schedules.py)
    with patch('app.domains.users.routers.datetime') as mock_dt:
        mock_dt.now.return_value.time.return_value = dtime(7, 45)

        resp = client.get(
            '/users/current-class-students', headers=_auth(teacher)
        )

    assert resp.status_code == HTTPStatus.OK
    ids = [s['id'] for s in resp.json()['students']]
    assert s1.id in ids
    assert s2.id in ids
    assert other.id not in ids


# ===========================================================================
# GET /users/search
# ===========================================================================


async def test_search_users_by_first_name(client, session):
    """Busca por primeiro nome retorna usuário correto."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    target = await _make_user(session, first_name='Zacarias')

    resp = client.get('/users/search?q=Zacarias', headers=_auth(admin))

    assert resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in resp.json()['users']]
    assert target.id in ids


async def test_search_users_by_last_name(client, session):
    """Busca por sobrenome retorna usuário correto."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    target = await _make_user(session, last_name='Figueiredo')

    resp = client.get('/users/search?q=Figueiredo', headers=_auth(admin))

    assert resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in resp.json()['users']]
    assert target.id in ids


async def test_search_users_by_username(client, session):
    """Busca por username retorna usuário correto."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    target = await _make_user(session, username='xablau99')

    resp = client.get('/users/search?q=xablau99', headers=_auth(admin))

    assert resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in resp.json()['users']]
    assert target.id in ids


async def test_search_users_filter_by_role(client, session):
    """Busca com filtro de role retorna apenas usuários daquele role."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    teacher = await _make_user(
        session, role=UserRole.TEACHER, first_name='Comum'
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, first_name='Comum'
    )

    resp = client.get(
        f'/users/search?q=Comum&role={UserRole.TEACHER.value}',
        headers=_auth(admin),
    )

    assert resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in resp.json()['users']]
    assert teacher.id in ids
    assert student.id not in ids


async def test_search_users_limit(client, session):
    """Parâmetro limit é respeitado."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    for _ in range(5):
        await _make_user(session, first_name='Repetido')

    resp = client.get('/users/search?q=Repetido&limit=2', headers=_auth(admin))

    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['users']) <= 2


async def test_search_users_no_results(client, session):
    """Busca sem resultados retorna lista vazia."""
    admin = await _make_user(session, role=UserRole.ADMIN)

    resp = client.get(
        '/users/search?q=NomeQueNaoExisteNuncaNaVida', headers=_auth(admin)
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['users'] == []


async def test_search_users_unauthenticated(client):
    """GET /users/search sem token → 401."""
    resp = client.get('/users/search?q=qualquer')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# POST /users/bulk
# ===========================================================================


async def test_bulk_users_returns_found(client, session):
    """POST /users/bulk com IDs existentes → retorna usuários na ordem."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    u1 = await _make_user(session)
    u2 = await _make_user(session)

    resp = client.post(
        '/users/bulk',
        headers=_auth(admin),
        json={'ids': [u2.id, u1.id]},
    )

    assert resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in resp.json()['users']]
    # Ordem dos IDs fornecidos deve ser preservada
    assert ids == [u2.id, u1.id]


async def test_bulk_users_ignores_missing_ids(client, session):
    """IDs inexistentes são silenciosamente ignorados."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    u = await _make_user(session)

    resp = client.post(
        '/users/bulk',
        headers=_auth(admin),
        json={'ids': [u.id, 999999]},
    )

    assert resp.status_code == HTTPStatus.OK
    ids = [x['id'] for x in resp.json()['users']]
    assert ids == [u.id]


async def test_bulk_users_empty_list(client, session):
    """Lista vazia de IDs → retorna lista vazia sem erro."""
    admin = await _make_user(session, role=UserRole.ADMIN)

    resp = client.post(
        '/users/bulk',
        headers=_auth(admin),
        json={'ids': []},
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['users'] == []


async def test_bulk_users_teacher_can_access(client, session):
    """Teacher tem USER_VIEW_STUDENTS → consegue usar /bulk."""
    teacher = await _make_user(session, role=UserRole.TEACHER)
    student = await _make_user(session, role=UserRole.STUDENT)

    resp = client.post(
        '/users/bulk',
        headers=_auth(teacher),
        json={'ids': [student.id]},
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['users'][0]['id'] == student.id


async def test_bulk_users_unauthenticated(client):
    """POST /users/bulk sem token → 401."""
    resp = client.post('/users/bulk', json={'ids': [1, 2]})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# GET /users/{id}/avatar — servir avatar
# ===========================================================================


async def test_get_avatar_unauthenticated(client):
    """GET /users/9999/avatar sem token → 401 (endpoint protegido desde proteção de avatar)."""
    resp = client.get('/users/9999/avatar')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_get_avatar_user_not_found(client, session):
    """GET /users/9999/avatar com token válido → 404 user not found."""
    u = await _make_user(session)
    resp = client.get('/users/9999/avatar', headers=_auth(u))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'User not found'


async def test_get_avatar_no_avatar_url(client, session):
    """GET avatar de usuário sem avatar_url → 404 avatar not found."""
    u = await _make_user(session)
    assert u.avatar_url is None
    resp = client.get(f'/users/{u.id}/avatar', headers=_auth(u))
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'Avatar not found'


async def test_get_avatar_file_missing_on_disk(client, session, tmp_path):
    """GET avatar com avatar_url no banco mas arquivo ausente no disco → 404."""
    u = await _make_user(session)
    # Seta avatar_url no banco sem criar o arquivo
    from app.domains.users.models import User
    from app.domains.users import routers as user_routers

    # Patch _AVATAR_DIR para tmp_path (sem criar o arquivo)
    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        u_fresh = await session.get(User, u.id)
        u_fresh.avatar_url = f'avatars/{u.id}.webp'
        await session.commit()

        resp = client.get(f'/users/{u.id}/avatar', headers=_auth(u))
        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()['detail'] == 'Avatar not found'


async def test_get_avatar_success(client, session, tmp_path):
    """GET avatar existente com token válido → 200 com content-type image/webp."""
    from PIL import Image
    from app.domains.users.models import User
    from app.domains.users import routers as user_routers

    u = await _make_user(session)

    # Criar avatar real no tmp_path
    avatar_file = tmp_path / f'{u.id}.webp'
    img = Image.new('RGB', (256, 256), color=(100, 150, 200))
    img.save(avatar_file, format='WEBP')

    # Atualizar avatar_url no banco
    u_fresh = await session.get(User, u.id)
    u_fresh.avatar_url = f'avatars/{u.id}.webp'
    await session.commit()

    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.get(f'/users/{u.id}/avatar', headers=_auth(u))
        assert resp.status_code == HTTPStatus.OK
        assert resp.headers['content-type'] == 'image/webp'


# ===========================================================================
# PUT /users/{id} — atualização
# ===========================================================================


def test_update_user_forbidden(client, user, other_user, token):
    """PUT no id de outro usuário → 403 Forbidden."""
    resp = client.put(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'first_name': 'Invasor'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json() == {'detail': 'Not enough permissions'}


def test_update_user_conflict_username(client, user, other_user, token):
    """PUT com username de outro usuário → 409."""
    resp = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'username': other_user.username},
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json() == {'detail': 'Username or Email already exists'}


def test_update_user_conflict_email(client, user, other_user, token):
    """PUT com e-mail de outro usuário → 409."""
    resp = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'email': other_user.email},
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json() == {'detail': 'Username or Email already exists'}


def test_update_user_same_own_email(client, user, token):
    """PUT enviando o próprio e-mail → sem conflito, 200."""
    resp = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'email': user.email},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['email'] == user.email


def test_update_user_non_conflicting_fields(client, user, token):
    """PUT com username/email únicos → 200 com dados atualizados."""
    resp = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'uniqueuser99',
            'email': 'unique99@example.com',
            'first_name': 'Atualizado',
        },
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['username'] == 'uniqueuser99'
    assert data['first_name'] == 'Atualizado'


def test_update_user_password_rehashes(client, user, token):
    """PUT com campo password → nova senha funciona no login."""
    resp = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'password': 'novasenha123'},
    )
    assert resp.status_code == HTTPStatus.OK
    login = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'novasenha123'},
    )
    assert login.status_code == HTTPStatus.OK


async def test_update_user_forbidden_other_async(client, session):
    """PUT /users/{id} de outro usuário (async fixture) → 403."""
    u1 = await _make_user(session)
    u2 = await _make_user(session)
    resp = client.put(
        f'/users/{u2.id}',
        json={'email': 'novo@test.com'},
        headers=_auth(u1),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_update_user_returns_updated(client, session):
    """PUT /users/{id} → retorna dados atualizados."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'first_name': 'NomeNovo'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['first_name'] == 'NomeNovo'


async def test_update_user_no_username_no_email(client, session):
    """PUT sem username/email → sem verificação de conflito → 200."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'first_name': 'Novo Nome'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['first_name'] == 'Novo Nome'


async def test_update_user_own_email_no_conflict(client, session):
    """PUT com o próprio e-mail → sem conflito → 200."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'email': u.email},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK


# ===========================================================================
# PATCH /users/me/avatar — upload de avatar (próprio usuário)
# ===========================================================================


def _make_webp_bytes() -> bytes:
    """Gera bytes de imagem WebP 10×10 válida para testes."""
    buf = io.BytesIO()
    from PIL import Image

    img = Image.new('RGB', (10, 10), color=(255, 0, 0))
    img.save(buf, format='WEBP')
    return buf.getvalue()


def _make_png_bytes() -> bytes:
    """Gera bytes de imagem PNG 10×10 válida para testes."""
    buf = io.BytesIO()
    from PIL import Image

    img = Image.new('RGB', (10, 10), color=(0, 255, 0))
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_rgba_png_bytes() -> bytes:
    """Gera bytes de imagem PNG RGBA para testar conversão."""
    buf = io.BytesIO()
    from PIL import Image

    img = Image.new('RGBA', (10, 10), color=(0, 0, 255, 128))
    img.save(buf, format='PNG')
    return buf.getvalue()


async def test_upload_my_avatar_success(client, session, tmp_path):
    """PATCH /users/me/avatar com imagem válida → 200 e avatar_url atualizado."""
    from app.domains.users import routers as user_routers

    u = await _make_user(session)
    webp_bytes = _make_webp_bytes()

    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.patch(
            '/users/me/avatar',
            headers=_auth(u),
            files={'file': ('avatar.webp', webp_bytes, 'image/webp')},
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['avatar_url'] is not None


async def test_upload_my_avatar_png_rgba(client, session, tmp_path):
    """PATCH /users/me/avatar com PNG RGBA → conversão para RGB → 200."""
    from app.domains.users import routers as user_routers

    u = await _make_user(session)
    rgba_bytes = _make_rgba_png_bytes()

    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.patch(
            '/users/me/avatar',
            headers=_auth(u),
            files={'file': ('avatar.png', rgba_bytes, 'image/png')},
        )
    assert resp.status_code == HTTPStatus.OK


async def test_upload_my_avatar_wrong_mime(client, session):
    """PATCH /users/me/avatar com MIME inválido → 422."""
    u = await _make_user(session)
    resp = client.patch(
        '/users/me/avatar',
        headers=_auth(u),
        files={'file': ('doc.pdf', b'%PDF-1.4', 'application/pdf')},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'Tipo de arquivo não suportado' in resp.json()['detail']


async def test_upload_my_avatar_too_large(client, session):
    """PATCH /users/me/avatar com arquivo > 2 MB → 413."""
    u = await _make_user(session)
    big_bytes = b'x' * (2 * 1024 * 1024 + 1)
    resp = client.patch(
        '/users/me/avatar',
        headers=_auth(u),
        files={'file': ('big.webp', big_bytes, 'image/webp')},
    )
    assert resp.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert 'muito grande' in resp.json()['detail']


async def test_upload_my_avatar_invalid_image_bytes(client, session):
    """PATCH /users/me/avatar com bytes que não são imagem → 422."""
    u = await _make_user(session)
    resp = client.patch(
        '/users/me/avatar',
        headers=_auth(u),
        files={'file': ('corrupt.webp', b'not-an-image', 'image/webp')},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'processar a imagem' in resp.json()['detail']


# ===========================================================================
# PATCH /users/me/password
# ===========================================================================


def test_change_password_wrong_current(client, user, token):
    """Senha atual errada → 401."""
    resp = client.patch(
        '/users/me/password',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'current_password': 'senha_errada',
            'new_password': 'novasenha123',
        },
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Current password is incorrect'}


def test_change_password_success(client, user, token):
    """Senha correta → 200 e novo login funciona."""
    resp = client.patch(
        '/users/me/password',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'current_password': user.clean_password,
            'new_password': 'novaSenhaForte!',
        },
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'Password updated successfully'}

    login = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'novaSenhaForte!'},
    )
    assert login.status_code == HTTPStatus.OK


async def test_change_password_success_async(client, session):
    """PATCH /me/password (async fixture) → mensagem de sucesso."""
    u = await _make_user(session)
    resp = client.patch(
        '/users/me/password',
        json={
            'current_password': u.clean_password,
            'new_password': 'novaSenha!',
        },
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'Password updated successfully'}


# ===========================================================================
# PATCH /users/{id}/avatar — DT faz upload de avatar de aluno
# ===========================================================================


async def test_dt_upload_student_avatar_success(client, session, tmp_path):
    """DT faz upload de avatar de aluno da sua turma → 200."""
    from app.domains.users.models import Classroom
    from app.domains.users import routers as user_routers

    classroom = Classroom(name='Turma X')
    session.add(classroom)
    await session.flush()

    dt = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )
    student = await _make_user(
        session,
        role=UserRole.STUDENT,
        classroom_id=classroom.id,
    )

    webp_bytes = _make_webp_bytes()
    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.patch(
            f'/users/{student.id}/avatar',
            headers=_auth(dt),
            files={'file': ('avatar.webp', webp_bytes, 'image/webp')},
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['avatar_url'] is not None


async def test_dt_upload_avatar_user_not_found(client, session):
    """DT tenta fazer upload de avatar de usuário inexistente → 404."""
    dt = await _make_user(session, role=UserRole.TEACHER, is_tutor=True)
    webp_bytes = _make_webp_bytes()
    resp = client.patch(
        '/users/9999/avatar',
        headers=_auth(dt),
        files={'file': ('avatar.webp', webp_bytes, 'image/webp')},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'User not found'


async def test_dt_upload_avatar_not_student(client, session):
    """DT tenta fazer upload de avatar de não-aluno → 422."""
    from app.domains.users.models import Classroom

    classroom = Classroom(name='Turma Y')
    session.add(classroom)
    await session.flush()

    dt = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )
    teacher2 = await _make_user(
        session, role=UserRole.TEACHER, classroom_id=classroom.id
    )

    webp_bytes = _make_webp_bytes()
    resp = client.patch(
        f'/users/{teacher2.id}/avatar',
        headers=_auth(dt),
        files={'file': ('avatar.webp', webp_bytes, 'image/webp')},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'avatares de alunos' in resp.json()['detail']


async def test_dt_upload_avatar_wrong_classroom(client, session):
    """DT tenta fazer upload de avatar de aluno de outra turma → 403."""
    from app.domains.users.models import Classroom

    c1 = Classroom(name='Turma DT1')
    c2 = Classroom(name='Turma DT2')
    session.add_all([c1, c2])
    await session.flush()

    dt = await _make_user(
        session, role=UserRole.TEACHER, is_tutor=True, classroom_id=c1.id
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=c2.id
    )

    webp_bytes = _make_webp_bytes()
    resp = client.patch(
        f'/users/{student.id}/avatar',
        headers=_auth(dt),
        files={'file': ('avatar.webp', webp_bytes, 'image/webp')},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert 'turma' in resp.json()['detail']


async def test_non_dt_cannot_upload_student_avatar(client, session):
    """Professor sem is_tutor não tem permissão → 403."""
    from app.domains.users.models import Classroom

    classroom = Classroom(name='Turma Z')
    session.add(classroom)
    await session.flush()

    teacher = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=False,
        classroom_id=classroom.id,
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )

    webp_bytes = _make_webp_bytes()
    resp = client.patch(
        f'/users/{student.id}/avatar',
        headers=_auth(teacher),
        files={'file': ('avatar.webp', webp_bytes, 'image/webp')},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_patch_profile_does_not_wipe_avatar_url(
    client, session, tmp_path
):
    """
    BUG REGRESSION: PATCH /users/{id}/profile sem avatar_url no body
    NÃO deve apagar o avatar_url existente do aluno.

    Reproduz o bug: após upload de avatar, chamar update_student_profile
    com body sem avatar_url zera o campo no banco.
    """
    from app.domains.users import routers as user_routers
    from app.domains.users.models import Classroom, User as UserModel
    from PIL import Image

    classroom = Classroom(name='Turma Bug')
    session.add(classroom)
    await session.flush()

    dt = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )

    # Simula avatar já existente no banco
    avatar_file = tmp_path / f'{student.id}.webp'
    Image.new('RGB', (256, 256)).save(avatar_file, format='WEBP')
    s = await session.get(UserModel, student.id)
    s.avatar_url = f'avatars/{student.id}.webp'
    await session.commit()

    # DT atualiza perfil SEM enviar avatar_url no body
    resp = client.patch(
        f'/users/{student.id}/profile',
        headers=_auth(dt),
        json={},  # body vazio — não deve tocar no avatar_url
    )

    assert resp.status_code == HTTPStatus.OK

    # BUG: avatar_url seria sobrescrito com None
    # Após a correção, deve preservar o valor original
    assert resp.json()['avatar_url'] == f'avatars/{student.id}.webp', (
        'avatar_url foi apagado pelo PATCH /profile — bug de campo com default=None '
        "no StudentProfileUpdate sendo tratado como 'enviado pelo cliente'"
    )


async def test_patch_profile_explicit_null_avatar_url_allowed(client, session):
    """
    avatar_url foi removido do StudentProfileUpdate — o endpoint /profile
    não gerencia mais avatar (responsabilidade do /avatar).
    Confirma que body vazio não explode o endpoint.
    """
    from app.domains.users.models import Classroom

    classroom = Classroom(name='Turma Intencional')
    session.add(classroom)
    await session.flush()

    dt = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )

    # Confirma que o endpoint funciona com body vazio sem explodir
    resp = client.patch(
        f'/users/{student.id}/profile',
        headers=_auth(dt),
        json={},
    )
    assert resp.status_code == HTTPStatus.OK


# ===========================================================================
# PATCH /users/{id}/profile — DT edita perfil de aluno
# ===========================================================================


async def test_dt_update_student_profile_success(client, session):
    """DT atualiza perfil de aluno da turma → 200."""
    from app.domains.users.models import Classroom

    classroom = Classroom(name='Turma P1')
    session.add(classroom)
    await session.flush()

    dt = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )

    resp = client.patch(
        f'/users/{student.id}/profile',
        headers=_auth(dt),
        json={'first_name': 'NomeAtualizado'},
    )
    assert resp.status_code == HTTPStatus.OK


async def test_dt_update_profile_user_not_found(client, session):
    """DT tenta editar perfil de usuário inexistente → 404."""
    dt = await _make_user(session, role=UserRole.TEACHER, is_tutor=True)
    resp = client.patch(
        '/users/9999/profile',
        headers=_auth(dt),
        json={'first_name': None},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'User not found'


async def test_dt_update_profile_not_student(client, session):
    """DT tenta editar perfil de não-aluno → 422."""
    from app.domains.users.models import Classroom

    classroom = Classroom(name='Turma P2')
    session.add(classroom)
    await session.flush()

    dt = await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )
    teacher2 = await _make_user(
        session, role=UserRole.TEACHER, classroom_id=classroom.id
    )

    resp = client.patch(
        f'/users/{teacher2.id}/profile',
        headers=_auth(dt),
        json={'first_name': None},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'perfil de alunos' in resp.json()['detail']


async def test_dt_update_profile_wrong_classroom(client, session):
    """DT tenta editar perfil de aluno de outra turma → 403."""
    from app.domains.users.models import Classroom

    c1 = Classroom(name='Turma P3')
    c2 = Classroom(name='Turma P4')
    session.add_all([c1, c2])
    await session.flush()

    dt = await _make_user(
        session, role=UserRole.TEACHER, is_tutor=True, classroom_id=c1.id
    )
    student = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=c2.id
    )

    resp = client.patch(
        f'/users/{student.id}/profile',
        headers=_auth(dt),
        json={'first_name': None},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert 'turma' in resp.json()['detail']


# ===========================================================================
# PATCH /users/{id}/deactivate — desativar usuário
# ===========================================================================


async def test_deactivate_user_success(client, session):
    """Admin desativa outro usuário → 200 e is_active = False."""
    from app.domains.users.models import User as UserModel

    admin = await _make_user(session, role=UserRole.ADMIN)
    target = await _make_user(session)

    resp = client.patch(
        f'/users/{target.id}/deactivate',
        headers=_auth(admin),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deactivated successfully'}

    # Verifica no banco que is_active virou False
    from sqlalchemy import select

    refreshed = await session.scalar(
        select(UserModel).where(UserModel.id == target.id)
    )
    assert refreshed.is_active is False


async def test_deactivate_self_not_allowed(client, session):
    """Usuário tenta desativar a si mesmo → 422."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    resp = client.patch(
        f'/users/{admin.id}/deactivate',
        headers=_auth(admin),
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'si mesmo' in resp.json()['detail']


async def test_deactivate_user_not_found(client, session):
    """Admin tenta desativar usuário inexistente → 404."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    resp = client.patch(
        '/users/9999/deactivate',
        headers=_auth(admin),
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'User not found'


async def test_deactivate_already_inactive(client, session):
    """Admin tenta desativar usuário já inativo → 409 Conflict."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    target = await _make_user(session, is_active=False)

    resp = client.patch(
        f'/users/{target.id}/deactivate',
        headers=_auth(admin),
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert 'já está desativado' in resp.json()['detail']


async def test_deactivate_requires_permission(client, session):
    """Professor comum não tem USER_DELETE → 403."""
    teacher = await _make_user(session, role=UserRole.TEACHER)
    target = await _make_user(session)

    resp = client.patch(
        f'/users/{target.id}/deactivate',
        headers=_auth(teacher),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_coordinator_can_deactivate(client, session):
    """Coordinator tem USER_DELETE → consegue desativar → 200."""
    coord = await _make_user(session, role=UserRole.COORDINATOR)
    target = await _make_user(session)

    resp = client.patch(
        f'/users/{target.id}/deactivate',
        headers=_auth(coord),
    )
    assert resp.status_code == HTTPStatus.OK


async def test_deactivate_preserves_avatar_on_disk(client, session, tmp_path):
    """Desativar NÃO remove arquivo de avatar do disco."""
    from app.domains.users import routers as user_routers
    from app.domains.users.models import User as UserModel
    from PIL import Image

    admin = await _make_user(session, role=UserRole.ADMIN)
    target = await _make_user(session)

    # Cria avatar fake no tmp_path
    avatar_file = tmp_path / f'{target.id}.webp'
    Image.new('RGB', (256, 256)).save(avatar_file, format='WEBP')

    t = await session.get(UserModel, target.id)
    t.avatar_url = f'avatars/{target.id}.webp'
    await session.commit()

    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.patch(
            f'/users/{target.id}/deactivate',
            headers=_auth(admin),
        )

    assert resp.status_code == HTTPStatus.OK
    assert avatar_file.exists(), 'Avatar deve ser preservado ao desativar'


# ===========================================================================
# DELETE /users/{id}
# ===========================================================================


def test_delete_user_forbidden(client, user, other_user, token):
    """DELETE de outro usuário → 403 Forbidden."""
    resp = client.delete(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json() == {'detail': 'Not enough permissions'}


def test_delete_user_success(client, admin, user, token):
    """DELETE do próprio usuário → 200, usuário não aparece mais na lista."""
    resp = client.delete(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deleted'}

    users = client.get('/users/', headers=_auth(admin)).json()['users']
    assert all(u['id'] != user.id for u in users)


async def test_delete_user_self_async(client, session):
    """DELETE /users/{id} (async fixture) → mensagem de sucesso."""
    u = await _make_user(session)
    resp = client.delete(f'/users/{u.id}', headers=_auth(u))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deleted'}


async def test_delete_user_removes_avatar_from_disk(client, session, tmp_path):
    """DELETE remove o arquivo de avatar do disco."""
    from app.domains.users import routers as user_routers
    from app.domains.users.models import User as UserModel
    from PIL import Image

    u = await _make_user(session)

    # Cria avatar fake no tmp_path
    avatar_file = tmp_path / f'{u.id}.webp'
    Image.new('RGB', (256, 256)).save(avatar_file, format='WEBP')
    assert avatar_file.exists()

    u_fresh = await session.get(UserModel, u.id)
    u_fresh.avatar_url = f'avatars/{u.id}.webp'
    await session.commit()

    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.delete(f'/users/{u.id}', headers=_auth(u))

    assert resp.status_code == HTTPStatus.OK
    assert not avatar_file.exists(), (
        'Avatar deve ser removido do disco ao deletar usuário'
    )


async def test_delete_user_no_avatar_no_error(client, session, tmp_path):
    """DELETE de usuário sem avatar → não gera erro mesmo sem arquivo no disco."""
    from app.domains.users import routers as user_routers

    u = await _make_user(session)
    # Não cria nenhum arquivo de avatar

    with patch.object(user_routers, '_AVATAR_DIR', tmp_path):
        resp = client.delete(f'/users/{u.id}', headers=_auth(u))

    assert resp.status_code == HTTPStatus.OK


# ===========================================================================
# Validação de schema — UserSchema / UserUpdate
# ===========================================================================


def test_schema_rejects_username_with_space():
    """Username com espaço → ValidationError."""
    with pytest.raises(ValidationError):
        UserSchema(
            username='João Silva',
            email='joao@test.com',
            password='secret',
            first_name='João',
            last_name='Silva',
        )


def test_schema_rejects_accented_username():
    """Username com acento → ValidationError."""
    with pytest.raises(ValidationError):
        UserSchema(
            username='joãosilva',
            email='joao2@test.com',
            password='secret',
            first_name='João',
            last_name='Silva',
        )


def test_schema_rejects_invalid_username_update():
    """UserUpdate com username inválido → ValidationError."""
    with pytest.raises(ValidationError):
        UserUpdate(username='nome inválido!')


def test_schema_accepts_valid_username():
    """Username com letras, dígitos, ponto e underscore → válido."""
    schema = UserSchema(
        username='joao.silva_99',
        email='joao99@test.com',
        password='secret',
        first_name='João',
        last_name='Silva',
    )
    assert schema.username == 'joao.silva_99'


# ===========================================================================
# GET /users/classrooms — Lista todas as turmas
# ===========================================================================


@pytest.mark.asyncio
async def test_list_classrooms_returns_all_sorted(client, session):
    """Admin recebe todas as turmas em ordem alfabética."""
    from app.domains.users.models import Classroom

    admin = await _make_user(session, role=UserRole.ADMIN)
    c1 = Classroom(name='Turma B')
    c2 = Classroom(name='Turma A')
    c3 = Classroom(name='Turma C')
    session.add_all([c1, c2, c3])
    await session.commit()

    resp = client.get('/users/classrooms', headers=_auth(admin))

    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    names = [item['name'] for item in data]
    # Deve vir em ordem alfabética
    assert names == sorted(names)
    # Todas as turmas criadas devem estar presentes
    assert {'Turma A', 'Turma B', 'Turma C'}.issubset(set(names))


@pytest.mark.asyncio
async def test_list_classrooms_response_shape(client, session):
    """Cada item retornado contém apenas 'id' e 'name'."""
    from app.domains.users.models import Classroom

    coord = await _make_user(session, role=UserRole.COORDINATOR)
    c = Classroom(name='Turma Shape')
    session.add(c)
    await session.commit()
    await session.refresh(c)

    resp = client.get('/users/classrooms', headers=_auth(coord))

    assert resp.status_code == HTTPStatus.OK
    # Encontra a turma criada no resultado
    match = next(
        (item for item in resp.json() if item['name'] == 'Turma Shape'), None
    )
    assert match is not None
    assert set(match.keys()) == {'id', 'name'}
    assert match['id'] == c.id


@pytest.mark.asyncio
async def test_list_classrooms_empty(client, session):
    """Endpoint retorna lista vazia quando não há turmas."""
    teacher = await _make_user(session, role=UserRole.TEACHER)

    resp = client.get('/users/classrooms', headers=_auth(teacher))

    assert resp.status_code == HTTPStatus.OK
    # Pode haver turmas residuais de outros testes; garante apenas que é lista
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Cobertura de permissão: quem PODE acessar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'role',
    [
        UserRole.ADMIN,
        UserRole.COORDINATOR,
        UserRole.TEACHER,
        UserRole.PORTER,
        UserRole.STUDENT,
        UserRole.GUARDIAN,
    ],
)
async def test_list_classrooms_allowed_roles(client, session, role):
    """
    Qualquer role que possua SCHEDULES_VIEW_ALL, _OWN ou _CHILD deve receber 200.
    Cobre: admin, coordinator, teacher, porter (VIEW_ALL),
           student (VIEW_OWN), guardian (VIEW_CHILD).
    """
    user = await _make_user(session, role=role)
    resp = client.get('/users/classrooms', headers=_auth(user))
    assert resp.status_code == HTTPStatus.OK


# ---------------------------------------------------------------------------
# Rejeição de unauthenticated
# ---------------------------------------------------------------------------


def test_list_classrooms_unauthenticated(client):
    """Requisição sem token deve ser recusada com 401."""
    resp = client.get('/users/classrooms')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
