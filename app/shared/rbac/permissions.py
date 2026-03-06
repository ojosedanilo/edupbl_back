from enum import Enum
from app.shared.rbac.roles import UserRole

# Naming convention: VERBO_RECURSO

# VERBOS
# CREATE  -> Criar
# VIEW    -> Visualizar (Ler)
# EDIT    -> Editar     (Atualziar)
# DELETE  -> Deletar    (Apagar)
# CHANGE  -> Mudar atributo
# !!! Falta Implementar !!!
# APPROVE -> Aprovar
# MODERATE -> Moderar
# REJECT  -> Rejeitar
# SUBMIT -> Enviar
# RESERVATE -> Reservar
# VALIDATE -> Validar

# DOMÍNIOS
# USERS        -> Usuários
# !!! Falta Implementar !!!
# OCCURRENCES  -> Ocorrências
# DELAYS       -> Atrasos
# CERTIFICATES -> Atestado
# SPACES       -> Espaços
# REPORTS      -> Relatórios
# SUGGESTIONS  -> Sugestões


class SystemPermissions(str, Enum):
    # Atestados
    CERTIFICATES_APPROVE = 'certificates:approve'
    CERTIFICATES_SUBMIT = 'certificates:submit'
    CERTIFICATES_VALIDATE = 'certificates:validate'

    # Atrasos
    DELAYS_APPROVE = 'delays:approve'
    DELAYS_CREATE = 'delays:create'
    DELAYS_REJECT = 'delays:reject'
    # Atrasos de todos do sistema
    DELAYS_VIEW_ALL = 'delays:read_all'
    # Meus atrasos próprias
    DELAYS_VIEW_OWN = 'delays:read_own'
    # Meus atrasos do(s) filho(s)
    DELAYS_VIEW_CHILD = 'delays:read_child'
    # Atrasos de todos da sala
    DELAYS_VIEW_OWN_CLASS = 'delays:read_own_class'

    # Ocorrências
    OCCURRENCES_CREATE = 'occurrences:create'
    OCCURRENCES_DELETE = 'occurrences:delete'
    OCCURRENCES_EDIT = 'occurrences:update'
    # Que criei OU que são sobre mim
    OCCURRENCES_VIEW_OWN = 'occurrences:read_own'
    # Que criei OU que são sobre mim
    OCCURRENCES_VIEW_CHILD = 'occurrences:read_child'
    # Todas as ocorrências
    OCCURRENCES_VIEW_ALL = 'occurrences:read_all'

    # Relatórios
    # Ver relatórios de todas turmas
    REPORTS_VIEW_ALL = 'reports:view_all'
    # Ver relatórios da própria turma
    REPORTS_VIEW_OWN_CLASS = 'reports:view_own_class'

    # Espaços
    SPACES_CREATE = 'spaces:create'
    SPACES_DELETE = 'spaces:delete'
    SPACES_EDIT = 'spaces:update'
    SPACES_RESERVATE = 'spaces:reservate'
    SPACES_VIEW_ALL = 'spaces:read_all'

    # Suggestions
    SUGGESTIONS_SUBMIT = 'suggestions:submit'
    SUGGESTIONS_MODERATE = 'suggestions:moderate'

    # Usuário
    USER_CHANGE_ROLE = 'user:change_role'
    USER_CREATE = 'user:create'
    USER_DELETE = 'user:delete'
    USER_EDIT = 'user:update'
    # Informações próprias
    USER_VIEW_OWN = 'user:read_own'
    # Informações do(s) filho(s)
    USER_VIEW_CHILD = 'user:read_child'
    # Informações de todos os usuários
    USER_VIEW_ALL = 'users:read_all'


# Roles que Coordenador não pode ter
COORDINATOR_EXCEPTION_ROLES = {SystemPermissions.USER_CHANGE_ROLE}

# Permissões para cada Role
ROLE_PERMISSIONS = {
    # Aluno
    UserRole.STUDENT: {
        SystemPermissions.OCCURRENCES_VIEW_OWN,
        SystemPermissions.DELAYS_VIEW_OWN,
        SystemPermissions.CERTIFICATES_SUBMIT,
    },
    # Responsável
    UserRole.GUARDIAN: {
        SystemPermissions.USER_VIEW_CHILD,
        SystemPermissions.OCCURRENCES_VIEW_CHILD,
        SystemPermissions.DELAYS_VIEW_CHILD,
        SystemPermissions.CERTIFICATES_SUBMIT,
    },
    # Professor
    UserRole.TEACHER: {
        SystemPermissions.OCCURRENCES_CREATE,
        SystemPermissions.OCCURRENCES_DELETE,
        SystemPermissions.OCCURRENCES_EDIT,
        SystemPermissions.OCCURRENCES_VIEW_OWN,
        SystemPermissions.SPACES_RESERVATE,
        SystemPermissions.SPACES_VIEW_ALL,
    },
    # Coordenador
    UserRole.COORDINATOR: {*SystemPermissions} - COORDINATOR_EXCEPTION_ROLES,
    # Porteiro
    # Admin do sistema
    UserRole.ADMIN: {*SystemPermissions},
}

# Permissões especiais para o Professor Diretor de Turma
TUTOR_EXTRA_PERMISSIONS = (
    {
        SystemPermissions.CERTIFICATES_VALIDATE,
        SystemPermissions.REPORTS_VIEW_OWN_CLASS,
    },
)

# Adiciona permissões para todos os usuários
for user_role, permissions in ROLE_PERMISSIONS.items():
    permissions.update({
        SystemPermissions.USER_EDIT,
        SystemPermissions.SUGGESTIONS_SUBMIT,
        SystemPermissions.USER_VIEW_OWN,
    })
