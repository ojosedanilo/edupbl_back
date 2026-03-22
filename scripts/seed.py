import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User, UserRole
from app.shared.security import get_password_hash

ROLE_MAP = {
    'admin': UserRole.ADMIN,
    'coordinator': UserRole.COORDINATOR,
    'teacher': UserRole.TEACHER,
    'porter': UserRole.PORTER,
    'student': UserRole.STUDENT,
    'guardian': UserRole.GUARDIAN,
}


# =========================
# STATE (resolve PLR0914)
# =========================


@dataclass
class ImportStats:
    created: int = 0
    existing: int = 0
    errors: int = 0


# =========================
# HELPERS
# =========================


def validate_row(row: dict, line: int):
    for field in ['nome', 'sobrenome', 'email', 'senha']:
        if not row.get(field, '').strip():
            return f'Linha {line}: campo "{field}" vazio'

    if '@' not in row['email']:
        return f'Linha {line}: email inválido "{row["email"]}"'

    return None


def parse_role(role_str: str, default: UserRole, line: int) -> UserRole:
    role_str = role_str.strip().lower()

    if not role_str:
        return default

    if role_str not in ROLE_MAP:
        print(
            f'⚠️ Linha {line}: role "{role_str}" inválida.'
            ' Usando {default.value}'
        )
        return default

    return ROLE_MAP[role_str]


def generate_username(base: str, used: set[str]) -> str:
    username = base
    i = 1

    while username in used:
        username = f'{base}{i}'
        i += 1

    used.add(username)
    return username


def load_csv(path: Path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


# =========================
# CORE LOGIC (resolve PLR0915)
# =========================


async def process_csv(
    session: AsyncSession,
    path: Path,
    default_role: UserRole,
    is_tutor: bool,
    stats: ImportStats,
):
    print(f'\n📄 Processando: {path.name}')

    try:
        rows = load_csv(path)
    except Exception as e:
        print(f'❌ Erro ao ler {path.name}: {e}')
        stats.errors += 1
        return []

    if not rows:
        return []

    emails = {r['email'].strip().lower() for r in rows if r.get('email')}

    existing_emails = set(
        (
            await session.execute(
                select(User.email).where(User.email.in_(emails))
            )
        )
        .scalars()
        .all()
    )

    existing_usernames = set(
        (await session.execute(select(User.username))).scalars().all()
    )

    new_users = []

    for line, row in enumerate(rows, start=2):
        error = validate_row(row, line)
        if error:
            print(f'⚠️ {error}')
            stats.errors += 1
            continue

        email = row['email'].strip().lower()

        if email in existing_emails:
            stats.existing += 1
            continue

        role = parse_role(row.get('role', ''), default_role, line)

        username = generate_username(email.split('@')[0], existing_usernames)

        user = User(
            username=username,
            email=email,
            password=get_password_hash(row['senha'].strip()),
            first_name=row['nome'].strip(),
            last_name=row['sobrenome'].strip(),
            role=role,
            is_tutor=is_tutor if role == UserRole.TEACHER else False,
            is_active=True,
        )

        new_users.append(user)
        stats.created += 1

    return new_users


# =========================
# ENTRYPOINT
# =========================


async def seed_real_users(session: AsyncSession):
    data_dir = Path(__file__).parent.parent.parent / 'data'

    configs = [
        ('admins.csv', UserRole.ADMIN, False),
        ('coordenadores.csv', UserRole.COORDINATOR, False),
        ('professores.csv', UserRole.TEACHER, False),
        ('professores_dt.csv', UserRole.TEACHER, True),
        ('alunos.csv', UserRole.STUDENT, False),
        ('porteiros.csv', UserRole.PORTER, False),
        ('responsaveis.csv', UserRole.GUARDIAN, False),
    ]

    stats = ImportStats()
    all_users = []

    print('=' * 60)
    print('📂 Importando usuários...')
    print('=' * 60)

    for filename, role, is_tutor in configs:
        path = data_dir / filename

        if not path.exists():
            print(f'ℹ️ {filename} não encontrado (pulando)')
            continue

        users = await process_csv(session, path, role, is_tutor, stats)
        all_users.extend(users)

    if all_users:
        session.add_all(all_users)
        await session.commit()

    print('\n' + '=' * 60)
    print(f'✅ Criados: {stats.created}')
    print(f'ℹ️ Existentes: {stats.existing}')
    print(f'⚠️ Erros: {stats.errors}')
    print('=' * 60)
