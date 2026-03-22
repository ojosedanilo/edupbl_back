import csv
import unicodedata
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import Classroom, User, UserRole
from app.shared.security import get_password_hash

# ---------------------------------------------------------------------------
# Salas
# ---------------------------------------------------------------------------

CLASSROOMS = {
    1: '1º ano A',
    2: '1º ano B',
    3: '1º ano C',
    4: '1º ano D',
    5: '2º ano A',
    6: '2º ano B',
    7: '2º ano C',
    8: '2º ano D',
    9: '3º ano A',
    10: '3º ano B',
    11: '3º ano C',
    12: '3º ano D',
}


async def seed_classrooms(session: AsyncSession) -> dict[int, int]:
    """Cria as salas padrão se não existirem.
    Retorna um dict {numero_sala: id_no_banco}.
    """
    id_map: dict[int, int] = {}

    for numero, nome in CLASSROOMS.items():
        existing = await session.scalar(
            select(Classroom).where(Classroom.name == nome)
        )
        if existing:
            id_map[numero] = existing.id
        else:
            classroom = Classroom(name=nome)
            session.add(classroom)
            await session.flush()  # garante que o id seja gerado
            id_map[numero] = classroom.id

    await session.commit()
    print(f'OK {len(id_map)} salas verificadas/criadas.')
    return id_map


# ---------------------------------------------------------------------------
# Normalização de texto para username
# ---------------------------------------------------------------------------


def _normalizar(texto: str) -> str:
    """Remove acentos, cedilha e caracteres especiais.

    Exemplos:
        'João'     -> 'joao'
        'Ângela'   -> 'angela'
        'Gonçalves'-> 'goncalves'
        'São Paulo' -> 'saopaulo'   (espaços removidos)
    """
    # NFD separa letra + marca diacrítica (acento, til, cedilha...)
    decomposto = unicodedata.normalize('NFD', texto)
    # Categoria 'Mn' = Mark, Nonspacing (os acentos/til/cedilha separados)
    sem_acento = ''.join(
        c for c in decomposto if unicodedata.category(c) != 'Mn'
    )
    # Minúsculas; mantém só letras e dígitos
    # (ponto adicionado ao montar o username)
    return ''.join(c for c in sem_acento.lower() if c.isalnum())


def _base_username(nome: str, sobrenome: str) -> str:
    """
    Monta a base do username: primeiro_nome.ultimo_sobrenome, sem acentos.
    """
    primeiro = _normalizar(nome.split(maxsplit=1)[0])
    ultimo = _normalizar(sobrenome.rsplit(maxsplit=1)[-1])
    return f'{primeiro}.{ultimo}'


async def _gerar_username_unico(
    session: AsyncSession,
    nome: str,
    sobrenome: str,
    usados_no_lote: set[str],
) -> str:
    """
    Retorna um username único, verificando tanto o banco quanto o lote atual.

    Sequência: joao.silva -> joao.silva1 -> joao.silva2 -> ...
    """
    base = _base_username(nome, sobrenome)
    candidato = base
    contador = 1

    while True:
        # 1. Não pode conflitar com o lote que ainda não foi commitado
        if candidato not in usados_no_lote:
            # 2. Não pode conflitar com o que já está no banco
            existe_no_banco = await session.scalar(
                select(User).where(User.username == candidato)
            )
            if existe_no_banco is None:
                break  # encontrou um username livre

        candidato = f'{base}{contador}'
        contador += 1

    usados_no_lote.add(candidato)
    return candidato


# ---------------------------------------------------------------------------
# Seed de desenvolvimento (usuários de teste)
# ---------------------------------------------------------------------------


