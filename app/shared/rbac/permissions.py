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
    CERTIFICATES_REVIEW = 'certificates:review'  # approve/reject
    CERTIFICATES_SUBMIT = 'certificates:submit'
    CERTIFICATES_VALIDATE = 'certificates:validate'

    # ── Atrasos ────────────────────────────────────────────────────── #
    DELAYS_CREATE = 'delays:create'
    DELAYS_REVIEW = 'delays:review'  # approve/reject
    DELAYS_VIEW_ALL = 'delays:read_all'  # Todos os atrasos do sistema
    DELAYS_VIEW_CHILD = 'delays:read_child'  # Atrasos do(s) filho(s)
    DELAYS_VIEW_OWN = 'delays:read_own'  # Meus próprios atrasos
    DELAYS_VIEW_OWN_CLASSROOM = (
        'delays:read_own_classroom'  # Atrasos da minha turma (DT)
    )

    # ── Espaços ────────────────────────────────────────────────────── #
    SPACES_MANAGE = 'spaces:manage'  # create, edit, delete
    SPACES_RESERVATE = 'spaces:reservate'
    SPACES_VIEW_ALL = 'spaces:read_all'

    # ── Horários ───────────────────────────────────────────────────── #
    SCHEDULES_MANAGE = 'schedules:manage'  # create, edit, delete
    SCHEDULES_VIEW_OWN = 'schedules:read_own'  # Minha turma / meu contexto
    SCHEDULES_VIEW_CHILD = 'schedules:read_child'  # Turma(s) do(s) filho(s)
    SCHEDULES_VIEW_ALL = (
        'schedules:read_all'  # Acesso amplo (coord/admin/porteiro/prof)
    )

    # ── Mídias ─────────────────────────────────────────────────────── #
    MEDIAS_MANAGE = 'medias:manage'  # create, edit, delete
    MEDIAS_RESERVATE = 'medias:reservate'
    MEDIAS_VIEW_ALL = 'medias:read_all'

    # ── Ocorrências ────────────────────────────────────────────────── #
    OCCURRENCES_CREATE = 'occurrences:create'
    OCCURRENCES_DELETE = 'occurrences:delete'
    OCCURRENCES_EDIT = 'occurrences:update'
    OCCURRENCES_VIEW_ALL = 'occurrences:read_all'  # Todas as ocorrências
    OCCURRENCES_VIEW_CHILD = (
        'occurrences:read_child'  # Ocorrências do(s) filho(s)
    )
    OCCURRENCES_VIEW_OWN = 'occurrences:read_own'  # Criei OU sou o aluno
    OCCURRENCES_VIEW_OWN_CLASSROOM = 'occurrences:read_own_classroom'  # Todas as ocorrências da minha turma (DT)

    # ── Relatórios ─────────────────────────────────────────────────── #
    REPORTS_VIEW_ALL = 'reports:view_all'  # Relatórios de todas as turmas
    REPORTS_VIEW_OWN_CLASSROOM = (
        'reports:view_own_classroom'  # Relatórios da minha turma
    )

    # ── Sugestões ──────────────────────────────────────────────────── #
    SUGGESTIONS_MODERATE = 'suggestions:moderate'
    SUGGESTIONS_SUBMIT = 'suggestions:submit'

    # ── Usuários ───────────────────────────────────────────────────── #
    USER_CHANGE_ROLE = 'users:change_role'
    USER_CREATE = 'users:create'
    USER_DELETE = 'users:delete'
    USER_EDIT = 'users:update'
    USER_EDIT_OWN_CLASSROOM = 'users:update_own_classroom'  # DT edita alunos da própria turma (apenas campos permitidos)
    USER_VIEW_ALL = 'users:read_all'  # Todos os usuários
    USER_VIEW_CHILD = 'users:read_child'  # Informações do(s) filho(s)
    USER_VIEW_OWN = 'users:read_own'  # Próprias informações
    USER_VIEW_STUDENTS = (
        'users:read_students'  # Lista reduzida de alunos (porteiro/professor)
    )


# Permissões que o Coordenador NÃO possui
# (apenas o Admin pode alterar o role de usuários)
COORDINATOR_EXCEPTION_ROLES = {SystemPermissions.USER_CHANGE_ROLE}

# Mapeamento role → conjunto de permissões específicas da role
ROLE_PERMISSIONS: dict[UserRole, set[SystemPermissions]] = {
    # Admin tem todas as permissões
    UserRole.ADMIN: {*SystemPermissions},
    # Aluno
    UserRole.STUDENT: {
        SystemPermissions.CERTIFICATES_SUBMIT,
        SystemPermissions.DELAYS_VIEW_OWN,
        SystemPermissions.OCCURRENCES_VIEW_OWN,
        SystemPermissions.SCHEDULES_VIEW_OWN,
    },
    # Coordenador tem tudo, exceto USER_CHANGE_ROLE
    UserRole.COORDINATOR: {*SystemPermissions} - COORDINATOR_EXCEPTION_ROLES,
    # Porteiro
    UserRole.PORTER: {
        SystemPermissions.DELAYS_CREATE,
        SystemPermissions.DELAYS_VIEW_ALL,
        SystemPermissions.SCHEDULES_VIEW_ALL,
        SystemPermissions.USER_VIEW_STUDENTS,
    },
    # Professor
    UserRole.TEACHER: {
        SystemPermissions.MEDIAS_RESERVATE,
        SystemPermissions.MEDIAS_VIEW_ALL,
        SystemPermissions.OCCURRENCES_CREATE,
        SystemPermissions.OCCURRENCES_DELETE,
        SystemPermissions.OCCURRENCES_EDIT,
        SystemPermissions.OCCURRENCES_VIEW_OWN,
        SystemPermissions.SCHEDULES_VIEW_ALL,
        SystemPermissions.SPACES_RESERVATE,
        SystemPermissions.SPACES_VIEW_ALL,
        SystemPermissions.USER_VIEW_STUDENTS,
    },
    # Responsável
    UserRole.GUARDIAN: {
        SystemPermissions.CERTIFICATES_SUBMIT,
        SystemPermissions.DELAYS_VIEW_CHILD,
        SystemPermissions.OCCURRENCES_VIEW_CHILD,
        SystemPermissions.SCHEDULES_VIEW_CHILD,
        SystemPermissions.USER_VIEW_CHILD,
    },
}

# Permissões extras exclusivas do Professor Diretor de Turma (TEACHER + is_tutor=True)
TUTOR_EXTRA_PERMISSIONS: set[SystemPermissions] = {
    SystemPermissions.CERTIFICATES_VALIDATE,
    SystemPermissions.DELAYS_VIEW_OWN_CLASSROOM,
    SystemPermissions.OCCURRENCES_VIEW_OWN_CLASSROOM,  # Ver todas as ocorrências da própria turma
    SystemPermissions.REPORTS_VIEW_OWN_CLASSROOM,
    SystemPermissions.USER_EDIT_OWN_CLASSROOM,  # Editar campos permitidos de alunos da própria turma
}

# Permissões base concedidas a TODOS os usuários, independentemente da role
# NOTA: USER_EDIT não entra aqui - é permissão privilegiada (admin/coord)
# para editar *outros* usuários. O auto-edit do proprio perfil (campo phone)
# é controlado no backend pelo check current_user.id == user_id.
_BASE_PERMISSIONS: set[SystemPermissions] = {
    SystemPermissions.USER_VIEW_OWN,
    SystemPermissions.SUGGESTIONS_SUBMIT,
}

for _perms in ROLE_PERMISSIONS.values():
    _perms.update(_BASE_PERMISSIONS)
