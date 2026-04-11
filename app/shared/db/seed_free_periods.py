"""
Importação de folgas e geração automática de horários de planejamento.

Fluxo
-----
1. Lê ``data/horarios/folgas_professores.csv`` e cria slots ``FREE`` para
   os períodos de folga de cada professor.
2. Para cada professor que já possui aulas (``class_period``) no banco,
   percorre todos os slots letivos da semana (segunda a sexta, períodos 1–9)
   e cria um slot ``PLANNING`` nos períodos que **não** são aula nem folga.

O passo 2 roda automaticamente após o passo 1, mas também pode ser chamado
de forma independente com ``seed_planning_slots``.

Formato do CSV
--------------
Arquivo: ``data/horarios/folgas_professores.csv``

    email,dia_semana,numero_slot

Colunas
~~~~~~~
email
    E-mail institucional do professor (deve já existir no banco).

dia_semana
    Número do dia: 2=segunda, 3=terça, 4=quarta, 5=quinta, 6=sexta.

numero_slot
    Número do período de aula (1–9), conforme ``periods.py``.

Exemplo de arquivo válido
~~~~~~~~~~~~~~~~~~~~~~~~~
::

    email,dia_semana,numero_slot
    maria.silva@escola.com,2,5
    maria.silva@escola.com,4,5
    maria.silva@escola.com,6,5
    joao.santos@escola.com,3,4
    joao.santos@escola.com,3,5
    joao.santos@escola.com,5,4
    joao.santos@escola.com,5,5

Idempotência
------------
Todos os seeds são idempotentes: slots já existentes são ignorados.
Execute quantas vezes quiser sem efeitos colaterais.

Horários de planejamento
------------------------
São gerados automaticamente para **todos os professores** que possuem pelo
menos uma aula no banco. Um slot de planejamento é criado para cada
combinação (professor × dia × período) que **não** esteja marcada como
``class_period`` nem como ``free``.

Como os slots de planejamento não pertencem a uma turma específica, eles
são armazenados com ``classroom_id = NULL``.  O frontend/API usa esses
registros para saber quando um professor está indisponível por motivo de
planejamento.
"""

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedules.enums import PeriodTypeEnum, WeekdayEnum
from app.domains.schedules.models import ScheduleSlot
from app.domains.users.models import User, UserRole

DATA_DIR = Path(__file__).parent.parent.parent.parent / 'data'
HORARIOS_DIR = DATA_DIR / 'horarios'
FREE_PERIODS_CSV = HORARIOS_DIR / 'folgas_professores.csv'

# Dias letivos padrão
WEEKDAYS = [
    WeekdayEnum.MONDAY,
    WeekdayEnum.TUESDAY,
    WeekdayEnum.WEDNESDAY,
    WeekdayEnum.THURSDAY,
    WeekdayEnum.FRIDAY,
]

# Períodos letivos válidos (1–9 conforme periods.py)
PERIOD_NUMBERS = list(range(1, 10))


async def seed_free_periods(session: AsyncSession) -> None:
    """
    Importa os slots de folga de ``folgas_professores.csv`` e,
    em seguida, gera automaticamente os slots de planejamento para
    todos os professores com aulas cadastradas.
    """
    print('\n🏖️  Importando folgas de professores...')

    if not FREE_PERIODS_CSV.exists():
        print(
            f'  ℹ️  {FREE_PERIODS_CSV.name} não encontrado — '
            'nenhuma folga importada.'
        )
    else:
        await _import_free_slots(session)

    print('\n📝 Gerando horários de planejamento automáticos...')
    await seed_planning_slots(session)


