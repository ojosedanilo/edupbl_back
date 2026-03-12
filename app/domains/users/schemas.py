from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole


class Message(BaseModel):
    message: str


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.STUDENT
    is_tutor: bool = False
    is_active: bool = True


class UserUpdate(BaseModel):
    """Schema para atualização de usuário - todos campos opcionais"""

    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_tutor: bool | None = None
    is_active: bool | None = None


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_tutor: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserWithPermissions(UserPublic):
    permissions: set[SystemPermissions]


class UserList(BaseModel):
    users: list[UserPublic]


class FilterPage(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1)
