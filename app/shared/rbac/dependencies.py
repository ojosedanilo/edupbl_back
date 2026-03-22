from http import HTTPStatus

from fastapi import Depends, HTTPException

from app.domains.users.models import User
from app.shared.rbac import helpers
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user


class PermissionChecker:
    def __init__(self, required_permissions: set[SystemPermissions]):
        self.required_permissions = required_permissions

    def __call__(self, user: User = Depends(get_current_user)):
        if helpers.user_has_all_permissions(user, self.required_permissions):
            return user

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )


def role_required(required_roles: list[UserRole]):
    def wrapper(user: User = Depends(get_current_user)):
        if user.role not in required_roles:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f'Access denied for role: {user.role}',
            )
        return user

    return wrapper


def require_permission(user: User, permission: SystemPermissions):
    return helpers.user_has_permission(user, permission)


def require_any_permission(user: User, permission: SystemPermissions):
    return helpers.user_has_any_permission(user, {permission})


def require_all_permissions(user: User, permissions: set[SystemPermissions]):
    return helpers.user_has_all_permissions(user, permissions)
