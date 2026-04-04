"""
Testes de integração com o banco de dados e seed — cobertura 100%.

Cobre:
  - app/shared/db/seed.py  (seed_classrooms, seed_test_users, seed_real_users,
                            _normalizar, _base_username, _gerar_username_unico,
                            _import_avatar)
  - Criação básica de User no banco
"""

import csv
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.domains.users.models import Classroom, User
from app.shared.db.seed import (
    SEED_IMAGES_DIR,
    USUARIOS_DIR,
    _base_username,
    _import_avatar,
    _normalizar,
    seed_classrooms,
    seed_real_users,
    seed_test_users,
)
from app.shared.rbac.roles import UserRole


# ===========================================================================
# Criação básica de usuário no banco
# ===========================================================================


async def test_create_user(session, mock_db_time):
    """Persiste um User e verifica todos os campos escalares."""
    from datetime import datetime

    with mock_db_time(model=User, time=datetime(2024, 1, 1)) as time:
        new_user = User(
            username='alice',
            first_name='alice',
            last_name='liddell',
            password='secret',
            email='teste@test',
            role=UserRole.TEACHER,
            is_tutor=True,
        )
        session.add(new_user)
        await session.commit()

    user = await session.scalar(select(User).where(User.username == 'alice'))

    assert user.id == 1
    assert user.username == 'alice'
    assert user.password == 'secret'
    assert user.first_name == 'alice'
    assert user.last_name == 'liddell'
    assert user.email == 'teste@test'
    assert user.role == UserRole.TEACHER
    assert user.is_active is True
    assert user.is_tutor is True
    assert user.must_change_password is False
    assert user.classroom_id is None
    assert user.created_at == time
    assert user.updated_at == time


# ===========================================================================
# _normalizar
# ===========================================================================


def test_normalizar_removes_accents():
    from app.shared.db.seed import _normalizar

    assert _normalizar('João') == 'joao'
    assert _normalizar('Ângela') == 'angela'
    assert _normalizar('Gonçalves') == 'goncalves'


def test_normalizar_removes_spaces():
    from app.shared.db.seed import _normalizar

    assert _normalizar('São Paulo') == 'saopaulo'


def test_normalizar_keeps_digits():
    from app.shared.db.seed import _normalizar

    assert _normalizar('Turma3') == 'turma3'


# ===========================================================================
# _base_username
# ===========================================================================


def test_base_username_simple():
    assert _base_username('João', 'Silva') == 'joao.silva'


def test_base_username_compound_first_name():
    """Só o primeiro token do nome é usado."""
    assert _base_username('Maria José', 'Costa') == 'maria.costa'


def test_base_username_compound_last_name():
    """Só o último token do sobrenome é usado."""
    assert _base_username('Ana', 'Gomes da Costa') == 'ana.costa'


# ===========================================================================
# _gerar_username_unico
# ===========================================================================


async def test_gerar_username_unico_no_conflict(session):
    from app.shared.db.seed import _gerar_username_unico

    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'João', 'Silva', usados)
    assert username == 'joao.silva'
    assert 'joao.silva' in usados


async def test_gerar_username_unico_batch_conflict(session):
    """Se já foi usado no lote, incrementa o sufixo."""
    from app.shared.db.seed import _gerar_username_unico

    usados: set[str] = {'joao.silva'}
    username = await _gerar_username_unico(session, 'João', 'Silva', usados)
    assert username == 'joao.silva1'


async def test_gerar_username_unico_db_conflict(session):
    """Se já existe no banco, incrementa o sufixo."""
    from app.shared.db.seed import _gerar_username_unico

    # Cria usuário no banco com o username base
    u = User(
        username='joao.costa',
        email='joao@costa.com',
        password='x',
        first_name='João',
        last_name='Costa',
        role=UserRole.STUDENT,
    )
    session.add(u)
    await session.commit()

    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'João', 'Costa', usados)
    assert username == 'joao.costa1'


async def test_gerar_username_unico_multiple_conflicts(session):
    """Conflito duplo → incrementa até encontrar livre."""
    from app.shared.db.seed import _gerar_username_unico

    for i, (email, uname) in enumerate([
        ('a@b.com', 'ana.lima'),
        ('c@d.com', 'ana.lima1'),
    ]):
        u = User(
            username=uname,
            email=email,
            password='x',
            first_name='Ana',
            last_name='Lima',
            role=UserRole.STUDENT,
        )
        session.add(u)
    await session.commit()

    usados: set[str] = set()
    username = await _gerar_username_unico(session, 'Ana', 'Lima', usados)
    assert username == 'ana.lima2'