async def seed_test_users(session: AsyncSession):
    """Cria usuários de teste para cada role.
    Idempotente — pula usuários que já existem.
    must_change_password=False: facilita o desenvolvimento sem fricção.
    """
    classroom_map = await seed_classrooms(session)

    users = [
        User(
            username='admin',
            email='admin@edupbl.com',
            password=get_password_hash('admin'),
            first_name='Admin',
            last_name='Sistema',
            role=UserRole.ADMIN,
            is_tutor=False,
            is_active=True,
            must_change_password=False,
            classroom_id=None,
        ),
        User(
            username='coordenador',
            email='coordenador@edupbl.com',
            password=get_password_hash('coordenador'),
            first_name='Larissa',
            last_name='Coordenadora',
            role=UserRole.COORDINATOR,
            is_tutor=False,
            is_active=True,
            must_change_password=False,
            classroom_id=None,
        ),
        User(
            username='professor',
            email='professor@edupbl.com',
            password=get_password_hash('professor'),
            first_name='Lucas',
            last_name='Professor',
            role=UserRole.TEACHER,
            is_tutor=False,
            is_active=True,
            must_change_password=False,
            classroom_id=None,
        ),
        User(
            username='professor_dt',
            email='professor_dt@edupbl.com',
            password=get_password_hash('professor_dt'),
            first_name='Maria',
            last_name='Tutora',
            role=UserRole.TEACHER,
            is_tutor=True,
            is_active=True,
            must_change_password=False,
            classroom_id=classroom_map[1],  # 1º ano A
        ),
        User(
            username='porteiro',
            email='porteiro@edupbl.com',
            password=get_password_hash('porteiro'),
            first_name='Lucas',
            last_name='Porteiro',
            role=UserRole.PORTER,
            is_tutor=False,
            is_active=True,
            must_change_password=False,
            classroom_id=None,
        ),
        User(
            username='aluno',
            email='aluno@edupbl.com',
            password=get_password_hash('aluno'),
            first_name='Danilo',
            last_name='Aluno',
            role=UserRole.STUDENT,
            is_tutor=False,
            is_active=True,
            must_change_password=False,
            classroom_id=classroom_map[1],  # 1º ano A
        ),
        User(
            username='responsavel',
            email='responsavel@edupbl.com',
            password=get_password_hash('responsavel'),
            first_name='Joao',
            last_name='Responsavel',
            role=UserRole.GUARDIAN,
            is_tutor=False,
            is_active=True,
            must_change_password=False,
            classroom_id=None,
        ),
    ]

    criados = 0
    for user in users:
        existing = await session.scalar(
            select(User).where(User.email == user.email)
        )
        if not existing:
            session.add(user)
            criados += 1

    if criados:
        await session.commit()
        print(f'OK {criados} usuarios criados com sucesso!')
    else:
        print('INFO Todos os usuarios de teste ja existem. Nenhum criado.')


# ---------------------------------------------------------------------------
# Seed de produção (usuários reais via CSV)
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent.parent / 'data'

# (nome_arquivo, role_padrão, is_tutor, usa_campo_sala)
CSV_CONFIG = [
    ('admins.csv', UserRole.ADMIN, False, False),
    ('coordenadores.csv', UserRole.COORDINATOR, False, False),
    ('professores.csv', UserRole.TEACHER, False, False),
    ('professores_dt.csv', UserRole.TEACHER, True, True),
    ('alunos.csv', UserRole.STUDENT, False, True),
    ('porteiros.csv', UserRole.PORTER, False, False),
    ('responsaveis.csv', UserRole.GUARDIAN, False, False),
]


async def seed_real_users(session: AsyncSession):  # noqa: PLR0914
    classroom_map = await seed_classrooms(session)

    print('\n📦 Carregando dados existentes do banco...')

    # 🔥 1. Carrega tudo de uma vez
    existing_emails = set(
        (await session.execute(select(User.email))).scalars().all()
    )

    existing_usernames = set(
        (await session.execute(select(User.username))).scalars().all()
    )

    usados_no_lote: set[str] = set()
    total_criados = 0

    for filename, default_role, default_is_tutor, usa_sala in CSV_CONFIG:
        filepath = DATA_DIR / filename

        if not filepath.exists():
            print(f'AVISO {filename} nao encontrado — pulando.')
            continue

        print(f'\n📄 Processando: {filename}')

        novos_usuarios = []
        erros = 0

        with open(filepath, encoding='utf-8') as f:
            reader = list(csv.DictReader(f))  # 🔥 carrega tudo

        for linha, row in enumerate(reader, start=2):
            try:
                nome = row['nome'].strip()
                sobrenome = row['sobrenome'].strip()
                email = row['email'].strip().lower()
                senha = row['senha'].strip()

                # 🔥 idempotência sem query
                if email in existing_emails:
                    continue

                role_str = row.get('role', '').strip()
                role = UserRole(role_str) if role_str else default_role

                # Sala
                classroom_id = None
                if usa_sala:
                    sala = row.get('sala', '').strip()
                    if sala:
                        classroom_id = classroom_map.get(int(sala))

                # 🔥 username sem query
                base = _base_username(nome, sobrenome)
                username = base
                i = 1

                while (
                    username in existing_usernames
                    or username in usados_no_lote
                ):
                    username = f'{base}{i}'
                    i += 1

                usados_no_lote.add(username)
                existing_usernames.add(username)

                user = User(
                    username=username,
                    email=email,
                    password=get_password_hash(senha),
                    first_name=nome,
                    last_name=sobrenome,
                    role=role,
                    is_tutor=default_is_tutor,
                    is_active=True,
                    classroom_id=classroom_id,
                    must_change_password=True,
                )

                novos_usuarios.append(user)
                existing_emails.add(email)
                total_criados += 1

            except Exception:
                erros += 1

        # 🔥 batch insert (sem savepoint por linha)
        if novos_usuarios:
            session.add_all(novos_usuarios)
            await session.commit()

        print(f'  ✅ {len(novos_usuarios)} usuários criados')
        if erros:
            print(f'  ⚠️  {erros} erro(s)')

    print(f'\n✅ {total_criados} usuários importados!')
