import csv
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import (
    AVATAR_DIR as _SETTINGS_AVATAR_DIR,
)
from app.core.settings import (
    SEED_IMAGES_DIR as _SETTINGS_SEED_IMAGES_DIR,
)
from app.core.settings import (
    USUARIOS_DIR as _SETTINGS_USUARIOS_DIR,
)
from app.domains.users.models import (
    Classroom,
    User,
    UserRole,
    guardian_student,
)
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
            await session.refresh(classroom)  # popula classroom.id após flush
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


# ---------------------------------------------------------------------------
# Validação de campos do CSV
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Colunas obrigatórias por arquivo (as extras são opcionais)
_COLUNAS_OBRIGATORIAS: dict[str, set[str]] = {
    'admins.csv': {'nome', 'sobrenome', 'email', 'senha'},
    'coordenadores.csv': {'nome', 'sobrenome', 'email', 'senha'},
    'professores.csv': {'nome', 'sobrenome', 'email', 'senha'},
    'professores_dt.csv': {'nome', 'sobrenome', 'email', 'senha'},
    'alunos.csv': {'nome', 'sobrenome', 'email', 'senha'},
    'porteiros.csv': {'nome', 'sobrenome', 'email', 'senha'},
    'responsaveis.csv': {'nome', 'sobrenome', 'email', 'senha'},
}


def _validar_cabecalho(filename: str, fieldnames: list[str]) -> list[str]:
    """
    Verifica se todas as colunas obrigatórias estão presentes.
    Retorna lista de erros (vazia = OK).
    """
    erros = []
    obrigatorias = _COLUNAS_OBRIGATORIAS.get(filename, set())
    presentes = {f.strip().lower() for f in (fieldnames or [])}
    faltando = obrigatorias - presentes
    if faltando:
        erros.append(
            f'Colunas obrigatórias ausentes: {", ".join(sorted(faltando))}'
        )
    return erros


def _validar_linha(row: dict, linha: int, usa_sala: bool) -> list[str]:
    """
    Valida os campos de uma linha do CSV.
    Retorna lista de erros (vazia = OK).
    """
    erros = []

    nome = row.get('nome', '').strip()
    sobrenome = row.get('sobrenome', '').strip()
    email = row.get('email', '').strip()
    senha = row.get('senha', '').strip()

    if not nome:
        erros.append(f'Linha {linha}: campo "nome" está vazio')
    if not sobrenome:
        erros.append(f'Linha {linha}: campo "sobrenome" está vazio')
    if not email:
        erros.append(f'Linha {linha}: campo "email" está vazio')
    elif not _EMAIL_RE.match(email):
        erros.append(f'Linha {linha}: e-mail inválido → "{email}"')
    if not senha:
        erros.append(f'Linha {linha}: campo "senha" está vazio')
    elif len(senha) < 6:
        erros.append(f'Linha {linha}: senha muito curta (mínimo 6 caracteres)')

    role_str = row.get('role', '').strip()
    if role_str:
        try:
            UserRole(role_str)
        except ValueError:
            valores = [r.value for r in UserRole]
            erros.append(
                f'Linha {linha}: role inválida "{role_str}" '
                f'(válidas: {", ".join(valores)})'
            )

    if usa_sala:
        sala = row.get('sala', '').strip()
        if sala:
            try:
                num = int(sala)
                if num not in range(1, 13):
                    erros.append(
                        f'Linha {linha}: sala "{sala}" fora do intervalo '
                        f'válido (1–12)'
                    )
            except ValueError:
                erros.append(
                    f'Linha {linha}: sala "{sala}" não é um número inteiro'
                )

    return erros


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
# Importação de avatar a partir do CSV
# ---------------------------------------------------------------------------

# Paths centralizados em settings.py — não recalcular via __file__ aqui.
USUARIOS_DIR = _SETTINGS_USUARIOS_DIR
SEED_IMAGES_DIR = _SETTINGS_SEED_IMAGES_DIR
AVATAR_DIR = _SETTINGS_AVATAR_DIR


