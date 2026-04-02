"""
FastAPI dependencies para controle de acesso baseado em permissões (RBAC).

Uso nas rotas:
    # Verifica uma ou mais permissões via Depends:
    dependencies=[Depends(PermissionChecker({SystemPermissions.OCCURRENCES_CREATE}))]

    # Verifica role diretamente:
    coordinator = Depends(role_required([UserRole.COORDINATOR, UserRole.ADMIN]))
"""

from http import HTTPStatus

from fastapi import Depends, HTTPException

from app.domains.users.models import User
from app.shared.rbac import helpers
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user


class PermissionChecker:
    """
    Dependency de permissão — bloqueia a rota se o usuário não possuir
    TODAS as permissões exigidas (lógica AND).

    Uso:
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_CREATE}))
    """

    def __init__(self, required_permissions: set[SystemPermissions]):
        self.required_permissions = required_permissions

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if helpers.user_has_all_permissions(user, self.required_permissions):
            return user

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )


class AnyPermissionChecker:
    """
    Dependency de permissão — bloqueia a rota se o usuário não possuir
    PELO MENOS UMA das permissões exigidas (lógica OR).

    Uso típico: endpoints que aceitam múltiplos perfis com permissões distintas,
    ex.: VIEW_ALL | VIEW_OWN | VIEW_CHILD.

        Depends(AnyPermissionChecker({
            SystemPermissions.SCHEDULES_VIEW_ALL,
            SystemPermissions.SCHEDULES_VIEW_OWN,
        }))
    """

    def __init__(self, required_permissions: set[SystemPermissions]):
        self.required_permissions = required_permissions

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if helpers.user_has_any_permission(user, self.required_permissions):
            return user

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )


def role_required(required_roles: list[UserRole]):
    """
    Dependency de role — bloqueia a rota se o usuário não possuir
    uma das roles listadas.

    Uso:
        Depends(role_required([UserRole.COORDINATOR, UserRole.ADMIN]))
    """

    def wrapper(user: User = Depends(get_current_user)) -> User:
        if user.role not in required_roles:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f'Access denied for role: {user.role}',
            )
        return user

    return wrapper


# ── Helpers para uso direto em lógica de negócio (fora de Depends) ───────── #


def require_permission(user: User, permission: SystemPermissions) -> bool:
    """Verifica uma única permissão. Use em if statements dentro das rotas."""
    return helpers.user_has_permission(user, permission)


def require_any_permission(user: User, permission: SystemPermissions) -> bool:
    """Verifica se o usuário tem ao menos a permissão informada."""
    return helpers.user_has_any_permission(user, {permission})


def require_all_permissions(
    user: User, permissions: set[SystemPermissions]
) -> bool:
    """Verifica se o usuário possui todas as permissões do conjunto."""
    return helpers.user_has_all_permissions(user, permissions)
