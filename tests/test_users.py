"""
Testes adicionais para cobertura de users/routers.py e users/schemas.py.

Gaps cobertos:
- POST /users/  → conflito de username, conflito de email, criação ok
- GET  /users/  → listagem paginada
- PUT  /users/  → atualização com conflito, atualização de senha,
  outros campos
- PATCH /me/password → senha atual errada, senha trocada com sucesso
- DELETE /users/ → deleção própria bem-sucedida
- UserSchema / UserUpdate → username inválido (acento / char proibido)
"""

from http import HTTPStatus

import pytest
from pydantic import ValidationError

from app.domains.users.schemas import UserSchema, UserUpdate
from app.shared.rbac.roles import UserRole

# --------------------------------------------------------------------------- #
# POST /users/ — conflitos e criação                                         #
# --------------------------------------------------------------------------- #


def test_create_user_duplicate_username(client, user):
    """Tenta criar usuário com username já existente → 409 Conflict."""
    response = client.post(
        '/users/',
        json={
            'username': user.username,  # mesmo username
            'email': 'outro@example.com',
            'password': 'secret123',
            'first_name': 'Outro',
            'last_name': 'Usuário',
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_duplicate_email(client, user):
    """Tenta criar usuário com e-mail já existente → 409 Conflict."""
    response = client.post(
        '/users/',
        json={
            'username': 'outrouser',
            'email': user.email,  # mesmo e-mail
            'password': 'secret123',
            'first_name': 'Outro',
            'last_name': 'Usuário',
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Email already exists'}


def test_create_user_success(client):
    """Cria usuário com dados válidos → 201 Created com dados corretos."""
    response = client.post(
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
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['username'] == 'novousuario'
    assert data['email'] == 'novo@example.com'
    assert data['role'] == UserRole.TEACHER.value
    assert data['is_active'] is True
    assert 'password' not in data  # senha nunca exposta


# --------------------------------------------------------------------------- #
# GET /users/ — listagem paginada                                            #
# --------------------------------------------------------------------------- #


def test_read_users_returns_list(client, user):
    """GET /users/ deve retornar lista com o usuário existente."""
    response = client.get('/users/')
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert 'users' in body
    assert len(body['users']) >= 1
    ids = [u['id'] for u in body['users']]
    assert user.id in ids


def test_read_users_empty(client):
    """GET /users/ sem usuários no banco → lista vazia."""
    response = client.get('/users/')
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'users': []}


# --------------------------------------------------------------------------- #
# PUT /users/{id} — atualização                                              #
# --------------------------------------------------------------------------- #


def test_update_user_forbidden(client, user, other_user, token):
    """PUT /users/{outro_id} → 403 Forbidden."""
    response = client.put(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'first_name': 'Invasor'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permissions'}


def test_update_user_conflict_username(client, user, other_user, token):
    """PUT com username já usado por outro usuário → 409."""
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'username': other_user.username},
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username or Email already exists'}


def test_update_user_conflict_email(client, user, other_user, token):
    """PUT com email já usado por outro usuário → 409."""
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'email': other_user.email},
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username or Email already exists'}


def test_update_user_password_only(client, user, token):
    """PUT /users/{id} com apenas senha → atualiza sem erro."""
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'password': 'novasenha123'},
    )
    assert response.status_code == HTTPStatus.OK
    # Confirma que o login com a nova senha funciona
    login = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'novasenha123'},
    )
    assert login.status_code == HTTPStatus.OK


def test_update_user_non_conflicting_fields(client, user, token):
    """PUT /users/{id} com username/email que não colidem → 200 OK."""
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'uniqueuser99',
            'email': 'unique99@example.com',
            'first_name': 'Atualizado',
            'last_name': 'Sobrenome',
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['username'] == 'uniqueuser99'
    assert data['email'] == 'unique99@example.com'
    assert data['first_name'] == 'Atualizado'


def test_update_user_same_own_email(client, user, token):
    """PUT /users/{id} enviando o próprio e-mail → não gera conflito."""
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={'email': user.email},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['email'] == user.email


# --------------------------------------------------------------------------- #
# PATCH /me/password                                                         #
# --------------------------------------------------------------------------- #


def test_change_password_wrong_current(client, user, token):
    """PATCH /me/password com senha atual errada → 401."""
    response = client.patch(
        '/users/me/password',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'current_password': 'senha_errada',
            'new_password': 'novasenha123',
        },
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Current password is incorrect'}


def test_change_password_success(client, user, token):
    """PATCH /me/password com senha correta → 200 e senha atualizada."""
    response = client.patch(
        '/users/me/password',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'current_password': user.clean_password,
            'new_password': 'novaSenhaForte!',
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Password updated successfully'}

    # Confirma que o login com a nova senha funciona
    login = client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'novaSenhaForte!'},
    )
    assert login.status_code == HTTPStatus.OK


# --------------------------------------------------------------------------- #
# DELETE /users/{id}                                                         #
# --------------------------------------------------------------------------- #


def test_delete_user_forbidden(client, user, other_user, token):
    """DELETE /users/{outro_id} → 403 Forbidden."""
    response = client.delete(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permissions'}


def test_delete_user_success(client, user, token):
    """
    DELETE /users/{id} do próprio usuário → 200 e mensagem de confirmação.
    """
    response = client.delete(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'User deleted'}

    # Usuário não deve mais existir
    response2 = client.get('/users/')
    users = response2.json()['users']
    assert all(u['id'] != user.id for u in users)


# --------------------------------------------------------------------------- #
# Validação de schema — username inválido                                    #
# --------------------------------------------------------------------------- #


def test_user_schema_rejects_invalid_username():
    """
    UserSchema deve rejeitar username com espaço e acento → ValidationError.
    """
    with pytest.raises(ValidationError):
        UserSchema(
            username='João Silva',  # espaço e acento → inválido
            email='joao@test.com',
            password='secret',
            first_name='João',
            last_name='Silva',
        )


def test_user_schema_rejects_accented_username():
    """
    UserSchema deve rejeitar username com letras acentuadas → ValidationError.
    """
    with pytest.raises(ValidationError):
        UserSchema(
            username='joãosilva',  # acento no 'a'
            email='joao2@test.com',
            password='secret',
            first_name='João',
            last_name='Silva',
        )


def test_user_update_rejects_invalid_username():
    """
    UserUpdate deve rejeitar username com caracteres inválidos
    → ValidationError.
    """
    with pytest.raises(ValidationError):
        UserUpdate(username='nome inválido!')


def test_user_schema_accepts_valid_username():
    """
    UserSchema deve aceitar username válido
    (só letras, dígitos, ponto, underscore).
    """
    schema = UserSchema(
        username='joao.silva_99',
        email='joao99@test.com',
        password='secret',
        first_name='João',
        last_name='Silva',
    )
    assert schema.username == 'joao.silva_99'


def test_create_user_api_invalid_username(client):
    """
    POST /users/ com username inválido (via API) → 422 Unprocessable Entity.
    """
    response = client.post(
        '/users/',
        json={
            'username': 'João Silva',  # inválido
            'email': 'joao@test.com',
            'password': 'secret',
            'first_name': 'João',
            'last_name': 'Silva',
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
