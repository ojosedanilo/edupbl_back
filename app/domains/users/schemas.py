"""
Schemas Pydantic do domínio de usuários.

Hierarquia:
  UserSchema          → criação de usuário (todos os campos)
  UserUpdate          → atualização parcial pelo próprio usuário
  StudentProfileUpdate → campos que o DT pode editar em alunos da turma
  UserPublic          → resposta da API (sem senha)
  UserWithPermissions → UserPublic + conjunto de permissões
  PasswordChange      → troca de senha com confirmação
  UserList            → wrapper de lista paginada
  FilterPage          → parâmetros de paginação (offset/limit)
"""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole

# Aceita apenas letras minúsculas sem acento, dígitos, ponto e underscore.
# A validação de regex é feita aqui no Pydantic em vez de CheckConstraint
# no banco porque SQLite (testes) e PostgreSQL (produção) têm sintaxes
# de regex incompatíveis.
_USERNAME_RE = re.compile(r'^[a-z0-9_.]+$')


def _validate_username(v: str | None) -> str | None:
    """Valida o formato do username. Reutilizado em UserSchema e UserUpdate."""
    if v is not None and not _USERNAME_RE.match(v):
        raise ValueError(
            'Username inválido: use apenas letras minúsculas sem acento, '
            'números, ponto (.) e underscore (_)'
        )
    return v


class UserSchema(BaseModel):
    """Schema de criação — todos os campos obrigatórios, exceto os com default."""

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
    def username_format(cls, v: str) -> str:
        return _validate_username(v)  # type: ignore[return-value]


class UserUpdate(BaseModel):
    """Schema de atualização parcial — todos os campos são opcionais."""

    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    is_tutor: bool | None = None
    is_active: bool | None = None
    classroom_id: int | None = None
    must_change_password: bool | None = None

    @field_validator('username')
    @classmethod
    def username_format(cls, v: str | None) -> str | None:
        return _validate_username(v)


class UserPublic(BaseModel):
    """Resposta pública da API — sem campos sensíveis (ex: senha)."""

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
    avatar_url: str | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


class UserWithPermissions(UserPublic):
    """UserPublic acrescido do conjunto de permissões calculadas da role."""

    permissions: set[SystemPermissions]


class StudentProfileUpdate(BaseModel):
    """
    Campos que o Professor DT pode editar em alunos da própria turma.

    Escopo intencional restrito: o DT não deve alterar dados de autenticação
    (email, senha, username) nem dados administrativos (role, is_active) de
    alunos. Apenas informações de perfil que ele naturalmente gerencia.
    """

    avatar_url: str | None = None


class PasswordChange(BaseModel):
    """Schema para troca de senha com confirmação da senha atual."""

    current_password: str
    new_password: str


class UserList(BaseModel):
    """Wrapper de listagem de usuários."""

    users: list[UserPublic]


class FilterPage(BaseModel):
    """Parâmetros de paginação para endpoints de listagem."""

    offset: int = Field(0, ge=0, description='Número de registros a pular')
    limit: int = Field(100, ge=1, description='Máximo de registros retornados')
