from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    is_tutor: bool
    is_active: bool


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


class UserList(BaseModel):
    users: list[UserPublic]


class FilterPage(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1)
