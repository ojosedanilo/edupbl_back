"""
Testes para o sistema RBAC (Roles e Permissions)
"""

from http import HTTPStatus

import pytest
import pytest_asyncio

from app.domains.users.models import User
from app.shared.rbac.helpers import get_user_permissions
from app.shared.rbac.permissions import (
    ROLE_PERMISSIONS,
    TUTOR_EXTRA_PERMISSIONS,
    SystemPermissions,
)
from app.shared.rbac.roles import UserRole
from app.shared.security import get_password_hash
from tests.conftest import UserFactory


# ============================================================================
# FIXTURES - Usuários com diferentes roles
# ============================================================================


@pytest_asyncio.fixture
async def student(session):
    """Aluno comum"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.STUDENT,
        is_tutor=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


@pytest_asyncio.fixture
async def guardian(session):
    """Responsável"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.GUARDIAN,
        is_tutor=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


@pytest_asyncio.fixture
async def teacher(session):
    """Professor comum"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.TEACHER,
        is_tutor=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


@pytest_asyncio.fixture
async def tutor(session):
    """Professor Diretor de Turma"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.TEACHER,
        is_tutor=True,  # ← Flag de tutor
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


@pytest_asyncio.fixture
async def coordinator(session):
    """Coordenador"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.COORDINATOR,
        is_tutor=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


@pytest_asyncio.fixture
async def porter(session):
    """Porteiro"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.PORTER,
        is_tutor=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


