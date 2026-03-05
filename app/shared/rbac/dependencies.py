from http import HTTPStatus

from fastapi import Depends, HTTPException

from app.domains.users.schemas import UserSchema
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user


def role_required(required_roles: list[UserRole]):
    def wrapper(user: UserSchema = Depends(get_current_user)):
        if user.role not in required_roles:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f'Access denied for role: {user.role}',
            )
        return user

    return wrapper
