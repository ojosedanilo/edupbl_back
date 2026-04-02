"""
Importação de horários via CSVs.

Formato esperado — um CSV por turma:
  horario_sala_1.csv, horario_sala_2.csv, ..., horario_sala_12.csv

Cada linha representa um slot no horário semanal:

  email_professor,dia_semana,numero_periodo,tipo,titulo

Colunas
-------
email_professor
    E-mail do professor responsável pelo slot.
    Deixe VAZIO para horários sem professor (folga ou planejamento).

dia_semana
    Número do dia: 2=segunda, 3=terça, 4=quarta, 5=quinta, 6=sexta.
    (1=domingo e 7=sábado existem no enum mas não são usados normalmente.)

numero_periodo
    Número da aula (1–9 conforme periods.py).
    Deixe VAZIO para intervalos (snack_break / lunch_break).

tipo
    - class_period  → aula normal  (professor obrigatório)
    - planning      → horário de planejamento (sem aula, sem professor na sala)
    - free          → turno de folga do professor
    - snack_break   → intervalo de lanche  (sem professor)
    - lunch_break   → intervalo de almoço  (sem professor)

titulo
    Rótulo exibido no horário (ex: "Matemática", "Planejamento", "Folga").
    Opcional — se omitido, usa o valor padrão do tipo.

Exemplos de linhas válidas
--------------------------
# Aula normal com professor:
maria.silva@escola.com,2,1,class_period,Matemática

# Horário de planejamento (professor não está na sala):
joao.santos@escola.com,4,3,planning,Planejamento

# Folga do professor (turno livre):
,5,,free,Folga

# Intervalo de lanche (automático, sem professor):
,2,,snack_break,Intervalo

Idempotência
------------
A importação é idempotente: slots já existentes são ignorados (sem erro).
Execute quantas vezes quiser — nada será duplicado.

Erros
-----
Linhas com email inválido, sala inexistente ou tipo desconhecido são puladas
com aviso — as demais linhas do arquivo continuam sendo processadas.
"""

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedules.models import ScheduleSlot
from app.domains.schedules.schemas import Weekday
from app.domains.users.models import Classroom, User

DATA_DIR = Path(__file__).parent.parent.parent.parent / 'data'
HORARIOS_DIR = DATA_DIR / 'horarios'

# Tipos válidos de slot
VALID_TYPES = {'class_period', 'planning', 'free', 'snack_break', 'lunch_break'}

# Títulos padrão por tipo (usado quando a coluna "titulo" está vazia)
DEFAULT_TITLES = {
    'class_period': 'Aula',
    'planning': 'Planejamento',
    'free': 'Folga',
    'snack_break': 'Intervalo',
    'lunch_break': 'Almoço',
}

# Tipos que representam slots de horário da turma (não são ausência do professor)
CLASSROOM_TYPES = {'class_period', 'snack_break', 'lunch_break'}


