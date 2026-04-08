"""
Testes de shared/rbac/ e shared/db/ — suite completa.

Organização:
  1. rbac/helpers.py       — get_user_permissions, user_has_permission/any/all
  2. rbac/dependencies.py  — PermissionChecker, AnyPermissionChecker, role_required
  3. shared/db/database.py — get_session
  4. shared/db/database.py — ssl='require'
  5. shared/db/seed.py     — funções de seed e username
"""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

import app.shared.db.database as db_module
from app.domains.users.models import User
from app.shared.db.registry import mapper_registry
from app.shared.db.seed import (
    _base_username,
    _gerar_username_unico,
    _normalizar,
    seed_classrooms,
    seed_real_users,
    seed_test_users,
)
from app.shared.rbac.dependencies import (
    require_all_permissions,
    require_any_permission,
    require_permission,
)
from app.shared.rbac.helpers import (
    get_user_permissions,
    user_has_all_permissions,
    user_has_any_permission,
    user_has_permission,
)
from app.shared.rbac.permissions import (
    TUTOR_EXTRA_PERMISSIONS,
    SystemPermissions,
)
from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token, get_password_hash
from tests.conftest import _make_user, make_token


# ===========================================================================
# 1. rbac/helpers.py — permissões por role e is_tutor
# ===========================================================================


def test_is_tutor_on_teacher_adds_extra_perms(tutor_user):
    """Professor DT (TEACHER + is_tutor=True) recebe TUTOR_EXTRA_PERMISSIONS."""
    perms = get_user_permissions(tutor_user)
    for extra in TUTOR_EXTRA_PERMISSIONS:
        assert extra in perms


def test_is_tutor_on_student_does_not_add_extra_perms(student_user):
    """Aluno com is_tutor=True não recebe extras (regra: só TEACHER)."""
    student_user.is_tutor = True
    perms = get_user_permissions(student_user)
    for extra in TUTOR_EXTRA_PERMISSIONS:
        assert extra not in perms


def test_user_has_permission_true(teacher_user):
    assert (
        user_has_permission(teacher_user, SystemPermissions.OCCURRENCES_CREATE)
        is True
    )


def test_user_has_permission_false(student_user):
    assert (
        user_has_permission(student_user, SystemPermissions.OCCURRENCES_CREATE)
        is False
    )


def test_user_has_any_permission_true(teacher_user):
    assert (
        user_has_any_permission(
            teacher_user,
            {
                SystemPermissions.OCCURRENCES_CREATE,
                SystemPermissions.USER_CHANGE_ROLE,
            },
        )
        is True
    )


def test_user_has_any_permission_false(student_user):
    assert (
        user_has_any_permission(
            student_user,
            {
                SystemPermissions.OCCURRENCES_CREATE,
                SystemPermissions.USER_CHANGE_ROLE,
            },
        )
        is False
    )


def test_user_has_all_permissions_true(coordinator_user):
    assert (
        user_has_all_permissions(
            coordinator_user,
            {
                SystemPermissions.OCCURRENCES_VIEW_ALL,
                SystemPermissions.OCCURRENCES_CREATE,
            },
        )
        is True
    )


def test_user_has_all_permissions_false(teacher_user):
    """Professor não tem OCCURRENCES_VIEW_ALL."""
    assert (
        user_has_all_permissions(
            teacher_user,
            {
                SystemPermissions.OCCURRENCES_CREATE,
                SystemPermissions.OCCURRENCES_VIEW_ALL,
            },
        )
        is False
    )


# ===========================================================================
# 2. rbac/dependencies.py — helpers de verificação e AnyPermissionChecker
# ===========================================================================


def test_require_permission_true(teacher_user):
    assert (
        require_permission(teacher_user, SystemPermissions.OCCURRENCES_CREATE)
        is True
    )


def test_require_permission_false(student_user):
    assert (
        require_permission(student_user, SystemPermissions.OCCURRENCES_CREATE)
        is False
    )


def test_require_any_permission_true(teacher_user):
    assert (
        require_any_permission(
            teacher_user, SystemPermissions.OCCURRENCES_CREATE
        )
        is True
    )