# ===========================================================================
# seed_classrooms
# ===========================================================================


async def test_seed_classrooms_creates_all(session):
    """seed_classrooms cria as 12 salas padrão."""
    id_map = await seed_classrooms(session)
    assert len(id_map) == 12
    result = await session.scalars(select(Classroom))
    assert len(result.all()) == 12


async def test_seed_classrooms_idempotent(session):
    """Chamar seed_classrooms duas vezes não duplica salas."""
    await seed_classrooms(session)
    await seed_classrooms(session)
    result = await session.scalars(select(Classroom))
    assert len(result.all()) == 12


async def test_seed_classrooms_returns_id_map(session):
    """Retorna mapeamento {numero: id_no_banco}."""
    id_map = await seed_classrooms(session)
    assert 1 in id_map
    assert 12 in id_map
    # IDs são inteiros positivos
    assert all(isinstance(v, int) and v > 0 for v in id_map.values())


# ===========================================================================
# seed_test_users
# ===========================================================================


async def test_seed_test_users_creates_expected_roles(session):
    """seed_test_users cria um usuário de cada role principal."""
    await seed_test_users(session)
    result = await session.scalars(select(User))
    users = result.all()
    roles = {u.role for u in users}
    assert UserRole.ADMIN in roles
    assert UserRole.COORDINATOR in roles
    assert UserRole.TEACHER in roles
    assert UserRole.STUDENT in roles
    assert UserRole.PORTER in roles
    assert UserRole.GUARDIAN in roles


async def test_seed_test_users_idempotent(session):
    """Chamar duas vezes não duplica usuários."""
    await seed_test_users(session)
    count_first = len((await session.scalars(select(User))).all())
    await seed_test_users(session)
    count_second = len((await session.scalars(select(User))).all())
    assert count_first == count_second


async def test_seed_test_users_must_change_password_false(session):
    """Usuários de seed de dev têm must_change_password=False."""
    await seed_test_users(session)
    result = await session.scalars(select(User))
    for user in result.all():
        assert user.must_change_password is False


# ===========================================================================
# _import_avatar
# ===========================================================================


def test_import_avatar_file_not_found(tmp_path):
    """Avatar não encontrado → retorna None e não aborta."""
    with patch('app.shared.db.seed.SEED_IMAGES_DIR', tmp_path):
        result = _import_avatar(99, 'inexistente.jpg')
    assert result is None


def test_import_avatar_success(tmp_path):
    """Avatar encontrado → processado e salvo em data/avatars/."""
    from PIL import Image
    from app.domains.users import routers as user_routers

    # Cria imagem de origem em seed-images
    seed_dir = tmp_path / 'seed-images'
    seed_dir.mkdir()
    src = seed_dir / 'foto.jpg'
    Image.new('RGB', (100, 100), color=(255, 0, 0)).save(src, format='JPEG')

    # Avatares serão salvos em tmp_path/avatars
    avatar_dir = tmp_path / 'avatars'

    with (
        patch('app.shared.db.seed.SEED_IMAGES_DIR', seed_dir),
        patch.object(user_routers, '_AVATAR_DIR', avatar_dir),
    ):
        result = _import_avatar(42, 'foto.jpg')

    assert result == 'avatars/42.webp'
    assert (avatar_dir / '42.webp').exists()


def test_import_avatar_rgba_converted(tmp_path):
    """Imagem RGBA é convertida para RGB antes de salvar."""
    from PIL import Image
    from app.domains.users import routers as user_routers

    seed_dir = tmp_path / 'seed-images'
    seed_dir.mkdir()
    src = seed_dir / 'rgba.png'
    Image.new('RGBA', (50, 80), color=(0, 255, 0, 200)).save(src, format='PNG')

    avatar_dir = tmp_path / 'avatars'

    with (
        patch('app.shared.db.seed.SEED_IMAGES_DIR', seed_dir),
        patch.object(user_routers, '_AVATAR_DIR', avatar_dir),
    ):
        result = _import_avatar(7, 'rgba.png')

    assert result == 'avatars/7.webp'


