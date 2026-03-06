from http import HTTPStatus

from fastapi import Depends, HTTPException

from typing import List

from app.domains.users.models import User
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user


class PermissionChecker:
    def __init__(self, required_permissions: List[SystemPermissions]):
        self.required_permissions = required_permissions

    def __call__(
        self,
        user_permissions: List[str] = Depends(
            get_current_user_permissions
        ),  # !!! Implementar !!!
    ):
        # Check if the user has any of the required permissions
        for permission in self.required_permissions:
            if permission.value in user_permissions:
                return True

        # If no permission is found, raise a 403 Forbidden error
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Insufficient permissions'
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
