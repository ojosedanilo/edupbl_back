"""
Testes de users/routers.py e users/schemas.py.

Endpoints:
  POST   /users/             — criação
  GET    /users/             — listagem paginada
  PUT    /users/{id}         — atualização
  PATCH  /users/me/password  — troca de senha
  DELETE /users/{id}         — deleção
"""

from http import HTTPStatus

import pytest
from pydantic import ValidationError

from app.domains.users.schemas import UserSchema, UserUpdate
from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ===========================================================================
# POST /users/ — criação
# ===========================================================================


def test_create_user_success(client):
    """Dados válidos → 201 com campos corretos, senha nunca exposta."""
    resp = client.post(
        '/users/',
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


def test_create_user_duplicate_username(client, user):
    """Username já existente → 409 Conflict."""
    resp = client.post(
        '/users/',
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


def test_create_user_duplicate_email(client, user):
    """E-mail já existente → 409 Conflict."""
    resp = client.post(
        '/users/',
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


async def test_create_user_username_conflict_async(client, session):
    """Username duplicado via _make_user (async) → 409."""
    existing = await _make_user(session)
    resp = client.post(
        '/users/',
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


async def test_create_user_email_conflict_async(client, session):
    """Email duplicado via _make_user (async) → 409."""
    existing = await _make_user(session)
    resp = client.post(
        '/users/',
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


def test_create_user_api_invalid_username(client):
    """Username inválido via API → 422 Unprocessable Entity."""
    resp = client.post(
        '/users/',
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


def test_read_users_returns_list(client, user):
    """GET /users/ → lista com o usuário existente."""
    resp = client.get('/users/')
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'users' in body
    assert user.id in [u['id'] for u in body['users']]


def test_read_users_empty(client):
    """GET /users/ sem usuários → lista vazia."""
    resp = client.get('/users/')
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'users': []}


async def test_read_users_with_pagination(client, session):
    """GET /users/?limit=1 → retorna exatamente 1 usuário."""
    await _make_user(session)
    await _make_user(session)
    resp = client.get('/users/?limit=1&offset=0')
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['users']) == 1


async def test_create_and_read_user(client):
    """POST /users/ + GET /users/ → novo usuário aparece na lista."""
    resp = client.post(
        '/users/',
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

    list_resp = client.get('/users/')
    ids = [u['id'] for u in list_resp.json()['users']]
    assert user_id in ids


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


def test_delete_user_success(client, user, token):
    """DELETE do próprio usuário → 200, usuário não aparece mais na lista."""
    resp = client.delete(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deleted'}

    users = client.get('/users/').json()['users']
    assert all(u['id'] != user.id for u in users)


async def test_delete_user_self_async(client, session):
    """DELETE /users/{id} (async fixture) → mensagem de sucesso."""
    u = await _make_user(session)
    resp = client.delete(f'/users/{u.id}', headers=_auth(u))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deleted'}


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