def test_import_avatar_processing_error(tmp_path):
    """Erro de processamento → retorna None, não aborta."""
    from app.domains.users import routers as user_routers

    seed_dir = tmp_path / 'seed-images'
    seed_dir.mkdir()
    # Arquivo corrompido
    bad = seed_dir / 'bad.jpg'
    bad.write_bytes(b'not-an-image')

    avatar_dir = tmp_path / 'avatars'

    with (
        patch('app.shared.db.seed.SEED_IMAGES_DIR', seed_dir),
        patch.object(user_routers, '_AVATAR_DIR', avatar_dir),
    ):
        result = _import_avatar(1, 'bad.jpg')

    assert result is None


# ===========================================================================
# seed_real_users — CSV completo
# ===========================================================================


def _write_csv(directory: Path, filename: str, content: str):
    """Escreve um CSV de teste no diretório dado."""
    (directory / filename).write_text(
        textwrap.dedent(content), encoding='utf-8'
    )


async def test_seed_real_users_skips_missing_files(session, tmp_path):
    """Arquivo CSV ausente → aviso e continua sem erro."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    # Nenhum arquivo criado

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(select(User))
    # Só as salas foram criadas, nenhum usuário
    assert len(result.all()) == 0


async def test_seed_real_users_creates_from_csv(session, tmp_path):
    """CSV de admins válido → usuários criados no banco."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()

    _write_csv(
        usuarios_dir,
        'admins.csv',
        """\
        nome,sobrenome,email,senha,role,avatar
        Jose,Silva,jose@test.com,Senha123!,admin,
        Maria,Costa,maria@test.com,Senha123!,admin,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(select(User))
    users = result.all()
    assert len(users) == 2
    assert all(u.role == UserRole.ADMIN for u in users)
    assert all(u.must_change_password is True for u in users)


async def test_seed_real_users_skips_existing_emails(session, tmp_path):
    """Email já existente no banco → linha ignorada (idempotente)."""
    from tests.conftest import _make_user

    existing = await _make_user(session, email='jose@dup.com')

    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    _write_csv(
        usuarios_dir,
        'admins.csv',
        f"""\
        nome,sobrenome,email,senha,role,avatar
        Jose,Silva,{existing.email},Senha123!,admin,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(select(User))
    # Deve ter só o usuário original (não duplicado)
    emails = [u.email for u in result.all()]
    assert emails.count(existing.email) == 1


async def test_seed_real_users_with_sala(session, tmp_path):
    """CSV de alunos com coluna sala → classroom_id preenchido."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    _write_csv(
        usuarios_dir,
        'alunos.csv',
        """\
        nome,sobrenome,email,senha,role,sala,avatar
        Pedro,Lima,pedro@test.com,Aluno123!,student,1,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(
        select(User).where(User.email == 'pedro@test.com')
    )
    aluno = result.first()
    assert aluno is not None
    assert aluno.classroom_id is not None


async def test_seed_real_users_duplicate_username_resolved(session, tmp_path):
    """Dois usuários com mesmo nome base → usernames distintos gerados."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    _write_csv(
        usuarios_dir,
        'admins.csv',
        """\
        nome,sobrenome,email,senha,role,avatar
        Ana,Costa,ana1@test.com,Senha!,admin,
        Ana,Costa,ana2@test.com,Senha!,admin,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(select(User))
    usernames = [u.username for u in result.all()]
    assert len(usernames) == len(set(usernames)), 'Usernames devem ser únicos'


async def test_seed_real_users_with_avatar(session, tmp_path):
    """CSV com coluna avatar preenchida → avatar processado e salvo."""
    from PIL import Image
    from app.domains.users import routers as user_routers

    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()

    seed_dir = tmp_path / 'seed-images'
    seed_dir.mkdir()
    img_file = seed_dir / 'foto.jpg'
    Image.new('RGB', (100, 100), color=(10, 20, 30)).save(
        img_file, format='JPEG'
    )

    avatar_dir = tmp_path / 'avatars'

    _write_csv(
        usuarios_dir,
        'admins.csv',
        """\
        nome,sobrenome,email,senha,role,avatar
        Carlos,Mendes,carlos@test.com,Senha!,admin,foto.jpg
    """,
    )

    with (
        patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir),
        patch('app.shared.db.seed.SEED_IMAGES_DIR', seed_dir),
        patch.object(user_routers, '_AVATAR_DIR', avatar_dir),
    ):
        await seed_real_users(session)

    result = await session.scalars(
        select(User).where(User.email == 'carlos@test.com')
    )
    user = result.first()
    assert user is not None
    assert user.avatar_url == f'avatars/{user.id}.webp'


