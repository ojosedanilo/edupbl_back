"""
Testes de auth/routers.py e shared/security.py — cobertura completa.

Cobre:
  auth/routers.py      107-113 (login senha errada)
                       170     (refresh sem 'sub')
                       181     (refresh user inexistente)
                       192     (GET /me)
                       203-205 (GET /me/permissions)
  shared/security.py   138     (usuário inativo → 403)
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


async def test_login_success_returns_token(client, session):
    """POST /auth/token com credenciais corretas → 200 com access_token."""
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


async def test_login_wrong_password_401(client, session):
    """auth line 108: senha errada → 401 com mensagem genérica."""
    user = await _make_user(session)
    response = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'senha_errada'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Incorrect email or password'}


async def test_login_unknown_email_401(client):
    """POST /auth/token com e-mail inexistente → 401 (branch not user)."""
    response = client.post(
        '/auth/token',
        data={'username': 'naoexiste@test.com', 'password': 'qualquer'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail'] == 'Incorrect email or password'


# ===========================================================================
# POST /auth/logout
# ===========================================================================


def test_logout_success(client):
    """POST /auth/logout → 200 e mensagem de confirmação."""
    response = client.post('/auth/logout')
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Logout successful'}


# ===========================================================================
# POST /auth/refresh_token — todos os branches
# ===========================================================================


def test_refresh_token_missing_cookie_401(client):
    """Sem cookie refresh_token → 401."""
    response = client.post('/auth/refresh_token')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_refresh_token_invalid_token_401(client):
    """Cookie com valor inválido (DecodeError) → 401."""
    response = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': 'token.invalido.aqui'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_refresh_token_expired_401(client):
    """Cookie com token expirado (ExpiredSignatureError) → 401."""
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


def test_refresh_token_no_sub_401(client):
    """auth line 170: token sem campo 'sub' → 401."""
    payload = {
        'exp': datetime.now(tz=ZoneInfo('UTC')) + timedelta(minutes=30),
        'data': 'sem_sub',
    }
    token = pyjwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    response = client.post(
        '/auth/refresh_token', cookies={'refresh_token': token}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_refresh_token_user_not_found_401(client):
    """auth line 181: sub válido mas usuário inexistente no banco → 401."""
    token = create_refresh_token(data={'sub': 'fantasma@inexistente.com'})
    response = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': token},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


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


# ===========================================================================
# GET /auth/me — linha 192
# ===========================================================================


async def test_get_me_returns_user(client, session):
    """auth line 192: GET /auth/me → 200 com dados do usuário autenticado."""
    user = await _make_user(session)
    response = client.get('/auth/me', headers=_auth(user))
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == user.id


async def test_get_me_unauthenticated_401(client):
    """GET /auth/me sem token → 401."""
    response = client.get('/auth/me')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


# ===========================================================================
# GET /auth/me/permissions — linhas 203-205
# ===========================================================================


async def test_get_me_permissions_returns_list(client, session):
    """auth lines 203-205: GET /auth/me/permissions → 200 com permissions."""
    user = await _make_user(session, role=UserRole.TEACHER)
    response = client.get('/auth/me/permissions', headers=_auth(user))
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert 'permissions' in body
    assert isinstance(body['permissions'], list)
    assert len(body['permissions']) > 0


async def test_get_me_permissions_student(client, session):
    """GET /auth/me/permissions para aluno → lista de permissões de aluno."""
    user = await _make_user(session, role=UserRole.STUDENT)
    response = client.get('/auth/me/permissions', headers=_auth(user))
    assert response.status_code == HTTPStatus.OK
    assert 'permissions' in response.json()


# ===========================================================================
# GET /auth/admin — controle de role
# ===========================================================================


async def test_admin_endpoint_coordinator_allowed(client, session):
    """Coordenador acessa /auth/admin → 200."""
    coord = await _make_user(session, role=UserRole.COORDINATOR)
    response = client.get('/auth/admin', headers=_auth(coord))
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == coord.id


async def test_admin_endpoint_admin_allowed(client, session):
    """Admin acessa /auth/admin → 200."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    response = client.get('/auth/admin', headers=_auth(admin))
    assert response.status_code == HTTPStatus.OK


async def test_admin_endpoint_teacher_forbidden(client, session):
    """Professor tenta acessar /auth/admin → 403."""
    teacher = await _make_user(session, role=UserRole.TEACHER)
    response = client.get('/auth/admin', headers=_auth(teacher))
    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_admin_endpoint_student_forbidden(client, session):
    """Aluno tenta acessar /auth/admin → 403."""
    student = await _make_user(session, role=UserRole.STUDENT)
    response = client.get('/auth/admin', headers=_auth(student))
    assert response.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# shared/security.py — get_current_user branches
# ===========================================================================


def test_token_without_sub_returns_401(client):
    """Token JWT válido mas sem campo 'sub' → 401."""
    token = create_access_token(data={'data': 'sem_sub'})
    response = client.get(
        '/auth/me',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_token_deleted_user_returns_401(client, user, token):
    """Token válido de usuário que foi deletado → 401."""
    client.delete(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    response = client.get(
        '/auth/me',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


async def test_security_inactive_user_403(client, session):
    """security line 138: usuário inativo → 403 Inactive user."""
    inactive = await _make_user(session, is_active=False)
    token = create_access_token(data={'sub': inactive.email})
    response = client.get(
        '/auth/me', headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Inactive user'


async def test_security_active_user_returns_200(client, session):
    """security line 142: return user → rota retorna 200."""
    user = await _make_user(session)
    response = client.get('/auth/me', headers=_auth(user))
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == user.id
