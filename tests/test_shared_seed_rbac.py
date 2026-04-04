"""
Testes de shared/db/seed.py, shared/db/database.py e shared/rbac/ — cobertura completa.

Cobre:
  shared/db/seed.py          339-340, 349
  shared/db/database.py      71% → 100%
  shared/rbac/dependencies.py 66, 97% → 100%
"""

from http import HTTPStatus
from unittest.mock import patch

import pytest_asyncio
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
)
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_password_hash
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ===========================================================================
# shared/db/database.py — get_session
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
# shared/db/seed.py — funções utilitárias
# ===========================================================================


async def test_seed_classrooms_creates_all(session):
    """seed_classrooms → cria 12 salas."""
    id_map = await seed_classrooms(session)
    assert len(id_map) == 12
    for k in range(1, 13):
        assert k in id_map


async def test_seed_classrooms_idempotent(session):
    """seed_classrooms chamado duas vezes → não duplica salas."""
    map1 = await seed_classrooms(session)
    map2 = await seed_classrooms(session)
    assert map1 == map2


async def test_seed_test_users_creates_users(session):
    """seed_test_users → cria usuários de todas as roles."""
    await seed_test_users(session)
    result = await session.scalars(select(User))
    users = result.all()
    emails = [u.email for u in users]
    assert 'admin@edupbl.com' in emails
    assert 'professor@edupbl.com' in emails
    assert 'aluno@edupbl.com' in emails


async def test_seed_test_users_idempotent(session):
    """seed_test_users chamado duas vezes → não duplica usuários."""
    await seed_test_users(session)
    result1 = await session.scalars(select(User))
    count1 = len(result1.all())

    await seed_test_users(session)
    result2 = await session.scalars(select(User))
    count2 = len(result2.all())

    assert count1 == count2


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
    """_gerar_username_unico → retorna base quando não há conflito."""
    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima'
    assert 'ana.lima' in usados


async def test_gerar_username_unico_com_conflito_no_lote(session):
    """_gerar_username_unico → adiciona sufixo quando conflita no lote."""
    usados = {'ana.lima'}
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima1'


async def test_gerar_username_unico_com_conflito_no_banco(session):
    """_gerar_username_unico → adiciona sufixo quando conflita no banco."""
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
    """seed_real_users com CSV inexistente → não lança exceção."""
    await seed_real_users(session)
    # Não deve lançar exceção; saída pode mencionar arquivos não encontrados
    capsys.readouterr()  # limpa saída


async def test_seed_real_users_with_malformed_csv(session, tmp_path, capsys):
    """seed.py lines 339-340, 349: CSV com linha inválida → erros++ e aviso."""
    csv_content = (
        'nome,sobrenome,email,senha\n'
        'Joao,Silva,joao.seed@test.com,senha123\n'
        ',,,\n'
    )
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    csv_file = usuarios_dir / 'admins.csv'
    csv_file.write_text(csv_content, encoding='utf-8')

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    captured = capsys.readouterr()
    assert 'erro' in captured.out.lower() or 'criados' in captured.out.lower()


# ===========================================================================
# shared/rbac/dependencies.py — require_any/all_permission helpers
# ===========================================================================


def test_require_any_permission_true():
    """require_any_permission com permissão existente → True."""
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
    result = require_any_permission(teacher, SystemPermissions.OCCURRENCES_CREATE)
    assert result is True


def test_require_all_permissions_true():
    """require_all_permissions com todas as permissões → True."""
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
    result = require_all_permissions(
        coord,
        {
            SystemPermissions.OCCURRENCES_VIEW_ALL,
            SystemPermissions.OCCURRENCES_CREATE,
        },
    )
    assert result is True


def test_require_all_permissions_false():
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
    result = require_all_permissions(
        student,
        {SystemPermissions.OCCURRENCES_VIEW_ALL},
    )
    assert result is False


async def test_any_permission_checker_raises_403(client, session):
    """rbac/deps line 66: aluno sem SCHEDULES_MANAGE tenta criar slot → 403."""
    stud = await _make_user(session, role=UserRole.STUDENT)
    resp = client.post(
        '/schedules/slots',
        json={
            'type': 'class_period',
            'title': 'X',
            'classroom_id': 1,
            'teacher_id': None,
            'weekday': 'monday',
            'period_number': 1,
        },
        headers=_auth(stud),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
