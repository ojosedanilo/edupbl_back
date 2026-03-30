"""
Definição de permissões do sistema e mapeamento role → permissões.

Convenção de nomenclatura: VERBO_DOMÍNIO
  Verbos  : CREATE, VIEW, EDIT, DELETE, CHANGE, APPROVE, MODERATE,
            REJECT, SUBMIT, RESERVATE, VALIDATE
  Domínios: USERS, OCCURRENCES, DELAYS, CERTIFICATES, SPACES,
            REPORTS, SUGGESTIONS

Permissões futuras (ainda não implementadas) estão comentadas
nos grupos correspondentes — não as remova.
"""

from enum import Enum

from app.shared.rbac.roles import UserRole


class SystemPermissions(str, Enum):

    # ── Atestados ──────────────────────────────────────────────────── #
    CERTIFICATES_APPROVE  = 'certificates:approve'
    CERTIFICATES_SUBMIT   = 'certificates:submit'
    CERTIFICATES_VALIDATE = 'certificates:validate'

    # ── Atrasos ────────────────────────────────────────────────────── #
    DELAYS_APPROVE        = 'delays:approve'
    DELAYS_CREATE         = 'delays:create'
    DELAYS_REJECT         = 'delays:reject'
    DELAYS_VIEW_ALL       = 'delays:read_all'       # Todos os atrasos do sistema
    DELAYS_VIEW_OWN       = 'delays:read_own'       # Meus próprios atrasos
    DELAYS_VIEW_CHILD     = 'delays:read_child'     # Atrasos do(s) filho(s)
    DELAYS_VIEW_OWN_CLASS = 'delays:read_own_class' # Atrasos da minha turma (DT)

    # ── Ocorrências ────────────────────────────────────────────────── #
    OCCURRENCES_CREATE     = 'occurrences:create'
    OCCURRENCES_DELETE     = 'occurrences:delete'
    OCCURRENCES_EDIT       = 'occurrences:update'
    OCCURRENCES_VIEW_OWN   = 'occurrences:read_own'   # Criei OU sou o aluno
    OCCURRENCES_VIEW_CHILD = 'occurrences:read_child' # Ocorrências do(s) filho(s)
    OCCURRENCES_VIEW_ALL   = 'occurrences:read_all'   # Todas as ocorrências

    # ── Relatórios ─────────────────────────────────────────────────── #
    REPORTS_VIEW_ALL       = 'reports:view_all'       # Relatórios de todas as turmas
    REPORTS_VIEW_OWN_CLASS = 'reports:view_own_class' # Relatórios da minha turma

    # ── Espaços ────────────────────────────────────────────────────── #
    SPACES_CREATE     = 'spaces:create'
    SPACES_DELETE     = 'spaces:delete'
    SPACES_EDIT       = 'spaces:update'
    SPACES_RESERVATE  = 'spaces:reservate'
    SPACES_VIEW_ALL   = 'spaces:read_all'

    # ── Sugestões ──────────────────────────────────────────────────── #
    SUGGESTIONS_SUBMIT   = 'suggestions:submit'
    SUGGESTIONS_MODERATE = 'suggestions:moderate'

    # ── Usuários ───────────────────────────────────────────────────── #
    USER_CHANGE_ROLE = 'user:change_role'
    USER_CREATE      = 'user:create'
    USER_DELETE      = 'user:delete'
    USER_EDIT        = 'user:update'
    USER_VIEW_OWN    = 'user:read_own'   # Próprias informações
    USER_VIEW_CHILD  = 'user:read_child' # Informações do(s) filho(s)
    USER_VIEW_ALL    = 'users:read_all'  # Todos os usuários


# Permissões que o Coordenador NÃO possui
# (apenas o Admin pode alterar o role de usuários)
COORDINATOR_EXCEPTION_ROLES = {SystemPermissions.USER_CHANGE_ROLE}

# Mapeamento role → conjunto de permissões específicas da role
ROLE_PERMISSIONS: dict[UserRole, set[SystemPermissions]] = {

    UserRole.STUDENT: {
        SystemPermissions.OCCURRENCES_VIEW_OWN,
        SystemPermissions.DELAYS_VIEW_OWN,
        SystemPermissions.CERTIFICATES_SUBMIT,
    },

    UserRole.GUARDIAN: {
        SystemPermissions.USER_VIEW_CHILD,
        SystemPermissions.OCCURRENCES_VIEW_CHILD,
        SystemPermissions.DELAYS_VIEW_CHILD,
        SystemPermissions.CERTIFICATES_SUBMIT,
    },

    UserRole.TEACHER: {
        SystemPermissions.OCCURRENCES_CREATE,
        SystemPermissions.OCCURRENCES_DELETE,
        SystemPermissions.OCCURRENCES_EDIT,
        SystemPermissions.OCCURRENCES_VIEW_OWN,
        SystemPermissions.SPACES_RESERVATE,
        SystemPermissions.SPACES_VIEW_ALL,
    },

    # Coordenador tem tudo, exceto USER_CHANGE_ROLE
    UserRole.COORDINATOR: {*SystemPermissions} - COORDINATOR_EXCEPTION_ROLES,

    UserRole.PORTER: {
        SystemPermissions.DELAYS_CREATE,
        SystemPermissions.DELAYS_VIEW_ALL,
    },

    # Admin tem todas as permissões
    UserRole.ADMIN: {*SystemPermissions},
}

# Permissões extras exclusivas do Professor Diretor de Turma (TEACHER + is_tutor=True)
TUTOR_EXTRA_PERMISSIONS: set[SystemPermissions] = {
    SystemPermissions.CERTIFICATES_VALIDATE,
    SystemPermissions.REPORTS_VIEW_OWN_CLASS,
}

# Permissões base concedidas a TODOS os usuários, independentemente da role
_BASE_PERMISSIONS: set[SystemPermissions] = {
    SystemPermissions.USER_EDIT,
    SystemPermissions.USER_VIEW_OWN,
    SystemPermissions.SUGGESTIONS_SUBMIT,
}

for _perms in ROLE_PERMISSIONS.values():
    _perms.update(_BASE_PERMISSIONS)
