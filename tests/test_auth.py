"""
Testes de auth/routers.py e shared/security.py.

Endpoints:
  POST /auth/token          — login
  POST /auth/logout         — logout
  POST /auth/refresh_token  — renovação de tokens
  GET  /auth/me             — perfil do usuário logado
  GET  /auth/me/permissions — permissões do usuário logado
  GET  /auth/admin          — rota restrita por role

Módulo compartilhado:
  shared/security.py — get_current_user (token sem sub, inativo, inexistente)
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from zoneinfo import ZoneInfo

import jwt as pyjwt

from app.core.settings import settings
from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token, create_refresh_token
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ===========================================================================
# POST /auth/token — Login
# ===========================================================================


async def test_login_success(client, session):
    """Credenciais corretas → 200, access_token no corpo, cookie de refresh."""
    user = await _make_user(session)
    resp = client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'access_token' in body
    assert body['token_type'] == 'bearer'
    assert 'must_change_password' in body


async def test_login_wrong_password(client, session):
    """Senha errada → 401 com mensagem genérica."""
    user = await _make_user(session)
    resp = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'senha_errada'},
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Incorrect email or password'}


def test_login_unknown_email(client):
    """E-mail inexistente → 401 (mesmo detalhe — não vaza enumeração)."""
    resp = client.post(
        '/auth/token',
        data={'username': 'naoexiste@test.com', 'password': 'qualquer'},
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json()['detail'] == 'Incorrect email or password'


# ===========================================================================
# POST /auth/logout
# ===========================================================================


def test_logout_clears_cookie(client):
    """Logout → 200 e mensagem de confirmação."""
    resp = client.post('/auth/logout')
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'message': 'Logout successful'}


# ===========================================================================
# POST /auth/refresh_token
# ===========================================================================


def test_refresh_missing_cookie(client):
    """Sem cookie refresh_token → 401."""
    resp = client.post('/auth/refresh_token')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Could not validate credentials'}


def test_refresh_invalid_token(client):
    """Cookie com valor malformado (DecodeError) → 401."""
    resp = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': 'token.invalido.aqui'},
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_expired_token(client):
    """Token expirado (ExpiredSignatureError) → 401."""
    payload = {
        'sub': 'alguem@test.com',
        'exp': datetime.now(tz=ZoneInfo('UTC')) - timedelta(minutes=1),
    }
    expired = pyjwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    resp = client.post(
        '/auth/refresh_token', cookies={'refresh_token': expired}
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_token_without_sub(client):
    """Token válido mas sem campo 'sub' → 401."""
    payload = {
        'exp': datetime.now(tz=ZoneInfo('UTC')) + timedelta(minutes=30),
        'data': 'sem_sub',
    }
    token = pyjwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    resp = client.post('/auth/refresh_token', cookies={'refresh_token': token})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Could not validate credentials'}


def test_refresh_user_not_in_db(client):
    """Sub válido mas usuário não existe no banco → 401."""
    token = create_refresh_token(data={'sub': 'fantasma@inexistente.com'})
    resp = client.post('/auth/refresh_token', cookies={'refresh_token': token})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Could not validate credentials'}


async def test_refresh_success(client, session):
    """Cookie válido com usuário existente → 200 com novo access_token."""
    user = await _make_user(session)
    token = create_refresh_token(data={'sub': user.email})
    resp = client.post('/auth/refresh_token', cookies={'refresh_token': token})
    assert resp.status_code == HTTPStatus.OK
    assert 'access_token' in resp.json()


# ===========================================================================
# GET /auth/me
# ===========================================================================


async def test_get_me_returns_current_user(client, session):
    """Usuário autenticado → 200 com seus próprios dados."""
    user = await _make_user(session)
    resp = client.get('/auth/me', headers=_auth(user))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == user.id


def test_get_me_unauthenticated(client):
    """Sem token → 401."""
    resp = client.get('/auth/me')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# GET /auth/me/permissions
# ===========================================================================


async def test_get_me_permissions_returns_list(client, session):
    """Retorna dados públicos + lista de permissões do usuário."""
    user = await _make_user(session, role=UserRole.TEACHER)
    resp = client.get('/auth/me/permissions', headers=_auth(user))
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert 'permissions' in body
    assert isinstance(body['permissions'], list)
    assert len(body['permissions']) > 0


async def test_get_me_permissions_student(client, session):
    """Aluno tem permissões de aluno na lista."""
    user = await _make_user(session, role=UserRole.STUDENT)
    resp = client.get('/auth/me/permissions', headers=_auth(user))
    assert resp.status_code == HTTPStatus.OK
    assert 'permissions' in resp.json()


# ===========================================================================
# GET /auth/admin
# ===========================================================================


async def test_admin_coordinator_allowed(client, session):
    """Coordenador acessa /auth/admin → 200."""
    coord = await _make_user(session, role=UserRole.COORDINATOR)
    resp = client.get('/auth/admin', headers=_auth(coord))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == coord.id


async def test_admin_admin_allowed(client, session):
    """Admin acessa /auth/admin → 200."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    resp = client.get('/auth/admin', headers=_auth(admin))
    assert resp.status_code == HTTPStatus.OK


async def test_admin_teacher_forbidden(client, session):
    """Professor tenta acessar /auth/admin → 403."""
    teacher = await _make_user(session, role=UserRole.TEACHER)
    resp = client.get('/auth/admin', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.FORBIDDEN


async def test_admin_student_forbidden(client, session):
    """Aluno tenta acessar /auth/admin → 403."""
    student = await _make_user(session, role=UserRole.STUDENT)
    resp = client.get('/auth/admin', headers=_auth(student))
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# shared/security.py — get_current_user
# ===========================================================================


def test_token_without_sub(client):
    """JWT válido sem campo 'sub' → 401."""
    token = create_access_token(data={'data': 'sem_sub'})
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Could not validate credentials'}


def test_jwt_encode_decode():
    """create_access_token gera JWT decodificável com 'exp'."""
    from jwt import decode

    data = {'test': 'value'}
    token = create_access_token(data)
    decoded = decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert decoded['test'] == data['test']
    assert 'exp' in decoded


def test_invalid_token_returns_401(client):
    """Token completamente inválido → 401."""
    resp = client.delete(
        '/users/1', headers={'Authorization': 'Bearer token-invalido'}
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert resp.json() == {'detail': 'Could not validate credentials'}


def test_deleted_user_token_returns_401(client, user, token):
    """Token válido de usuário que foi deletado → 401."""
    client.delete(
        f'/users/{user.id}', headers={'Authorization': f'Bearer {token}'}
    )
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_inactive_user_returns_403(client, session):
    """Usuário inativo → 403 Inactive user."""
    inactive = await _make_user(session, is_active=False)
    token = create_access_token(data={'sub': inactive.email})
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Inactive user'


async def test_active_user_returns_200(client, session):
    """Usuário ativo com token válido → 200."""
    user = await _make_user(session)
    resp = client.get('/auth/me', headers=_auth(user))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == user.id
