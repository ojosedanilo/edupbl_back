# 📅 Feature: Schedules (Horários) — Guia de Implementação

> Grade de aulas semanal por turma e professor, com suporte a exceções
> pontuais (eventos, simulados, feriados). Base necessária para o fluxo
> de atrasos identificar qual professor está em aula no momento.

---

## 🎯 Objetivo

1. Armazenar a grade fixa semanal de cada turma (professor + disciplina + período)
2. Registrar exceções pontuais que alteram o dia (eventos, simulados)
3. Expor uma função `get_current_teacher(classroom_id, at)` para o fluxo de atrasos
4. Servir os dados para a tela de horários no frontend

---

## 📐 Design do modelo de dados

### Por que duas tabelas?

A grade semanal e os eventos especiais têm naturezas diferentes. A grade é
recorrente e permanente; os eventos são pontuais. Juntar os dois em uma tabela
complica consultas do tipo "qual é a grade normal desta turma?" e "quais eventos
acontecem este mês?". Separando, cada consulta é trivial.

### `schedule_slots` — a grade fixa semanal

| Campo          | Tipo                    | Observação                                        |
|----------------|-------------------------|---------------------------------------------------|
| `id`           | PK                      |                                                   |
| `classroom_id` | FK → classrooms         | CASCADE DELETE                                    |
| `teacher_id`   | FK → users (TEACHER)    | SET NULL se professor for deletado                |
| `weekday`      | Integer (0=seg … 4=sex) | Dia da semana                                     |
| `period`       | Integer (1–9)           | Número do período (ver tabela de períodos abaixo) |
| `subject`      | String(100)             | Disciplina (ex: "Matemática")                     |

Índice único em `(classroom_id, weekday, period)` — uma turma não pode ter dois
professores no mesmo período do mesmo dia.

### `schedule_overrides` — exceções pontuais

| Campo           | Tipo         | Observação                                        |
|-----------------|--------------|---------------------------------------------------|
| `id`            | PK           |                                                   |
| `override_date` | Date         | Data específica do evento                         |
| `description`   | String(200)  | Ex: "Simulado ENEM", "Festa Junina"               |
| `starts_at`     | Time         | Início do horário modificado (ex: 08:00)          |
| `ends_at`       | Time         | Fim do horário modificado (ex: 12:00)             |
| `affects_all`   | Boolean      | True = toda a escola; False = só turmas definidas |
| `created_at`    | Datetime     | Auto                                              |

Tabela de associação `override_classrooms(override_id, classroom_id)` para quando
`affects_all=False`.

---

## ⏰ Tabela de períodos

Hardcoded como constante Python em `app/domains/schedules/periods.py`.
Não precisa de tabela no banco — raramente muda, e quando mudar basta
alterar o arquivo.

```python
# app/domains/schedules/periods.py

from datetime import time, timedelta, datetime
from typing import NamedTuple

class Period(NamedTuple):
    number: int
    start: time
    end: time

# Configuração da escola
SCHOOL_START = time(7, 30)
PERIOD_DURATION_MINUTES = 50

BREAKS: list[tuple[time, time]] = [
    (time(9, 10),  time(9, 30)),   # Intervalo da manhã
    (time(12, 0),  time(13, 20)),  # Almoço
    (time(15, 0),  time(15, 20)),  # Intervalo da tarde
]

def _build_periods() -> dict[int, Period]:
    """Calcula automaticamente o horário de cada período respeitando os intervalos."""
    periods = {}
    current = datetime.combine(datetime.today(), SCHOOL_START)
    end_of_day = datetime.combine(datetime.today(), time(17, 0))
    period_number = 1

    while current < end_of_day:
        start = current.time()
        end = (current + timedelta(minutes=PERIOD_DURATION_MINUTES)).time()

        # Avança sobre qualquer intervalo que caia dentro deste período
        for break_start, break_end in BREAKS:
            if start < break_start <= end:
                current = datetime.combine(datetime.today(), break_end)
                end = (current + timedelta(minutes=PERIOD_DURATION_MINUTES)).time()
                break

        periods[period_number] = Period(period_number, start, end)
        period_number += 1
        current = datetime.combine(datetime.today(), end)

        # Pula intervalos que caem entre períodos
        for break_start, break_end in BREAKS:
            if current.time() == break_start:
                current = datetime.combine(datetime.today(), break_end)

    return periods

PERIODS: dict[int, Period] = _build_periods()
```

O resultado de `_build_periods()`:

