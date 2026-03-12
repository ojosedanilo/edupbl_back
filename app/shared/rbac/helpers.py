from app.domains.users.models import User
from app.shared.rbac.permissions import (
    ROLE_PERMISSIONS,
    TUTOR_EXTRA_PERMISSIONS,
    SystemPermissions,
)


def get_user_permissions(user: User) -> set[SystemPermissions]:
    """Obtém as permissões do usuário"""
    # Obtém as permissões da role do usuário, ou retorna um set vazio
    permissions = ROLE_PERMISSIONS.get(user.role, set()).copy()

    # Permissões extras para o Professor Diretor de Turma (tutor)
    if user.is_tutor:
        permissions.update(TUTOR_EXTRA_PERMISSIONS)

    return permissions


def user_has_permission(user: User, permission: SystemPermissions) -> bool:
    """Verifica se usuário tem a permissão específica"""
    permissions = get_user_permissions(user)
    return permission in permissions


def user_has_any_permission(user: User, permission: SystemPermissions) -> bool:
    """Verifica se usuário tem QUALQUER uma das permissões"""
    return not get_user_permissions(user).isdisjoint(permission)


def user_has_all_permissions(
    user: User, permissions: set[SystemPermissions]
) -> bool:
    """Verifica se usuário tem TODAS as permissões"""
    return permissions.issubset(get_user_permissions(user))
