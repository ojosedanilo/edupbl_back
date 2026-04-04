"""
Testes de users/routers.py — cobertura completa.

Cobre:
  users/routers.py  65-91, 108, 147-148, 161-162, 191, 218
"""

from http import HTTPStatus

from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ===========================================================================
# POST /users/ — criação
# ===========================================================================


async def test_create_user_username_conflict(client, session):
    """lines 65-70: POST /users/ → username duplicado → 409."""
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


async def test_create_user_email_conflict(client, session):
    """lines 71-74: POST /users/ → email duplicado → 409."""
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


async def test_create_user_success_and_read(client):
    """lines 76-91, 108: POST /users/ sucesso + GET /users/ retorna lista."""
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
    assert list_resp.status_code == HTTPStatus.OK
    ids = [u['id'] for u in list_resp.json()['users']]
    assert user_id in ids


# ===========================================================================
# PUT /users/{id} — atualização
# ===========================================================================


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
    """lines 147-148: PUT /users/{id} → username de outro → 409."""
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
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'email': u.email},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK


async def test_update_user_returns_updated(client, session):
    """lines 161-162: PUT /users/{id} → commit + return → 200."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'first_name': 'NomeNovo'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['first_name'] == 'NomeNovo'


async def test_update_user_password_is_hashed(client, session):
    """PUT /users/{id} com campo password → é salvo hasheado."""
    u = await _make_user(session)
    resp = client.put(
        f'/users/{u.id}',
        json={'password': 'novaSenha!'},
        headers=_auth(u),
    )
    assert resp.status_code == HTTPStatus.OK
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


# ===========================================================================
# PATCH /users/me/password
# ===========================================================================


async def test_change_password_success_message(client, session):
    """line 191: PATCH /me/password → return message."""
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


async def test_delete_user_self_success_message(client, session):
    """line 218: DELETE /users/{id} → return message."""
    u = await _make_user(session)
    resp = client.delete(f'/users/{u.id}', headers=_auth(u))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'User deleted'}


# ===========================================================================
# GET /users/ — paginação
# ===========================================================================


async def test_read_users_with_pagination(client, session):
    """GET /users/?limit=1&offset=0 → paginação funcionando."""
    await _make_user(session)
    await _make_user(session)
    resp = client.get('/users/?limit=1&offset=0')
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['users']) == 1
