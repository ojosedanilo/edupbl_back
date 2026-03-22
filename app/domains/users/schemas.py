import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole


class Message(BaseModel):
    message: str


# Padrão válido para username:
# apenas letras sem acento, dígitos, ponto e underscore
_USERNAME_RE = re.compile(r'^[a-z0-9_.]+$')


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.STUDENT
    is_tutor: bool = False
    is_active: bool = True
    classroom_id: int | None = None
    must_change_password: bool = False

    @field_validator('username')
    @classmethod
    def username_sem_acentos(cls, v: str) -> str:
        """
        Garante que o username só contenha
        [a-z0-9_.] — sem acentos, ç ou espaços.
        """
        if not _USERNAME_RE.match(v):
            raise ValueError(
                'Username inválido: use apenas letras minúsculas sem acento, '
                'números, ponto (.) e underscore (_)'
            )
        return v


class UserUpdate(BaseModel):
    """Schema para atualização de usuário - todos campos opcionais"""

    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_tutor: bool | None = None
    is_active: bool | None = None
    classroom_id: int | None = None
    must_change_password: bool | None = None

    @field_validator('username')
    @classmethod
    def username_sem_acentos(cls, v: str | None) -> str | None:
        if v is not None and not _USERNAME_RE.match(v):
            raise ValueError(
                'Username inválido: use apenas letras minúsculas sem acento, '
                'números, ponto (.) e underscore (_)'
            )
        return v


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_tutor: bool
    is_active: bool
    classroom_id: int | None
    must_change_password: bool

    model_config = ConfigDict(from_attributes=True)


class UserWithPermissions(UserPublic):
    permissions: set[SystemPermissions]


class PasswordChange(BaseModel):
    """Schema para troca de senha pelo próprio usuário."""

    current_password: str
    new_password: str


class UserList(BaseModel):
    users: list[UserPublic]


class FilterPage(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1)
