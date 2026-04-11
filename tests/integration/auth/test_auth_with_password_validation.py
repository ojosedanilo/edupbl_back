"""
Testes de integração: validação de senha nos endpoints de autenticação.

Usa o padrão TestClient + fixtures do conftest principal (engine/session/client).
"""

from http import HTTPStatus

import pytest

from app.shared.rbac.roles import UserRole
from app.shared.security import get_password_hash


# ── HELPERS ──────────────────────────────────────────────────────────────── #


async def _create_user(
    session, *, email, password, first_name='Test', last_name='User'
):
    """Cria um usuário diretamente na sessão de teste."""
    from app.domains.users.models import User

    user = User(
        email=email,
        username=email.split('@')[0],
        password=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole.STUDENT,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _auth_headers(client, *, email, password):
    """Faz login e retorna headers de autorização."""
    resp = client.post(
        '/auth/token',
        data={'username': email, 'password': password},
    )
    assert resp.status_code == HTTPStatus.OK, resp.json()
    token = resp.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


# ── POST /users — criação com senha fraca ────────────────────────────────── #


@pytest.mark.asyncio
async def test_create_user_with_weak_password(client, session):
    """Criar usuário com senha fraca (123456) deve retornar 400."""
    admin = await _create_user(
        session,
        email='admin@test.com',
        password='Admin@Str0ng#Pass!',
        first_name='Admin',
        last_name='User',
    )
    admin.role = UserRole.ADMIN
    await session.commit()

    headers = _auth_headers(
        client, email='admin@test.com', password='Admin@Str0ng#Pass!'
    )

    response = client.post(
        '/users/',
        json={
            'email': 'new@test.com',
            'username': 'newuser',
            'password': '123456',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'student',
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = response.json()
    assert data['detail']['valid'] is False
    assert 'min_length' in data['detail']['errors']


@pytest.mark.asyncio
async def test_create_user_with_strong_password(client, session):
    """Criar usuário com senha forte deve retornar 201."""
    admin = await _create_user(
        session,
        email='admin2@test.com',
        password='Admin@Str0ng#Pass!',
        first_name='Admin',
        last_name='User',
    )
    admin.role = UserRole.ADMIN
    await session.commit()

    headers = _auth_headers(
        client, email='admin2@test.com', password='Admin@Str0ng#Pass!'
    )

    response = client.post(
        '/users/',
        json={
            'email': 'strong@test.com',
            'username': 'stronguser',
            'password': 'MyStr0ng@Passw0rd!XY',
            'first_name': 'Strong',
            'last_name': 'User',
            'role': 'student',
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED


# ── POST /auth/change-password ───────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_change_password_reuse_old(client, session):
    """Tentar reutilizar a senha antiga deve retornar 400."""
    old_password = 'OldStr0ng@Pass#123'
    await _create_user(
        session,
        email='change@test.com',
        password=old_password,
        first_name='Change',
        last_name='User',
    )

    headers = _auth_headers(
        client, email='change@test.com', password=old_password
    )

    response = client.post(
        '/auth/change-password',
        params={
            'old_password': old_password,
            'new_password': old_password,  # mesma senha
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = response.json()
    assert 'same_as_old' in data['detail']['errors']


@pytest.mark.asyncio
async def test_change_password_with_weak_new_password(client, session):
    """Tentar mudar para senha fraca deve retornar 400."""
    old_password = 'OldStr0ng@Pass#456'
    await _create_user(
        session,
        email='change2@test.com',
        password=old_password,
    )

    headers = _auth_headers(
        client, email='change2@test.com', password=old_password
    )

    response = client.post(
        '/auth/change-password',
        params={
            'old_password': old_password,
            'new_password': '123456',
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = response.json()
    assert data['detail']['valid'] is False


@pytest.mark.asyncio
async def test_change_password_success(client, session):
    """Trocar senha por uma forte e diferente deve funcionar."""
    old_password = 'OldStr0ng@Pass#789'
    await _create_user(
        session,
        email='change3@test.com',
        password=old_password,
    )

    headers = _auth_headers(
        client, email='change3@test.com', password=old_password
    )

    response = client.post(
        '/auth/change-password',
        params={
            'old_password': old_password,
            'new_password': 'NewStr0ng@Pass#Xyz!',
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'Senha alterada com sucesso'


@pytest.mark.asyncio
async def test_change_password_wrong_old_password(client, session):
    """Fornecer senha atual errada deve retornar 401."""
    await _create_user(
        session,
        email='change4@test.com',
        password='OldStr0ng@Pass#000',
    )

    headers = _auth_headers(
        client, email='change4@test.com', password='OldStr0ng@Pass#000'
    )

    response = client.post(
        '/auth/change-password',
        params={
            'old_password': 'SenhaErrada@123!',
            'new_password': 'NewStr0ng@Pass#Xyz!',
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