| Período | Início | Fim   |
|---------|--------|-------|
| 1       | 07:30  | 08:20 |
| 2       | 08:20  | 09:10 |
| 3       | 09:30  | 10:20 |
| 4       | 10:20  | 11:10 |
| 5       | 11:10  | 12:00 |
| 6       | 13:20  | 14:10 |
| 7       | 14:10  | 15:00 |
| 8       | 15:20  | 16:10 |
| 9       | 16:10  | 17:00 |

---

## 🔧 Helper para o fluxo de atrasos

```python
# app/domains/schedules/helpers.py

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domains.schedules.models import ScheduleSlot, ScheduleOverride
from app.domains.schedules.periods import PERIODS
from app.domains.users.models import User

async def get_current_teacher(
    classroom_id: int,
    at: datetime,
    db: AsyncSession,
) -> User | None:
    """
    Retorna o professor que está dando aula na turma `classroom_id`
    no momento `at`.

    Retorna None se:
    - Há um override ativo que afeta essa turma (aula suspensa)
    - Nenhum slot corresponde ao weekday + period atual
    - O slot existe mas o professor foi deletado (teacher_id é NULL)
    """
    current_date = at.date()
    current_time = at.time()
    weekday = at.weekday()  # 0 = segunda, 4 = sexta

    # 1. Verifica se há um override ativo para esta data e turma
    override = await db.scalar(
        select(ScheduleOverride)
        .where(ScheduleOverride.override_date == current_date)
        .where(ScheduleOverride.starts_at <= current_time)
        .where(ScheduleOverride.ends_at > current_time)
        # affects_all=True OU a turma está listada no override
        # (a lógica completa depende do join com override_classrooms)
    )
    if override:
        return None  # Aula suspensa por evento especial

    # 2. Descobre o período atual
    current_period = None
    for period in PERIODS.values():
        if period.start <= current_time < period.end:
            current_period = period.number
            break

    if current_period is None:
        return None  # Fora do horário de aula (intervalo ou após 17h)

    # 3. Busca o slot correspondente
    slot = await db.scalar(
        select(ScheduleSlot)
        .where(ScheduleSlot.classroom_id == classroom_id)
        .where(ScheduleSlot.weekday == weekday)
        .where(ScheduleSlot.period == current_period)
    )

    if not slot or not slot.teacher_id:
        return None

    return await db.get(User, slot.teacher_id)
```

---

## 🔐 Permissões novas

Adicionar em `app/shared/rbac/permissions.py`:

```python
# ── Horários ───────────────────────────────────────────────────── #
SCHEDULES_VIEW   = 'schedules:view'    # Todos os usuários logados
SCHEDULES_MANAGE = 'schedules:manage'  # Coordenação e Admin
```

Adicionar no `ROLE_PERMISSIONS`:

```python
UserRole.STUDENT:     { ..., SystemPermissions.SCHEDULES_VIEW },
UserRole.GUARDIAN:    { ..., SystemPermissions.SCHEDULES_VIEW },
UserRole.TEACHER:     { ..., SystemPermissions.SCHEDULES_VIEW },
UserRole.PORTER:      { ..., SystemPermissions.SCHEDULES_VIEW },
UserRole.COORDINATOR: { ... },  # já tem tudo (exceto USER_CHANGE_ROLE)
UserRole.ADMIN:       { ... },  # já tem tudo
```

---

## 📋 Estrutura de arquivos

```
app/domains/schedules/
├── __init__.py
├── models.py      ← ScheduleSlot, ScheduleOverride, override_classrooms
├── periods.py     ← PERIODS, BREAKS, SCHOOL_START, _build_periods()
├── helpers.py     ← get_current_teacher()
├── schemas.py     ← SlotCreate, SlotPublic, OverrideCreate, OverridePublic
└── routers.py     ← endpoints CRUD

tests/
└── test_schedules.py
```

---

## 📋 Endpoints

Prefixo: `/schedules`

| Método | Rota                                   | Permissão         | Comportamento                        |
|--------|----------------------------------------|-------------------|--------------------------------------|
| GET    | `/schedules/periods`                   | qualquer logado   | Retorna a tabela de períodos         |
| GET    | `/schedules/classroom/{id}`            | SCHEDULES_VIEW    | Grade completa de uma turma          |
| GET    | `/schedules/teacher/{id}`              | SCHEDULES_VIEW    | Grade completa de um professor       |
| GET    | `/schedules/current-teacher/{class_id}`| SCHEDULES_VIEW    | Professor em aula agora              |
| POST   | `/schedules/slots`                     | SCHEDULES_MANAGE  | Criar slot                           |
| PUT    | `/schedules/slots/{id}`                | SCHEDULES_MANAGE  | Editar slot                          |
| DELETE | `/schedules/slots/{id}`                | SCHEDULES_MANAGE  | Remover slot                         |
| GET    | `/schedules/overrides`                 | SCHEDULES_VIEW    | Listar eventos especiais             |
| POST   | `/schedules/overrides`                 | SCHEDULES_MANAGE  | Criar evento especial                |
| DELETE | `/schedules/overrides/{id}`            | SCHEDULES_MANAGE  | Remover evento especial              |