async def test_seed_real_users_with_avatar_and_sala(session, tmp_path):
    """CSV de alunos com avatar + sala → classroom_id preenchido E avatar salvo.

    Cobre o branch `if cid is not None` dentro do loop `novos_com_avatar`,
    que permanecia descoberto pelos demais testes (avatar sem sala ou sala sem avatar).
    """
    from PIL import Image
    from app.domains.users import routers as user_routers

    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()

    seed_dir = tmp_path / 'seed-images'
    seed_dir.mkdir()
    img_file = seed_dir / 'foto.jpg'
    Image.new('RGB', (100, 100), color=(10, 20, 30)).save(
        img_file, format='JPEG'
    )

    avatar_dir = tmp_path / 'avatars'

    _write_csv(
        usuarios_dir,
        'alunos.csv',
        """\
        nome,sobrenome,email,senha,role,sala,avatar
        Beatriz,Souza,beatriz@test.com,Aluno123!,student,1,foto.jpg
    """,
    )

    with (
        patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir),
        patch('app.shared.db.seed.SEED_IMAGES_DIR', seed_dir),
        patch.object(user_routers, '_AVATAR_DIR', avatar_dir),
    ):
        await seed_real_users(session)

    result = await session.scalars(
        select(User).where(User.email == 'beatriz@test.com')
    )
    aluna = result.first()
    assert aluna is not None
    assert aluna.classroom_id is not None, (
        'classroom_id deve ser preenchido via setattr após flush'
    )
    assert aluna.avatar_url == f'avatars/{aluna.id}.webp', (
        'avatar_url deve ser salvo normalmente'
    )


async def test_seed_real_users_avatar_not_found(session, tmp_path):
    """Avatar referenciado no CSV mas ausente em seed-images → usuário criado sem avatar."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    seed_dir = tmp_path / 'seed-images'
    seed_dir.mkdir()

    _write_csv(
        usuarios_dir,
        'admins.csv',
        """\
        nome,sobrenome,email,senha,role,avatar
        Fulano,Tal,fulano@test.com,Senha!,admin,inexistente.jpg
    """,
    )

    with (
        patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir),
        patch('app.shared.db.seed.SEED_IMAGES_DIR', seed_dir),
    ):
        await seed_real_users(session)

    result = await session.scalars(
        select(User).where(User.email == 'fulano@test.com')
    )
    user = result.first()
    assert user is not None
    assert user.avatar_url is None


async def test_seed_real_users_invalid_row_logged(session, tmp_path, capsys):
    """Linha malformada no CSV → erro capturado, outros usuários criados."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    _write_csv(
        usuarios_dir,
        'admins.csv',
        """\
        nome,sobrenome,email,senha,role,avatar
        Valido,Usuario,valido@test.com,Senha!,admin,
        ,SemNome,,SenhaSemEmail,admin,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    # O usuário válido deve ter sido criado mesmo com linha inválida
    result = await session.scalars(
        select(User).where(User.email == 'valido@test.com')
    )
    assert result.first() is not None


async def test_seed_real_users_default_role_used(session, tmp_path):
    """Coluna role vazia → usa o role padrão definido no CSV_CONFIG."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    # porteiros.csv tem default_role=PORTER
    _write_csv(
        usuarios_dir,
        'porteiros.csv',
        """\
        nome,sobrenome,email,senha,role,avatar
        Marcos,Guard,marcos@test.com,Senha!,,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(
        select(User).where(User.email == 'marcos@test.com')
    )
    user = result.first()
    assert user is not None
    assert user.role == UserRole.PORTER


async def test_seed_real_users_professores_dt_is_tutor(session, tmp_path):
    """professores_dt.csv → is_tutor=True para todos."""
    usuarios_dir = tmp_path / 'usuarios'
    usuarios_dir.mkdir()
    _write_csv(
        usuarios_dir,
        'professores_dt.csv',
        """\
        nome,sobrenome,email,senha,role,sala,avatar
        Fernanda,DT,fernanda@test.com,Senha!,teacher,1,
    """,
    )

    with patch('app.shared.db.seed.USUARIOS_DIR', usuarios_dir):
        await seed_real_users(session)

    result = await session.scalars(
        select(User).where(User.email == 'fernanda@test.com')
    )
    user = result.first()
    assert user is not None
    assert user.is_tutor is True