def test_require_any_permission_false(student_user):
    assert (
        require_any_permission(
            student_user, SystemPermissions.OCCURRENCES_CREATE
        )
        is False
    )


def test_require_all_permissions_true(coordinator_user):
    assert (
        require_all_permissions(
            coordinator_user,
            {
                SystemPermissions.OCCURRENCES_VIEW_ALL,
                SystemPermissions.OCCURRENCES_CREATE,
            },
        )
        is True
    )


def test_require_all_permissions_false(teacher_user):
    assert (
        require_all_permissions(
            teacher_user,
            {
                SystemPermissions.OCCURRENCES_CREATE,
                SystemPermissions.OCCURRENCES_VIEW_ALL,
            },
        )
        is False
    )


def test_require_any_permission_inline_true():
    """require_any_permission via User inline (sem fixture async)."""
    teacher = User(
        username='prof_rbac',
        email='prof_rbac@test.com',
        password='hash',
        first_name='Prof',
        last_name='Rbac',
        role=UserRole.TEACHER,
        is_tutor=False,
        is_active=True,
    )
    assert (
        require_any_permission(teacher, SystemPermissions.OCCURRENCES_CREATE)
        is True
    )


def test_require_all_permissions_inline_true():
    """require_all_permissions via User inline."""
    coord = User(
        username='coord_rbac',
        email='coord_rbac@test.com',
        password='hash',
        first_name='Coord',
        last_name='Rbac',
        role=UserRole.COORDINATOR,
        is_tutor=False,
        is_active=True,
    )
    assert (
        require_all_permissions(
            coord,
            {
                SystemPermissions.OCCURRENCES_VIEW_ALL,
                SystemPermissions.OCCURRENCES_CREATE,
            },
        )
        is True
    )


def test_require_all_permissions_inline_false():
    """require_all_permissions com permissão ausente → False."""
    student = User(
        username='aluno_rbac',
        email='aluno_rbac@test.com',
        password='hash',
        first_name='Aluno',
        last_name='Rbac',
        role=UserRole.STUDENT,
        is_tutor=False,
        is_active=True,
    )
    assert (
        require_all_permissions(
            student, {SystemPermissions.OCCURRENCES_VIEW_ALL}
        )
        is False
    )


