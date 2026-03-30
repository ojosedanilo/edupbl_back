"""
Funções auxiliares de verificação de permissões.

Estas funções são usadas internamente pelo PermissionChecker (dependencies.py)
e podem ser chamadas diretamente em lógica de negócio dentro das rotas.
"""

from app.domains.users.models import User
from app.shared.rbac.permissions import (
    ROLE_PERMISSIONS,
    TUTOR_EXTRA_PERMISSIONS,
    SystemPermissions,
)
from app.shared.rbac.roles import UserRole


def get_user_permissions(user: User) -> set[SystemPermissions]:
    """
    Retorna o conjunto completo de permissões do usuário.

    Combina as permissões da role + permissões extras de DT (se aplicável).
    A flag is_tutor só adiciona permissões quando role == TEACHER —
    um aluno com is_tutor=True por engano não recebe permissões extras.
    """
    permissions = ROLE_PERMISSIONS.get(user.role, set()).copy()

    if user.is_tutor and user.role == UserRole.TEACHER:
        permissions.update(TUTOR_EXTRA_PERMISSIONS)

    return permissions


def user_has_permission(user: User, permission: SystemPermissions) -> bool:
    """Retorna True se o usuário possui a permissão específica."""
    return permission in get_user_permissions(user)


def user_has_any_permission(
    user: User, permissions: set[SystemPermissions]
) -> bool:
    """Retorna True se o usuário possui PELO MENOS UMA das permissões."""
    return not get_user_permissions(user).isdisjoint(permissions)


def user_has_all_permissions(
    user: User, permissions: set[SystemPermissions]
) -> bool:
    """Retorna True somente se o usuário possui TODAS as permissões."""
    return permissions.issubset(get_user_permissions(user))
