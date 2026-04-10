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
"""

import re

# --------------------------------------------------------------------------- #
# Validação de senha                                                           #
# --------------------------------------------------------------------------- #

_COMMON_SEQUENCES = re.compile(
    r'(012|123|234|345|456|567|678|789|890'
    r'|abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz'
    r'|qwerty|asdf|zxcv|senha|password|admin)',
    re.IGNORECASE,
)
_REPEATED_CHARS = re.compile(r'(.)\1{3,}')  # 4+ repetições do mesmo char


def validate_password_strength(v: str) -> str:
    """
    Valida os critérios de segurança da senha.
    Lança ValueError descritivo se algum critério não for atendido.
    """
    errors: list[str] = []

    if len(v) < 8:
        errors.append('Mínimo de 8 caracteres (15+ é muito mais seguro).')
    if not re.search(r'[A-Z]', v):
        errors.append('Pelo menos uma letra maiúscula (A-Z).')
    if not re.search(r'[a-z]', v):
        errors.append('Pelo menos uma letra minúscula (a-z).')
    if not re.search(r'\d', v):
        errors.append('Pelo menos um número (0-9).')
    if not re.search(r'[@#$%&!*]', v):
        errors.append('Pelo menos um caractere especial: @ # $ % & ! *')
    if _REPEATED_CHARS.search(v):
        errors.append('Evite repetições de caracteres (ex: aaaa).')
    if _COMMON_SEQUENCES.search(v):
        errors.append('Evite sequências comuns (ex: 123456, qwerty, senha).')

    if errors:
        raise ValueError(' | '.join(errors))

    return v

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

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

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


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


class AdminUserUpdate(BaseModel):
    """
    Schema de atualização privilegiada — usado por Coord/Admin via
    PATCH /users/{id}/admin-update.

    Permite editar qualquer campo de qualquer usuário, incluindo role,
    is_tutor e classroom_id. A alteração de role requer USER_CHANGE_ROLE
    (Admin); Coordenadores têm USER_EDIT mas não USER_CHANGE_ROLE.
    """

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    username: str | None = None
    role: UserRole | None = None
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

    avatar_url é gerenciado exclusivamente pelo endpoint PATCH /users/{id}/avatar.
    """

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class PasswordChange(BaseModel):
    """Schema para troca de senha com confirmação da senha atual."""

    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserList(BaseModel):
    """Wrapper de listagem de usuários."""

    users: list[UserPublic]


class StudentSummary(BaseModel):
    """
    Visão reduzida de um aluno — exposta a porteiros e professores.

    Contém apenas o necessário para identificar o aluno na interface:
    nome, turma e avatar. Campos sensíveis (e-mail, telefone, etc.)
    são omitidos intencionalmente.
    """

    id: int
    first_name: str
    last_name: str
    classroom_id: int | None
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class StudentSummaryList(BaseModel):
    """Wrapper de listagem de alunos com dados reduzidos."""

    students: list[StudentSummary]


class UserBulkRequest(BaseModel):
    """Lista de IDs para busca em lote de usuários."""

    ids: list[int]


class UserBulkResponse(BaseModel):
    """Wrapper de resposta de busca em lote de usuários."""

    users: list[UserPublic]
