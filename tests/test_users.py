from http import HTTPStatus

from app.domains.users.schemas import UserPublic
from app.shared.rbac.roles import UserRole


def test_create_user(client):
    response = client.post(
        '/users/',
        json={
            'username': 'alice',
            'first_name': 'alice',
            'last_name': 'liddell',
            'email': 'alice@example.com',
            'password': 'secret',
            'role': UserRole.TEACHER,
            'is_active': True,
            'is_tutor': True,
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json() == {
        'id': 1,
        'username': 'alice',
        'email': 'alice@example.com',
        'first_name': 'alice',
        'last_name': 'liddell',
        'role': UserRole.TEACHER,
        'is_active': True,
        'is_tutor': True,
    }


def test_read_users(client):
    response = client.get('/users')
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'users': []}


def test_read_users_with_users(client, user):
    user_schema = UserPublic.model_validate(user).model_dump()
    response = client.get('/users/')
    assert response.json() == {'users': [user_schema]}


def test_update_user(client, user, token):
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'bob',
            'email': 'bob@example.com',
            'first_name': 'bob',
            'last_name': 'bobson',
            'password': 'mynewpassword',
            'is_active': True,
            'is_tutor': False,
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'username': 'bob',
        'email': 'bob@example.com',
        'first_name': 'bob',
        'last_name': 'bobson',
        'id': user.id,
        'role': user.role,  # Usa o role que o user já tinha
        'is_active': True,
        'is_tutor': False,
    }


def test_update_integrity_error(client, user, token):
    # Inserindo fausto
    client.post(
        '/users',
        json={
            'username': 'fausto',
            'email': 'fausto@example.com',
            'first_name': 'fausto',
            'last_name': 'faustino',
            'password': 'secret',
        },
    )

    # Alterando o user das fixture para fausto
    response_update = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'fausto',
            'email': 'bob@example.com',
            'first_name': 'fausto',
            'last_name': 'faustino',
            'password': 'mynewpassword',
            'is_active': True,
            'is_tutor': False,
        },
    )
    print(response_update.status_code)
    print(response_update.json())
    # breakpoint()

    assert response_update.status_code == HTTPStatus.CONFLICT
    assert response_update.json() == {
        'detail': 'Username or Email already exists'
    }


def test_delete_user(client, user, token):
    response = client.delete(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'User deleted'}


def test_update_user_with_wrong_user(client, other_user, token):
    response = client.put(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'bob',
            'email': 'bob@example.com',
            'first_name': 'bob',
            'last_name': 'bobson',
            'password': 'mynewpassword',
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permissions'}


def test_delete_user_wrong_user(client, other_user, token):
    response = client.delete(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permissions'}