async def test_any_permission_checker_403_via_http(client, session):
    """
    AnyPermissionChecker → 403 quando usuário não tem nenhuma das permissões.
    Guardian tem SCHEDULES_VIEW_CHILD mas não VIEW_ALL nem VIEW_OWN →
    GET /schedules/teacher/{id} retorna 403.
    """
    guardian = await _make_user(session, role=UserRole.GUARDIAN)
    tok = create_access_token(data={'sub': guardian.email})
    resp = client.get(
        '/schedules/teacher/1',
        headers={'Authorization': f'Bearer {tok}'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Insufficient permissions'


# ===========================================================================
# 3. shared/db/database.py — get_session
# ===========================================================================


async def test_get_session_yields_async_session():
    """get_session deve produzir uma AsyncSession."""
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.create_all)

    original_engine = db_module.engine
    db_module.engine = engine

    try:
        gen = db_module.get_session()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        try:
            await gen.aclose()
        except StopAsyncIteration:
            pass
    finally:
        db_module.engine = original_engine
        await engine.dispose()


# ===========================================================================
# 4. shared/db/database.py — ssl='require'
# ===========================================================================


def test_database_engine_production_uses_ssl():
    """
    Branch `production` do database.py cria engine com ssl='require'.
    Cobre o statement faltante na linha do connect_args={'ssl': 'require'}.
    """
    mock_engine = MagicMock()

    with (
        patch('app.core.settings.settings') as mock_settings,
        patch(
            'sqlalchemy.ext.asyncio.create_async_engine',
            return_value=mock_engine,
        ) as mock_create,
    ):
        mock_settings.ENVIRONMENT = 'production'
        mock_settings.RESOLVED_DATABASE_URL = 'postgresql+asyncpg://u:p@h/db'

        import importlib
        import app.shared.db.database as db_module

        importlib.reload(db_module)

        mock_create.assert_called_once_with(
            'postgresql+asyncpg://u:p@h/db',
            future=True,
            connect_args={'ssl': 'require'},
        )


def test_database_engine_development_no_ssl():
    """
    Branch `development` do database.py cria engine sem ssl.
    Confirma que o caminho não-produção NÃO passa connect_args.
    """
    with (
        patch('app.core.settings.settings') as mock_settings,
        patch(
            'sqlalchemy.ext.asyncio.create_async_engine',
        ) as mock_create,
    ):
        mock_settings.ENVIRONMENT = 'development'
        mock_settings.RESOLVED_DATABASE_URL = 'sqlite+aiosqlite:///:memory:'

        import importlib
        import app.shared.db.database as db_module

        importlib.reload(db_module)

        mock_create.assert_called_once_with(
            'sqlite+aiosqlite:///:memory:', future=True
        )


# ===========================================================================
# 5. shared/db/seed.py — utilitários de seed
# ===========================================================================


async def test_seed_classrooms_creates_all(session):
    """seed_classrooms → cria 12 salas."""
    id_map = await seed_classrooms(session)
    assert len(id_map) == 12
    for k in range(1, 13):
        assert k in id_map


async def test_seed_classrooms_idempotent(session):
    """seed_classrooms chamado duas vezes → não duplica."""
    map1 = await seed_classrooms(session)
    map2 = await seed_classrooms(session)
    assert map1 == map2


async def test_seed_test_users_creates_users(session):
    """seed_test_users → cria usuários de todas as roles."""
    await seed_test_users(session)
    result = await session.scalars(select(User))
    emails = [u.email for u in result.all()]
    assert 'admin@edupbl.com' in emails
    assert 'professor@edupbl.com' in emails
    assert 'aluno@edupbl.com' in emails


async def test_seed_test_users_idempotent(session):
    """seed_test_users chamado duas vezes → não duplica usuários."""
    await seed_test_users(session)
    c1 = len((await session.scalars(select(User))).all())
    await seed_test_users(session)
    c2 = len((await session.scalars(select(User))).all())
    assert c1 == c2


def test_normalizar():
    """_normalizar → remove acentos e converte para minúsculas."""
    assert _normalizar('João') == 'joao'
    assert _normalizar('Ângela') == 'angela'
    assert _normalizar('Gonçalves') == 'goncalves'
    assert _normalizar('São Paulo') == 'saopaulo'


def test_base_username():
    """_base_username → primeiro.ultimo sem acentos."""
    assert _base_username('João', 'Silva Santos') == 'joao.santos'
    assert _base_username('Maria Clara', 'Rodrigues') == 'maria.rodrigues'
    assert _base_username('Ana', 'Lima') == 'ana.lima'


async def test_gerar_username_unico_sem_conflito(session):
    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima'
    assert 'ana.lima' in usados


async def test_gerar_username_unico_conflito_no_lote(session):
    usados = {'ana.lima'}
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima1'


async def test_gerar_username_unico_conflito_no_banco(session):
    u = User(
        username='pedro.costa',
        email='pedro.seed@test.com',
        password=get_password_hash('test'),
        first_name='Pedro',
        last_name='Costa',
        role=UserRole.STUDENT,
        is_tutor=False,
        is_active=True,
    )
    session.add(u)
    await session.commit()

    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'Pedro', 'Costa', usados)
    assert username == 'pedro.costa1'


async def test_seed_real_users_missing_csv(session, capsys):
    """CSV inexistente → não lança exceção."""
    await seed_real_users(session)
    capsys.readouterr()


async def test_seed_real_users_with_malformed_csv(session, tmp_path, capsys):
    """seed.py lines 339-340, 349: CSV com linha inválida → erros contabilizados."""
    csv_content = (
        'nome,sobrenome,email,senha\n'
        'Joao,Silva,joao.seed@test.com,senha123\n'
        ',,,\n'
    )
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    (usuarios_dir / 'admins.csv').write_text(csv_content, encoding='utf-8')

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    captured = capsys.readouterr()
    assert 'erro' in captured.out.lower() or 'criados' in captured.out.lower()