async def _import_free_slots(session: AsyncSession) -> None:
    """Lê o CSV e cria slots FREE para cada professor."""
    # Cache de professores (email → id)
    rows = await session.execute(
        select(User.email, User.id).where(User.role.in_([
            UserRole.TEACHER,
        ]))
    )
    teacher_map: dict[str, int] = {
        email.lower(): uid for email, uid in rows.all()
    }

    with open(FREE_PERIODS_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        linhas = list(reader)

    # Verifica cabeçalho mínimo
    fieldnames = {(reader.fieldnames or [])[i].strip().lower()
                  for i in range(len(reader.fieldnames or []))}
    required = {'email', 'dia_semana', 'numero_slot'}
    missing = required - fieldnames
    if missing:
        print(
            f'  ❌ Colunas obrigatórias ausentes em '
            f'{FREE_PERIODS_CSV.name}: {", ".join(sorted(missing))}'
        )
        return

    criados = pulados = erros = 0

    for linha_num, row in enumerate(linhas, start=2):
        try:
            email = row.get('email', '').strip().lower()
            dia_raw = row.get('dia_semana', '').strip()
            slot_raw = row.get('numero_slot', '').strip()

            if not email or not dia_raw or not slot_raw:
                print(f'  ⚠️  Linha {linha_num}: campos obrigatórios vazios — ignorada.')
                erros += 1
                continue

            teacher_id = teacher_map.get(email)
            if teacher_id is None:
                print(
                    f'  ⚠️  Linha {linha_num}: professor "{email}" não '
                    'encontrado no banco — ignorado.'
                )
                erros += 1
                continue

            try:
                weekday = WeekdayEnum(int(dia_raw))
            except (ValueError, KeyError):
                print(f'  ⚠️  Linha {linha_num}: dia_semana inválido "{dia_raw}"')
                erros += 1
                continue

            try:
                period_number = int(slot_raw)
                if period_number not in PERIOD_NUMBERS:
                    raise ValueError
            except ValueError:
                print(
                    f'  ⚠️  Linha {linha_num}: numero_slot inválido '
                    f'"{slot_raw}" (esperado 1–9)'
                )
                erros += 1
                continue

            # Verifica se já existe esse slot de folga para o professor
            existing = await session.scalar(
                select(ScheduleSlot).where(
                    ScheduleSlot.teacher_id == teacher_id,
                    ScheduleSlot.weekday == weekday,
                    ScheduleSlot.period_number == period_number,
                    ScheduleSlot.type == PeriodTypeEnum.FREE,
                )
            )
            if existing:
                pulados += 1
                continue

            slot = ScheduleSlot(
                type=PeriodTypeEnum.FREE,
                title='Folga',
                classroom_id=None,  # type: ignore[arg-type]
                teacher_id=teacher_id,
                weekday=weekday,
                period_number=period_number,
            )
            session.add(slot)

            try:
                await session.flush()
                criados += 1
            except IntegrityError:
                await session.rollback()
                pulados += 1

        except Exception as exc:
            print(f'  ⚠️  Linha {linha_num}: erro inesperado — {exc}')
            erros += 1

    await session.commit()

    print(f'  ✅ {criados} folga(s) criada(s)', end='')
    if pulados:
        print(f', {pulados} ignorada(s)', end='')
    if erros:
        print(f', ⚠️  {erros} erro(s)', end='')
    print()


async def seed_planning_slots(session: AsyncSession) -> None:
    """
    Para cada professor com pelo menos uma aula cadastrada, cria slots
    ``PLANNING`` nos períodos letivos que **não** estejam ocupados por
    ``class_period`` ou ``free``.

    Slots de planejamento têm ``classroom_id = NULL`` — não pertencem a
    nenhuma turma, representam apenas a indisponibilidade do professor.
    """
    # Busca todos os professores que têm pelo menos uma aula
    teacher_rows = await session.execute(
        select(ScheduleSlot.teacher_id)
        .where(
            ScheduleSlot.type == PeriodTypeEnum.CLASS_PERIOD,
            ScheduleSlot.teacher_id.isnot(None),
        )
        .distinct()
    )
    teacher_ids = [row[0] for row in teacher_rows.all()]

    if not teacher_ids:
        print('  ℹ️  Nenhum professor com aulas cadastradas — nada a fazer.')
        return

    criados = pulados = 0

    for teacher_id in teacher_ids:
        # Carrega todos os slots já existentes para esse professor
        existing_rows = await session.execute(
            select(
                ScheduleSlot.weekday,
                ScheduleSlot.period_number,
                ScheduleSlot.type,
            ).where(
                ScheduleSlot.teacher_id == teacher_id,
                ScheduleSlot.period_number.isnot(None),
            )
        )
        # Conjunto de (weekday, period_number) já ocupados
        occupied: set[tuple] = {
            (w, p) for w, p, _ in existing_rows.all()
        }

        for weekday in WEEKDAYS:
            for period_number in PERIOD_NUMBERS:
                key = (weekday, period_number)
                if key in occupied:
                    pulados += 1
                    continue

                # Verifica se já existe planejamento (idempotência via banco)
                existing = await session.scalar(
                    select(ScheduleSlot).where(
                        ScheduleSlot.teacher_id == teacher_id,
                        ScheduleSlot.weekday == weekday,
                        ScheduleSlot.period_number == period_number,
                        ScheduleSlot.type == PeriodTypeEnum.PLANNING,
                    )
                )
                if existing:
                    pulados += 1
                    continue

                slot = ScheduleSlot(
                    type=PeriodTypeEnum.PLANNING,
                    title='Planejamento',
                    classroom_id=None,  # type: ignore[arg-type]
                    teacher_id=teacher_id,
                    weekday=weekday,
                    period_number=period_number,
                )
                session.add(slot)

                try:
                    await session.flush()
                    criados += 1
                    occupied.add(key)
                except IntegrityError:
                    await session.rollback()
                    pulados += 1

    await session.commit()

    print(f'  ✅ {criados} slot(s) de planejamento criado(s)', end='')
    if pulados:
        print(f', {pulados} ignorado(s)', end='')
    print()