def _import_avatar(user_id: int, avatar_filename: str) -> str | None:
    """
    Copia e redimensiona o avatar indicado no CSV para data/avatars/.

    avatar_filename é o nome do arquivo relativo a data/fotos/
    (ex: 'joao.jpg' ou 'turma1/pedro.png').

    Se o arquivo não existir, loga um aviso e retorna None sem abortar
    a importação do usuário.

    Retorna o caminho relativo salvo no banco (ex: 'avatars/42.webp').
    """
    from PIL import (
        Image,
    )  # import local — Pillow pode não estar em todos os envs

    _AVATAR_DIR = AVATAR_DIR  # módulo-level — patchável nos testes
    _AVATAR_SIZE = 256

    src = SEED_IMAGES_DIR / avatar_filename.strip()
    if not src.exists():
        print(
            f'  ⚠️  Avatar não encontrado: {src} — campo avatar_url ignorado.'
        )
        return None

    try:
        _AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        img = Image.open(src)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        side = min(w, h)
        img = img.crop((
            (w - side) // 2,
            (h - side) // 2,
            (w + side) // 2,
            (h + side) // 2,
        ))
        img = img.resize((_AVATAR_SIZE, _AVATAR_SIZE), Image.LANCZOS)
        dest = _AVATAR_DIR / f'{user_id}.webp'
        img.save(dest, format='WEBP', quality=85)
        return f'avatars/{user_id}.webp'
    except Exception as e:
        print(f'  ⚠️  Erro ao processar avatar {src}: {e} — ignorado.')
        return None


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

    existing_emails = set(
        (await session.execute(select(User.email))).scalars().all()
    )
    existing_usernames = set(
        (await session.execute(select(User.username))).scalars().all()
    )

    usados_no_lote: set[str] = set()
    total_criados = 0

    for filename, default_role, default_is_tutor, usa_sala in CSV_CONFIG:
        filepath = USUARIOS_DIR / filename

        if not filepath.exists():
            print(f'AVISO {filename} não encontrado — pulando.')
            continue

        print(f'\n📄 Processando: {filename}')

        with open(filepath, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        # --- Validação de cabeçalho ---
        erros_cabecalho = _validar_cabecalho(filename, list(fieldnames))
        if erros_cabecalho:
            for err in erros_cabecalho:
                print(f'  ❌ {err}')
            print(f'  ⛔ {filename} ignorado por erro de formato.')
            continue

        # --- Validação prévia de todas as linhas ---
        erros_validacao: list[str] = []
        for linha, row in enumerate(rows, start=2):
            erros_validacao.extend(_validar_linha(row, linha, usa_sala))

        if erros_validacao:
            print(f'  ⚠️  {len(erros_validacao)} erro(s) de validação:')
            for err in erros_validacao[
                :10
            ]:  # exibe no máximo 10 para não poluir
                print(f'     • {err}')
            if len(erros_validacao) > 10:
                print(f'     … e mais {len(erros_validacao) - 10} erro(s).')
            print('  ⛔ Corrija o CSV e rode o seed novamente.')
            continue

        novos_sem_avatar: list[tuple] = []
        novos_com_avatar: list[tuple] = []
        erros = 0

        for linha, row in enumerate(rows, start=2):
            try:
                nome = row['nome'].strip()
                sobrenome = row['sobrenome'].strip()
                email = row['email'].strip().lower()
                senha = row['senha'].strip()

                if email in existing_emails:
                    continue

                role_str = row.get('role', '').strip()
                role = UserRole(role_str) if role_str else default_role

                classroom_id = None
                if usa_sala:
                    sala = row.get('sala', '').strip()
                    if sala:
                        classroom_id = classroom_map.get(int(sala))

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
                    must_change_password=True,
                )
                _classroom_id = classroom_id

                avatar_filename = row.get('avatar', '').strip()
                if avatar_filename:
                    novos_com_avatar.append((
                        user,
                        _classroom_id,
                        avatar_filename,
                    ))
                else:
                    novos_sem_avatar.append((user, _classroom_id))

                existing_emails.add(email)
                total_criados += 1

            except Exception as exc:
                print(f'  ⚠️  Linha {linha}: {exc}')
                erros += 1

        # Batch insert sem avatar
        if novos_sem_avatar:
            for user, cid in novos_sem_avatar:
                session.add(user)
                await session.flush()
                if cid is not None:
                    user.classroom_id = cid
            await session.commit()

        # Insert com avatar (flush individual para obter id)
        if novos_com_avatar:
            for user, cid, avatar_filename in novos_com_avatar:
                session.add(user)
                await session.flush()
                if cid is not None:
                    user.classroom_id = cid
                avatar_url = _import_avatar(user.id, avatar_filename)
                if avatar_url:
                    user.avatar_url = avatar_url
            await session.commit()

        criados = len(novos_sem_avatar) + len(novos_com_avatar)
        print(f'  ✅ {criados} usuários criados')
        if erros:
            print(f'  ⚠️  {erros} erro(s)')

    print(f'\n✅ {total_criados} usuários importados!')

    # Processa associações responsável → aluno após todos os usuários criados
    await seed_guardian_associations(session)


