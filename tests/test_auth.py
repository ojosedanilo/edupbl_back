"""
Testes complementares para auth/routers.py.

Gaps cobertos:
- POST /auth/logout -> limpa cookie
- POST /auth/refresh_token -> sem cookie (401), DecodeError (401),
  usuario inexistente (401)
- GET  /auth/admin -> role autorizada (200), role nao autorizada (403)
"""

from http import HTTPStatus

import pytest

from app.shared.rbac.roles import UserRole
from app.shared.security import create_refresh_token
from tests.conftest import _make_user, make_token

# --------------------------------------------------------------------------- #
# POST /auth/logout                                                           #
# --------------------------------------------------------------------------- #


def test_logout_success(client):
    """POST /auth/logout -> 200 e mensagem de confirmacao."""
    response = client.post('/auth/logout')
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Logout successful'}


# --------------------------------------------------------------------------- #
# POST /auth/refresh_token - casos de erro                                   #
# --------------------------------------------------------------------------- #


def test_refresh_token_missing_cookie(client):
    """Sem cookie refresh_token -> 401."""
    response = client.post('/auth/refresh_token')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_refresh_token_invalid_token(client):
    """Cookie com valor invalido (DecodeError) -> 401."""
    response = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': 'token.invalido.aqui'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_refresh_token_user_not_found(client):
    """
    Token valido mas sub aponta para email inexistente -> 401.
    Cobre o branch onde session.scalar retorna None.
    """
    token = create_refresh_token(data={'sub': 'fantasma@inexistente.com'})
    response = client.post(
        '/auth/refresh_token',
        cookies={'refresh_token': token},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


# --------------------------------------------------------------------------- #
# GET /auth/admin - controle de role                                         #
# --------------------------------------------------------------------------- #


async def test_admin_endpoint_coordinator_allowed(client, session):
    """Coordenador acessa /auth/admin -> 200."""
    coord = await _make_user(session, role=UserRole.COORDINATOR)
    response = client.get(
        '/auth/admin',
        headers={'Authorization': f'Bearer {make_token(coord)}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == coord.id


async def test_admin_endpoint_admin_allowed(client, session):
    """Admin acessa /auth/admin -> 200."""
    admin = await _make_user(session, role=UserRole.ADMIN)
    response = client.get(
        '/auth/admin',
        headers={'Authorization': f'Bearer {make_token(admin)}'},
    )
    assert response.status_code == HTTPStatus.OK


async def test_admin_endpoint_teacher_forbidden(client, session):
    """Professor tenta acessar /auth/admin -> 403."""
    teacher = await _make_user(session, role=UserRole.TEACHER)
    response = client.get(
        '/auth/admin',
        headers={'Authorization': f'Bearer {make_token(teacher)}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_admin_endpoint_student_forbidden(client, session):
    """Aluno tenta acessar /auth/admin -> 403."""
    student = await _make_user(session, role=UserRole.STUDENT)
    response = client.get(
        '/auth/admin',
        headers={'Authorization': f'Bearer {make_token(student)}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