### `GET /schedules/periods` — usado pelo frontend para montar a tabela visual

Retorna:
```json
[
  { "number": 1, "start": "07:30", "end": "08:20" },
  { "number": 2, "start": "08:20", "end": "09:10" },
  ...
]
```

### `GET /schedules/current-teacher/{classroom_id}` — usado pelo fluxo de atrasos

Retorna o professor atual ou `{ "teacher": null }` se não houver aula.

---

## 🛠️ Passo a Passo de Implementação

### Passo 1 — Criar `periods.py`

Implemente `_build_periods()` e valide que os 9 períodos batem com a tabela acima.
Escreva um teste unitário simples (sem banco):

```python
def test_period_1_starts_at_730():
    assert PERIODS[1].start == time(7, 30)

def test_period_3_starts_after_break():
    assert PERIODS[3].start == time(9, 30)

def test_no_period_during_lunch():
    lunch = time(12, 30)
    current = next((p for p in PERIODS.values() if p.start <= lunch < p.end), None)
    assert current is None
```

### Passo 2 — Criar `models.py`

Inclua o índice único em `ScheduleSlot`:

```python
__table_args__ = (
    UniqueConstraint('classroom_id', 'weekday', 'period',
                     name='uq_slot_classroom_weekday_period'),
)
```

### Passo 3 — Criar `schemas.py`

```python
class SlotCreate(BaseModel):
    classroom_id: int
    teacher_id: int | None
    weekday: int          # 0–4
    period: int           # 1–9
    subject: str

class SlotPublic(SlotCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SlotList(BaseModel):
    slots: list[SlotPublic]

class OverrideCreate(BaseModel):
    override_date: date
    description: str
    starts_at: time
    ends_at: time
    affects_all: bool = True
    classroom_ids: list[int] = []  # usado quando affects_all=False

class OverridePublic(BaseModel):
    id: int
    override_date: date
    description: str
    starts_at: time
    ends_at: time
    affects_all: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### Passo 4 — Criar `helpers.py`

Implemente `get_current_teacher()` conforme o código acima.

### Passo 5 — Criar `routers.py`

Siga o padrão de `occurrences/routers.py` (helper `_get_slot_or_404`, etc.).

### Passo 6 — Registrar no `app/main.py`

```python
from app.domains.schedules import routers as schedules_routers
app.include_router(schedules_routers.router)
```

### Passo 7 — Atualizar `migrations/env.py`

```python
from app.domains.schedules.models import ScheduleSlot, ScheduleOverride  # noqa: F401
```

### Passo 8 — Gerar e aplicar migration

```bash
alembic revision --autogenerate -m "adicionar tabela schedules"
alembic upgrade head
```

### Passo 9 — Testes

```python
# tests/test_schedules.py

# Testes de períodos (sem banco)
def test_period_count():
    assert len(PERIODS) == 9

# Testes de CRUD
async def test_create_slot(client, coordinator_token):
    ...

async def test_unique_slot_constraint(client, coordinator_token):
    # Tenta criar dois slots na mesma turma, dia e período
    ...

# Testes de get_current_teacher
async def test_returns_teacher_during_class(db):
    ...

async def test_returns_none_during_break(db):
    ...

async def test_returns_none_during_override(db):
    ...
```

---

## ✅ Checklist de Implementação

- [ ] Criar `app/domains/schedules/__init__.py`
- [ ] Criar `app/domains/schedules/periods.py` + testes unitários dos períodos
- [ ] Criar `app/domains/schedules/models.py` (ScheduleSlot, ScheduleOverride, override_classrooms)
- [ ] Criar `app/domains/schedules/schemas.py`
- [ ] Criar `app/domains/schedules/helpers.py` (get_current_teacher)
- [ ] Criar `app/domains/schedules/routers.py`
- [ ] Adicionar `SCHEDULES_VIEW` e `SCHEDULES_MANAGE` em `permissions.py`
- [ ] Atualizar `ROLE_PERMISSIONS` para incluir `SCHEDULES_VIEW` em todas as roles
- [ ] Registrar router em `app/main.py`
- [ ] Importar models em `migrations/env.py`
- [ ] Gerar e aplicar migration
- [ ] Criar `tests/test_schedules.py`