# ---------------------------------------------------------------------------
# Seed de associações responsável ↔ aluno via CSV
# ---------------------------------------------------------------------------


async def seed_guardian_associations(session: AsyncSession) -> None:
    """
    Lê responsaveis.csv e cria as associações guardian_student para cada
    aluno listado na coluna `emails_alunos`.

    Formato da coluna (opcional — responsáveis sem filhos no sistema são
    criados normalmente, só sem vínculo):

        emails_alunos
        pedro.lima@escola.com
        pedro.lima@escola.com;lucia.ferreira@escola.com

    Separador aceito: ponto-e-vírgula (;) ou vírgula (,).
    E-mails inexistentes ou de não-alunos geram aviso e são ignorados.
    Associações já existentes são puladas (idempotente).
    """
    filepath = USUARIOS_DIR / 'responsaveis.csv'
    if not filepath.exists():
        return

    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    # Coluna ausente → nada a fazer (CSV antigo sem a feature)
    if 'emails_alunos' not in [c.strip().lower() for c in fieldnames]:
        return

    print('\n🔗 Processando associações responsável → aluno...')

    # Carrega todos os usuários ativos com role STUDENT indexados por e-mail
    result = await session.execute(
        select(User.id, User.email, User.role).where(User.is_active == True)  # noqa: E712
    )
    users_by_email: dict[str, tuple[int, UserRole]] = {
        row.email: (row.id, row.role) for row in result
    }

    # Carrega pares já existentes para evitar duplicatas
    existing_pairs = set(
        (
            await session.execute(
                select(
                    guardian_student.c.guardian_id,
                    guardian_student.c.student_id,
                )
            )
        ).fetchall()
    )

    vinculos_criados = 0
    erros = 0

    for linha, row in enumerate(rows, start=2):
        guardian_email = row.get('email', '').strip().lower()
        emails_alunos_raw = row.get('emails_alunos', '').strip()

        if not guardian_email or not emails_alunos_raw:
            continue

        # Localiza o responsável no banco
        guardian_info = users_by_email.get(guardian_email)
        if guardian_info is None:
            # Pode ser que o responsável não tenha sido criado nesta rodada
            # (ex: já existia antes, com e-mail diferente no banco)
            guardian_db = await session.scalar(
                select(User).where(User.email == guardian_email)
            )
            if not guardian_db:
                print(
                    f'  ⚠️  Linha {linha}: responsável "{guardian_email}" '
                    f'não encontrado — pulando vínculos.'
                )
                erros += 1
                continue
            guardian_id = guardian_db.id
        else:
            guardian_id = guardian_info[0]

        # Separa e-mails dos alunos (aceita ; ou ,)
        separador = ';' if ';' in emails_alunos_raw else ','
        emails_alunos = [
            e.strip().lower()
            for e in emails_alunos_raw.split(separador)
            if e.strip()
        ]

        for aluno_email in emails_alunos:
            if not _EMAIL_RE.match(aluno_email):
                print(
                    f'  ⚠️  Linha {linha}: e-mail de aluno inválido '
                    f'"{aluno_email}" — ignorado.'
                )
                erros += 1
                continue

            aluno_info = users_by_email.get(aluno_email)
            if aluno_info is None:
                print(
                    f'  ⚠️  Linha {linha}: aluno "{aluno_email}" não '
                    f'encontrado no banco — ignorado.'
                )
                erros += 1
                continue

            aluno_id, aluno_role = aluno_info
            if aluno_role != UserRole.STUDENT:
                print(
                    f'  ⚠️  Linha {linha}: "{aluno_email}" não é um aluno '
                    f'(role={aluno_role.value}) — ignorado.'
                )
                erros += 1
                continue

            par = (guardian_id, aluno_id)
            if par in existing_pairs:
                continue  # já associado — idempotente

            await session.execute(
                guardian_student.insert().values(
                    guardian_id=guardian_id,
                    student_id=aluno_id,
                )
            )
            existing_pairs.add(par)
            vinculos_criados += 1

    if vinculos_criados or erros:
        await session.commit()

    print(f'  ✅ {vinculos_criados} vínculo(s) criado(s)')
    if erros:
        print(f'  ⚠️  {erros} aviso(s)')
