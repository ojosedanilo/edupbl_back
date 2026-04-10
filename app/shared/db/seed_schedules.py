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

from app.domains.schedules.enums import PeriodTypeEnum, WeekdayEnum
from app.domains.schedules.models import ScheduleSlot
from app.domains.users.models import Classroom, User

DATA_DIR = Path(__file__).parent.parent.parent.parent / 'data'
HORARIOS_DIR = DATA_DIR / 'horarios'

# Tipos válidos de slot
VALID_TYPES = set(PeriodTypeEnum)

# Títulos padrão por tipo (usado quando a coluna "titulo" está vazia)
DEFAULT_TITLES = {
    PeriodTypeEnum.CLASS_PERIOD: 'Aula',
    PeriodTypeEnum.PLANNING: 'Planejamento',
    PeriodTypeEnum.FREE: 'Folga',
    PeriodTypeEnum.SNACK_BREAK: 'Intervalo',
    PeriodTypeEnum.LUNCH_BREAK: 'Almoço',
}

# Tipos que representam slots de horário da turma (não são ausência do professor)
CLASSROOM_TYPES = {
    PeriodTypeEnum.CLASS_PERIOD,
    PeriodTypeEnum.SNACK_BREAK,
    PeriodTypeEnum.LUNCH_BREAK,
}


async def seed_schedules(session: AsyncSession) -> None:  # noqa: PLR0915
    """
    Importa horários de CSVs em data/horarios/horario_sala_{N}.csv.

    - Idempotente: slots duplicados são ignorados.
    - Erros por linha são reportados sem interromper o processo.
    """
    from app.shared.db.seed import CLASSROOMS  # evita import circular

    print('\n📅 Importando horários...')

    # ------------------------------------------------------------------
    # 1. Mapa {numero_sala → classroom_id}
    # ------------------------------------------------------------------
    classroom_map: dict[int, int] = {}

    for numero, nome in CLASSROOMS.items():
        cid = await session.scalar(
            select(Classroom.id).where(Classroom.name == nome)
        )
        if cid:
            classroom_map[numero] = cid

    if not classroom_map:
        print('  ⚠️ Nenhuma sala encontrada. Execute o seed de salas primeiro.')
        return

    # ------------------------------------------------------------------
    # 2. Cache de professores
    # ------------------------------------------------------------------
    rows = await session.execute(select(User.email, User.id))
    teacher_map: dict[str, int] = {
        email.lower(): uid for email, uid in rows.all()
    }

    # ------------------------------------------------------------------
    # 3. Processamento dos CSVs
    # ------------------------------------------------------------------
    total_criados = 0
    total_pulados = 0

    for numero_sala, classroom_id in sorted(classroom_map.items()):
        filepath = HORARIOS_DIR / f'horario_sala_{numero_sala}.csv'

        if not filepath.exists():
            continue

        print(f'\n  📄 horario_sala_{numero_sala}.csv')

        with open(filepath, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            linhas = list(reader)

        # 🔥 Cache de slots existentes (performance)
        existing_rows = await session.execute(
            select(
                ScheduleSlot.weekday,
                ScheduleSlot.period_number,
                ScheduleSlot.type,
            ).where(ScheduleSlot.classroom_id == classroom_id)
        )

        existing_set = {
            (w, p, t) for w, p, t in existing_rows.all()
        }

        criados = pulados = erros = 0

        for linha_num, row in enumerate(linhas, start=2):
            try:
                tipo_raw = row.get('tipo', '').strip()

                # --- Tipo ---
                try:
                    tipo = PeriodTypeEnum(tipo_raw)
                except ValueError:
                    print(f'    ⚠️ Linha {linha_num}: tipo inválido "{tipo_raw}"')
                    erros += 1
                    continue

                # --- Dia ---
                try:
                    weekday = WeekdayEnum(int(row.get('dia_semana', '').strip()))
                except Exception:
                    print(f'    ⚠️ Linha {linha_num}: dia_semana inválido')
                    erros += 1
                    continue

                # --- Período ---
                periodo_raw = row.get('numero_periodo', '').strip()
                period_number = int(periodo_raw) if periodo_raw else None

                if tipo.requires_teacher and period_number is None:
                    print(f'    ⚠️ Linha {linha_num}: class_period sem numero_periodo')
                    erros += 1
                    continue

                # --- Professor ---
                email = row.get('email_professor', '').strip().lower()
                teacher_id = None

                if email:
                    teacher_id = teacher_map.get(email)
                    if not teacher_id:
                        print(f'    ⚠️ Linha {linha_num}: professor "{email}" não encontrado')
                        erros += 1
                        continue
                elif tipo.requires_teacher:
                    print(f'    ⚠️ Linha {linha_num}: class_period sem professor')
                    erros += 1
                    continue

                # --- Título ---
                titulo = row.get('titulo', '').strip() or tipo.default_title

                key = (weekday, period_number, tipo)

                if key in existing_set:
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

                try:
                    await session.flush()
                    criados += 1
                    existing_set.add(key)
                except IntegrityError:
                    pulados += 1
                    continue

            except Exception as exc:
                print(f'    ⚠️ Linha {linha_num}: erro inesperado — {exc}')
                erros += 1

        await session.commit()

        print(f'    ✅ {criados} criados, {pulados} ignorados', end='')
        if erros:
            print(f', ⚠️ {erros} erros', end='')
        print()

        total_criados += criados
        total_pulados += pulados

    if total_criados == 0 and total_pulados == 0:
        print('\n  ℹ️ Nenhum CSV encontrado em data/horarios/')
    else:
        print(f'\n  ✅ {total_criados} slot(s) importado(s)!')
