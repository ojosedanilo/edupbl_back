"""
Testes adicionais para cobertura de:
- shared/security.py        → token sem 'sub', usuário deletado
- shared/rbac/helpers.py    → user_has_permission, user_has_any_permission
- shared/rbac/dependencies.py → require_permission, require_any_permission,
  require_all_permissions
"""

from http import HTTPStatus

from app.shared.rbac.dependencies import (
    require_all_permissions,
    require_any_permission,
    require_permission,
)
from app.shared.rbac.helpers import (
    get_user_permissions,
    user_has_any_permission,
    user_has_permission,
)
from app.shared.rbac.permissions import (
    TUTOR_EXTRA_PERMISSIONS,
    SystemPermissions,
)
from app.shared.security import create_access_token

# --------------------------------------------------------------------------- #
# security.py — token sem 'sub' e usuário inexistente                        #
# --------------------------------------------------------------------------- #


def test_token_without_sub_returns_401(client):
    """
    Token JWT válido mas sem campo 'sub'→ 401.
    Cobre a linha: if not subject_email: raise credentials_exception.
    """
    # Gera token sem o campo 'sub'
    token = create_access_token(data={'data': 'sem_sub'})
    response = client.get(
        '/auth/me',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


def test_token_deleted_user_returns_401(client, user, token):
    """
    Token válido de usuário que foi deletado → 401.
    Cobre linhas 84-87: if not user: raise credentials_exception; return user.
    """
    # Deleta o usuário antes de usar o token
    client.delete(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    # Tenta usar o mesmo token após a deleção
    response = client.get(
        '/auth/me',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


# --------------------------------------------------------------------------- #
# rbac/helpers.py — is_tutor=True em role diferente de TEACHER               #
# --------------------------------------------------------------------------- #


def test_is_tutor_on_student_does_not_add_extra_perms(student_user):
    """
    Aluno com is_tutor=True não recebe TUTOR_EXTRA_PERMISSIONS.
    Cobre o branch falso de:
      `if user.is_tutor and user.role == UserRole.TEACHER`
    """
    student_user.is_tutor = True
    perms = get_user_permissions(student_user)

    for extra in TUTOR_EXTRA_PERMISSIONS:
        assert extra not in perms


def test_is_tutor_on_teacher_adds_extra_perms(tutor_user):
    """Professor DT (TEACHER + is_tutor=True) recebe extras."""
    perms = get_user_permissions(tutor_user)

    for extra in TUTOR_EXTRA_PERMISSIONS:
        assert extra in perms


# --------------------------------------------------------------------------- #
# rbac/helpers.py — user_has_permission e user_has_any_permission             #
# --------------------------------------------------------------------------- #


def test_user_has_permission_true(teacher_user):
    """
    user_has_permission retorna True quando usuário tem a permissão
    (linhas 26-27).
    """
    result = user_has_permission(
        teacher_user, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is True


def test_user_has_permission_false(student_user):
    """user_has_permission retorna False quando usuário não tem a permissão."""
    result = user_has_permission(
        student_user, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is False


def test_user_has_any_permission_true(teacher_user):
    """user_has_any_permission retorna True quando tem ao menos uma."""
    result = user_has_any_permission(
        teacher_user,
        {
            SystemPermissions.OCCURRENCES_CREATE,
            SystemPermissions.USER_CHANGE_ROLE,
        },
    )
    assert result is True


def test_user_has_any_permission_false(student_user):
    """user_has_any_permission retorna False quando não tem nenhuma."""
    result = user_has_any_permission(
        student_user,
        {
            SystemPermissions.OCCURRENCES_CREATE,
            SystemPermissions.USER_CHANGE_ROLE,
        },
    )
    assert result is False


# --------------------------------------------------------------------------- #
# rbac/dependencies.py — require_permission / require_any / require_all       #
# --------------------------------------------------------------------------- #


def test_require_permission_returns_true(teacher_user):
    """require_permission retorna True para permissão existente."""
    result = require_permission(
        teacher_user, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is True


def test_require_permission_returns_false(student_user):
    """require_permission retorna False para permissão ausente."""
    result = require_permission(
        student_user, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is False


def test_require_any_permission_returns_true(teacher_user):
    """require_any_permission retorna True quando tem ao menos uma."""
    result = require_any_permission(
        teacher_user, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is True


def test_require_any_permission_returns_false(student_user):
    """require_any_permission retorna False quando não tem nenhuma."""
    result = require_any_permission(
        student_user, SystemPermissions.OCCURRENCES_CREATE
    )
    assert result is False


def test_require_all_permissions_true(coordinator_user):
    """require_all_permissions retorna True quando tem todas."""
    result = require_all_permissions(
        coordinator_user,
        {
            SystemPermissions.OCCURRENCES_VIEW_ALL,
            SystemPermissions.OCCURRENCES_CREATE,
        },
    )
    assert result is True


def test_require_all_permissions_false(teacher_user):
    """require_all_permissions retorna False quando falta ao menos uma."""
    result = require_all_permissions(
        teacher_user,
        # Professor não tem OCCURRENCES_VIEW_ALL
        {
            SystemPermissions.OCCURRENCES_CREATE,
            SystemPermissions.OCCURRENCES_VIEW_ALL,
        },
    )
    assert result is False