@pytest_asyncio.fixture
async def admin(session):
    """Administrador do sistema"""
    password = 'testtest'
    user = UserFactory(
        password=get_password_hash(password),
        role=UserRole.ADMIN,
        is_tutor=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


# ============================================================================
# TESTES - Helpers de Permissões
# ============================================================================


def test_get_user_permissions_student(student):
    """Aluno deve ter permissões base"""
    permissions = get_user_permissions(student)

    assert SystemPermissions.OCCURRENCES_VIEW_OWN in permissions
    assert SystemPermissions.DELAYS_VIEW_OWN in permissions
    assert SystemPermissions.CERTIFICATES_SUBMIT in permissions
    # Não deve ter permissões de criar ocorrência
    assert SystemPermissions.OCCURRENCES_CREATE not in permissions


def test_get_user_permissions_teacher(teacher):
    """Professor deve poder criar ocorrências"""
    permissions = get_user_permissions(teacher)

    assert SystemPermissions.OCCURRENCES_CREATE in permissions
    assert SystemPermissions.OCCURRENCES_EDIT in permissions
    assert SystemPermissions.OCCURRENCES_DELETE in permissions
    assert SystemPermissions.SPACES_RESERVATE in permissions
    # Não deve ter permissões de coordenador
    assert SystemPermissions.OCCURRENCES_VIEW_ALL not in permissions


def test_get_user_permissions_tutor(tutor):
    """Professor DT deve ter permissões extras"""
    permissions = get_user_permissions(tutor)

    # Permissões normais de professor
    assert SystemPermissions.OCCURRENCES_CREATE in permissions

    # Permissões extras de tutor
    assert SystemPermissions.CERTIFICATES_VALIDATE in permissions
    assert SystemPermissions.REPORTS_VIEW_OWN_CLASS in permissions


def test_get_user_permissions_coordinator(coordinator):
    """Coordenador deve ter quase todas as permissões"""
    permissions = get_user_permissions(coordinator)

    assert SystemPermissions.OCCURRENCES_VIEW_ALL in permissions
    assert SystemPermissions.DELAYS_APPROVE in permissions
    assert SystemPermissions.CERTIFICATES_APPROVE in permissions
    # Coordenador NÃO pode mudar role de usuários (só admin)
    assert SystemPermissions.USER_CHANGE_ROLE not in permissions


def test_get_user_permissions_porter(porter):
    """Porteiro deve ter permissões específicas de atrasos"""
    permissions = get_user_permissions(porter)

    assert SystemPermissions.DELAYS_CREATE in permissions
    assert SystemPermissions.DELAYS_VIEW_ALL in permissions
    # Não deve ter permissões de ocorrências
    assert SystemPermissions.OCCURRENCES_CREATE not in permissions


def test_get_user_permissions_admin(admin):
    """Admin deve ter TODAS as permissões"""
    permissions = get_user_permissions(admin)

    # Admin tem todas
    assert SystemPermissions.USER_CHANGE_ROLE in permissions
    assert SystemPermissions.OCCURRENCES_VIEW_ALL in permissions
    assert len(permissions) == len(SystemPermissions)


def test_tutor_extra_permissions_only_for_teachers(student):
    """Tutor extra permissions só devem ser dadas a professores"""
    # Criar estudante com is_tutor=True (não deveria acontecer, mas testa)
    student.is_tutor = True
    permissions = get_user_permissions(student)

    # Mesmo com is_tutor=True, aluno não ganha permissões de tutor
    # porque não é TEACHER
    assert SystemPermissions.CERTIFICATES_VALIDATE not in permissions


# ============================================================================
# TESTES - Endpoint /auth/me
# ============================================================================


def test_me_returns_role_and_flags(client, student, token):
    """Endpoint /me deve retornar role e flags"""
    response = client.get(
        '/auth/me', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    assert 'role' in data
    assert 'is_tutor' in data
    assert 'is_active' in data
    assert data['role'] == UserRole.STUDENT.value


# ============================================================================
# TESTES - Endpoint /auth/me/permissions
# ============================================================================


def test_me_permissions_student(client, student):
    """Endpoint /me/permissions deve retornar permissões do aluno"""
    # Login
    response = client.post(
        '/auth/token',
        data={'username': student.email, 'password': student.clean_password},
    )
    token = response.json()['access_token']

    # Buscar permissões
    response = client.get(
        '/auth/me/permissions', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    # Deve ter campo permissions
    assert 'permissions' in data
    permissions = set(data['permissions'])

    # Verificar permissões de aluno
    assert SystemPermissions.OCCURRENCES_VIEW_OWN.value in permissions
    assert SystemPermissions.DELAYS_VIEW_OWN.value in permissions
    # Não deve ter permissões de professor
    assert SystemPermissions.OCCURRENCES_CREATE.value not in permissions


def test_me_permissions_teacher(client, teacher):
    """Endpoint /me/permissions deve retornar permissões do professor"""
    # Login
    response = client.post(
        '/auth/token',
        data={'username': teacher.email, 'password': teacher.clean_password},
    )
    token = response.json()['access_token']

    # Buscar permissões
    response = client.get(
        '/auth/me/permissions', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    permissions = set(data['permissions'])

    # Professor pode criar ocorrências
    assert SystemPermissions.OCCURRENCES_CREATE.value in permissions
    assert SystemPermissions.SPACES_RESERVATE.value in permissions


def test_me_permissions_tutor(client, tutor):
    """Endpoint /me/permissions deve incluir permissões extras de tutor"""
    # Login
    response = client.post(
        '/auth/token',
        data={'username': tutor.email, 'password': tutor.clean_password},
    )
    token = response.json()['access_token']

    # Buscar permissões
    response = client.get(
        '/auth/me/permissions', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    permissions = set(data['permissions'])

    # Deve ter permissões extras de tutor
    assert SystemPermissions.CERTIFICATES_VALIDATE.value in permissions
    assert SystemPermissions.REPORTS_VIEW_OWN_CLASS.value in permissions


def test_me_permissions_coordinator(client, coordinator):
    """Coordenador deve ter quase todas as permissões"""
    # Login
    response = client.post(
        '/auth/token',
        data={
            'username': coordinator.email,
            'password': coordinator.clean_password,
        },
    )
    token = response.json()['access_token']

    # Buscar permissões
    response = client.get(
        '/auth/me/permissions', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    permissions = set(data['permissions'])

    # Coordenador tem muitas permissões
    assert SystemPermissions.OCCURRENCES_VIEW_ALL.value in permissions
    assert SystemPermissions.DELAYS_APPROVE.value in permissions
    # Mas NÃO pode mudar role (só admin)
    assert SystemPermissions.USER_CHANGE_ROLE.value not in permissions


# ============================================================================
# TESTES - Endpoint /auth/admin (role_required)
# ============================================================================


def test_admin_endpoint_with_coordinator(client, coordinator):
    """Coordenador deve acessar endpoint /admin"""
    # Login
    response = client.post(
        '/auth/token',
        data={
            'username': coordinator.email,
            'password': coordinator.clean_password,
        },
    )
    token = response.json()['access_token']

    # Tentar acessar /admin
    response = client.get(
        '/auth/admin', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK


def test_admin_endpoint_with_admin(client, admin):
    """Admin deve acessar endpoint /admin"""
    # Login
    response = client.post(
        '/auth/token',
        data={'username': admin.email, 'password': admin.clean_password},
    )
    token = response.json()['access_token']

    # Tentar acessar /admin
    response = client.get(
        '/auth/admin', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK


def test_admin_endpoint_with_teacher_forbidden(client, teacher):
    """Professor NÃO deve acessar endpoint /admin"""
    # Login
    response = client.post(
        '/auth/token',
        data={'username': teacher.email, 'password': teacher.clean_password},
    )
    token = response.json()['access_token']

    # Tentar acessar /admin
    response = client.get(
        '/auth/admin', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert 'Access denied for role' in response.json()['detail']


def test_admin_endpoint_with_student_forbidden(client, student):
    """Aluno NÃO deve acessar endpoint /admin"""
    # Login
    response = client.post(
        '/auth/token',
        data={'username': student.email, 'password': student.clean_password},
    )
    token = response.json()['access_token']

    # Tentar acessar /admin
    response = client.get(
        '/auth/admin', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


# ============================================================================
# TESTES - Criação de Usuário com Role
# ============================================================================


def test_create_user_with_role(client):
    """Criar usuário deve respeitar role enviado"""
    response = client.post(
        '/users/',
        json={
            'username': 'newteacher',
            'email': 'newteacher@test.com',
            'password': 'testtest',
            'first_name': 'New',
            'last_name': 'Teacher',
            'role': UserRole.TEACHER.value,
            'is_tutor': False,
            'is_active': True,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()

    assert data['role'] == UserRole.TEACHER.value
    assert data['is_tutor'] is False
    assert data['is_active'] is True


def test_create_user_with_tutor_flag(client):
    """Criar usuário com is_tutor=True"""
    response = client.post(
        '/users/',
        json={
            'username': 'newtutor',
            'email': 'newtutor@test.com',
            'password': 'testtest',
            'first_name': 'New',
            'last_name': 'Tutor',
            'role': UserRole.TEACHER.value,
            'is_tutor': True,  # ← Professor DT
            'is_active': True,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()

    assert data['role'] == UserRole.TEACHER.value
    assert data['is_tutor'] is True


def test_create_user_defaults_to_student(client):
    """Criar usuário sem especificar role deve criar como STUDENT"""
    response = client.post(
        '/users/',
        json={
            'username': 'newstudent',
            'email': 'newstudent@test.com',
            'password': 'testtest',
            'first_name': 'New',
            'last_name': 'Student',
            # Não especifica role, is_tutor, is_active
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()

    # Deve ter valores default
    assert data['role'] == UserRole.STUDENT.value
    assert data['is_tutor'] is False
    assert data['is_active'] is True