async def seed_schedules(session: AsyncSession) -> None:  # noqa: PLR0912, PLR0914, PLR0915
    """
    Importa horários de CSVs em data/horario_sala_{N}.csv.

    - Idempotente: slots duplicados são ignorados.
    - Erros por linha são reportados sem interromper o processo.
    """
    from app.shared.db.seed import CLASSROOMS  # evita import circular

    print('\n📅 Importando horários...')

    # ------------------------------------------------------------------
    # 1. Monta mapa {numero_sala → classroom_id} a partir do banco
    # ------------------------------------------------------------------
    classroom_map: dict[int, int] = {}
    for numero, nome in CLASSROOMS.items():
        cid = await session.scalar(
            select(Classroom.id).where(Classroom.name == nome)
        )
        if cid is not None:
            classroom_map[numero] = cid

    if not classroom_map:
        print(
            '  ⚠️  Nenhuma sala encontrada no banco. '
            'Execute seed de salas antes de importar horários.'
        )
        return

    # ------------------------------------------------------------------
    # 2. Cache de professores {email → user_id}
    # ------------------------------------------------------------------
    rows = await session.execute(select(User.email, User.id))
    teacher_map: dict[str, int] = {email: uid for email, uid in rows.all()}

    # ------------------------------------------------------------------
    # 3. Processa um CSV por turma
    # ------------------------------------------------------------------
    total_criados = 0
    total_pulados = 0

    for numero_sala, classroom_id in sorted(classroom_map.items()):
        filepath = HORARIOS_DIR / f'horario_sala_{numero_sala}.csv'

        if not filepath.exists():
            continue

        print(f'\n  📄 Processando: horario_sala_{numero_sala}.csv')

        criados = 0
        pulados = 0
        erros = 0

        with open(filepath, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            linhas = list(reader)

        for linha_num, row in enumerate(linhas, start=2):
            try:
                # --- Campos obrigatórios ---
                tipo = row.get('tipo', '').strip()
                if tipo not in VALID_TYPES:
                    print(
                        f'    ⚠️  Linha {linha_num}: tipo inválido "{tipo}" — pulando.'
                    )
                    erros += 1
                    continue

                dia_raw = row.get('dia_semana', '').strip()
                if not dia_raw:
                    print(
                        f'    ⚠️  Linha {linha_num}: dia_semana vazio — pulando.'
                    )
                    erros += 1
                    continue

                try:
                    weekday = Weekday(int(dia_raw))
                except (ValueError, KeyError):
                    print(
                        f'    ⚠️  Linha {linha_num}: dia_semana inválido "{dia_raw}" — pulando.'
                    )
                    erros += 1
                    continue

                # --- Número do período (opcional para breaks/folga) ---
                periodo_raw = row.get('numero_periodo', '').strip()
                period_number: int | None = None
                if periodo_raw:
                    try:
                        period_number = int(periodo_raw)
                    except ValueError:
                        print(
                            f'    ⚠️  Linha {linha_num}: numero_periodo inválido "{periodo_raw}" — pulando.'
                        )
                        erros += 1
                        continue

                # --- Professor (obrigatório apenas para class_period) ---
                email_raw = row.get('email_professor', '').strip().lower()
                teacher_id: int | None = None

                if email_raw:
                    teacher_id = teacher_map.get(email_raw)
                    if teacher_id is None:
                        print(
                            f'    ⚠️  Linha {linha_num}: professor "{email_raw}" não encontrado — pulando.'
                        )
                        erros += 1
                        continue
                elif tipo == 'class_period':
                    print(
                        f'    ⚠️  Linha {linha_num}: class_period sem email_professor — pulando.'
                    )
                    erros += 1
                    continue

                # --- Para slots do tipo planning/free, classroom_id é NULL
                #     pois representam ausência do professor da turma, não
                #     um slot da grade da turma em si. Mas a constraint
                #     exige classroom_id. Usamos o classroom_id da turma
                #     mesmo, pois o "tipo" já diferencia o significado.
                # ---

                titulo_raw = row.get('titulo', '').strip()
                titulo = titulo_raw if titulo_raw else DEFAULT_TITLES[tipo]

                # --- Idempotência: verifica se já existe ---
                existing = await session.scalar(
                    select(ScheduleSlot).where(
                        ScheduleSlot.classroom_id == classroom_id,
                        ScheduleSlot.weekday == weekday,
                        ScheduleSlot.period_number == period_number,
                        ScheduleSlot.type == tipo,
                    )
                )

                if existing:
                    pulados += 1
                    continue

                slot = ScheduleSlot(
                    type=tipo,
                    title=titulo,
                    classroom_id=classroom_id,
                    teacher_id=teacher_id,
                    weekday=weekday,
                    period_number=period_number,
                )
                session.add(slot)

                # Flush por linha para detectar violações de constraint cedo
                try:
                    await session.flush()
                    criados += 1
                except IntegrityError:
                    await session.rollback()
                    pulados += 1
                    continue

            except Exception as exc:
                print(f'    ⚠️  Linha {linha_num}: erro inesperado — {exc}')
                erros += 1

        await session.commit()

        print(f'    ✅ {criados} slot(s) criado(s), {pulados} já existiam', end='')
        if erros:
            print(f', ⚠️  {erros} erro(s)', end='')
        print()

        total_criados += criados
        total_pulados += pulados

    if total_criados == 0 and total_pulados == 0:
        print(
            '\n  ℹ️  Nenhum CSV de horário encontrado em data/horarios/.'
            ' Crie horario_sala_1.csv, horario_sala_2.csv, etc.'
        )
    else:
        print(f'\n  ✅ {total_criados} slot(s) de horário importado(s)!')
