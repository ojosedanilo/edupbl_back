# Feature: Schedules (Horários) — Guia de Implementação

> Grade de aulas semanal por turma e professor, com suporte a exceções
> pontuais (eventos, simulados, feriados). Base necessária para o fluxo
> de atrasos identificar qual professor está em aula no momento.

---

## Objetivo

1. Armazenar a grade fixa semanal de cada turma (professor + disciplina + período)
2. Registrar exceções pontuais que alteram o dia (eventos, simulados, feriados)
3. Expor a função `get_current_teacher(classroom_id, at)` para o fluxo de atrasos
4. Servir os dados para a tela de horários no frontend

---

## Estrutura de arquivos

```
app/domains/schedules/
├── __init__.py
├── models.py      ← ScheduleSlot, ScheduleOverride, override_classrooms
├── periods.py     ← Constante PERIODS com os 9 períodos do dia
├── helpers.py     ← get_current_teacher()
├── schemas.py     ← SlotCreate, SlotPublic, OverrideCreate, OverridePublic
└── routers.py     ← Endpoints CRUD

tests/
└── test_schedules.py
```

---

## Design do modelo de dados

### Por que duas tabelas?

A grade semanal e os eventos especiais têm naturezas diferentes. A grade é recorrente e permanente; os eventos são pontuais e afetam dias específicos. Juntar os dois em uma tabela complica consultas do tipo "qual é a grade normal desta turma?" e "quais eventos acontecem este mês?". Separando, cada consulta é simples e direta.

### `schedule_slots` — a grade fixa semanal

| Campo            | Tipo                     | Observação                            |
| ---------------- | ------------------------ | --------------------------------------- |
| `id`           | PK                       |                                         |
| `classroom_id` | FK → classrooms         | CASCADE DELETE                          |
| `teacher_id`   | FK → users (TEACHER)    | SET NULL se professor for deletado      |
| `weekday`      | Integer (0=seg … 4=sex) | Dia da semana                           |
| `period`       | Integer (1–9)           | Número do período (ver tabela abaixo) |
| `subject`      | String(100)              | Disciplina (ex: "Matemática")          |

Adicione um índice único em `(classroom_id, weekday, period)` — uma turma não pode ter dois professores no mesmo período do mesmo dia.

### `schedule_overrides` — exceções pontuais

| Campo             | Tipo        | Observação                                       |
| ----------------- | ----------- | -------------------------------------------------- |
| `id`            | PK          |                                                    |
| `override_date` | Date        | Data específica do evento                         |
| `description`   | String(200) | Ex: "Simulado ENEM", "Festa Junina"                |
| `starts_at`     | Time        | Início do horário modificado                     |
| `ends_at`       | Time        | Fim do horário modificado                         |
| `affects_all`   | Boolean     | True = toda a escola; False = só turmas definidas |
| `created_at`    | Datetime    | Auto                                               |

Crie também uma tabela de associação `override_classrooms(override_id, classroom_id)` para quando `affects_all=False` — ela define quais turmas específicas o evento afeta.

---

## Tabela de períodos

Os períodos são hardcoded como uma constante Python em `periods.py` — não precisam de tabela no banco porque raramente mudam, e quando mudar basta alterar o arquivo.

A lógica de `periods.py` deve:

1. Começar no horário de entrada da escola (07:30)
2. Calcular cada período com 50 minutos de duração
3. Pular automaticamente os três intervalos do dia (manhã, almoço, tarde)
4. Resultado esperado:

| Período | Início | Fim   |
| -------- | ------- | ----- |
| 1        | 07:30   | 08:20 |
| 2        | 08:20   | 09:10 |
| 3        | 09:30   | 10:20 |
| 4        | 10:20   | 11:10 |
| 5        | 11:10   | 12:00 |
| 6        | 13:20   | 14:10 |
| 7        | 14:10   | 15:00 |
| 8        | 15:20   | 16:10 |
| 9        | 16:10   | 17:00 |

Os intervalos são: 09:10–09:30 (manhã), 12:00–13:20 (almoço), 15:00–15:20 (tarde).

---

## Helper `get_current_teacher`

Este é o coração da feature — é ele que o fluxo de atrasos chama para descobrir quem notificar.

**Assinatura:** `get_current_teacher(classroom_id, at, db)` → `User | None`

**Lógica em ordem:**

1. Verifica se há um `ScheduleOverride` ativo para a data e horário em questão que afeta a turma (por `affects_all=True` ou pelo vínculo em `override_classrooms`). Se sim, retorna `None` — aula suspensa por evento.
2. Descobre em qual período cai o horário `at`, consultando a constante `PERIODS`. Se cair em um intervalo ou fora do horário escolar, retorna `None`.
3. Busca o `ScheduleSlot` correspondente à combinação `(classroom_id, weekday, period)`. Se não existir ou se `teacher_id` for `None`, retorna `None`.
4. Busca e retorna o `User` com o `teacher_id` encontrado.

---

## Permissões novas

Adicionar em `app/shared/rbac/permissions.py`, na classe `SystemPermissions`:

- `SCHEDULES_VIEW` — ver horários (todos os usuários logados)
- `SCHEDULES_MANAGE` — criar, editar e deletar slots e overrides (coordenação e admin)

Adicionar em `ROLE_PERMISSIONS`:

- `SCHEDULES_VIEW` para STUDENT, GUARDIAN, TEACHER e PORTER
- COORDINATOR e ADMIN já recebem tudo automaticamente

---

## Endpoints

Prefixo: `/schedules`

| Método | Rota                                      | Permissão       | Comportamento                           |
| ------- | ----------------------------------------- | ---------------- | --------------------------------------- |
| GET     | `/schedules/periods`                    | qualquer logado  | Retorna a tabela de períodos como JSON |
| GET     | `/schedules/classroom/{id}`             | SCHEDULES_VIEW   | Grade completa de uma turma             |
| GET     | `/schedules/teacher/{id}`               | SCHEDULES_VIEW   | Grade completa de um professor          |
| GET     | `/schedules/current-teacher/{class_id}` | SCHEDULES_VIEW   | Professor em aula agora nesta turma     |
| POST    | `/schedules/slots`                      | SCHEDULES_MANAGE | Criar slot                              |
| PUT     | `/schedules/slots/{id}`                 | SCHEDULES_MANAGE | Editar slot                             |
| DELETE  | `/schedules/slots/{id}`                 | SCHEDULES_MANAGE | Remover slot                            |
| GET     | `/schedules/overrides`                  | SCHEDULES_VIEW   | Listar eventos especiais                |
| POST    | `/schedules/overrides`                  | SCHEDULES_MANAGE | Criar evento especial                   |
| DELETE  | `/schedules/overrides/{id}`             | SCHEDULES_MANAGE | Remover evento especial                 |

**`GET /schedules/periods`** é consumido pelo frontend para montar a tabela visual da grade.

**`GET /schedules/current-teacher/{classroom_id}`** é o endpoint público do helper — retorna o professor atual ou indica que não há aula no momento.

---

## Schemas

**`SlotCreate`** — campos obrigatórios para criar um slot: `classroom_id`, `teacher_id` (nullable), `weekday` (0–4), `period` (1–9), `subject`.

**`SlotPublic`** — mesmos campos + `id`, com `from_attributes=True`.

**`SlotList`** — wrapper `{ slots: [...] }`.

**`OverrideCreate`** — campos para criar um evento: `override_date`, `description`, `starts_at`, `ends_at`, `affects_all` (padrão True), `classroom_ids` (lista de IDs para quando `affects_all=False`).

**`OverridePublic`** — campos escalares do override + `id` e `created_at`, com `from_attributes=True`.

---

## Passo a Passo de Implementação

### Passo 1 — Criar `periods.py`

Implemente a função `_build_periods()` que calcula os 9 períodos a partir do horário de início e dos intervalos fixos. Armazene o resultado em uma constante `PERIODS`.

Valide imediatamente com testes unitários simples (sem banco de dados):

- O período 1 começa às 07:30
- O período 3 começa às 09:30 (após o intervalo da manhã)
- Nenhum período cobre o horário do almoço (12:00–13:20)
- Existem exatamente 9 períodos

### Passo 2 — Criar `models.py`

Crie `ScheduleSlot` com o índice único em `(classroom_id, weekday, period)` para impedir conflitos. Crie `ScheduleOverride` e a tabela de associação `override_classrooms`. Use o `mapper_registry` compartilhado.

### Passo 3 — Criar `schemas.py`

Crie os schemas conforme descrito na seção de Schemas acima.

### Passo 4 — Criar `helpers.py`

Implemente `get_current_teacher()` conforme a lógica descrita na seção do helper.

### Passo 5 — Criar `routers.py`

Siga o padrão de `occurrences/routers.py`. Para evitar repetição, crie um helper interno `_get_slot_or_404` que centraliza a busca e o lançamento de 404.

### Passo 6 — Registrar no `app/main.py`

Importe o router do domínio `schedules` e registre com `app.include_router(...)`.

### Passo 7 — Atualizar `migrations/env.py`

Importe os models `ScheduleSlot` e `ScheduleOverride` para que o Alembic os detecte ao gerar migrations.

### Passo 8 — Gerar e aplicar migration

Execute `alembic revision --autogenerate` com uma mensagem descritiva, confira o arquivo gerado e aplique com `alembic upgrade head`.

### Passo 9 — Testes

Crie `tests/test_schedules.py` cobrindo:

- **Unitários (sem banco):** contagem de períodos, horários corretos, ausência de períodos nos intervalos
- **CRUD:** criar slot, tentar criar duplicata (deve retornar 409), editar, deletar
- **Helper:** retorna professor quando está em aula, retorna `None` no intervalo, retorna `None` quando há override ativo

---

## Checklist de Implementação

- [ ] Criar `app/domains/schedules/__init__.py`
- [ ] Criar `app/domains/schedules/periods.py` + testes unitários dos períodos
- [ ] Criar `app/domains/schedules/models.py` (ScheduleSlot, ScheduleOverride, override_classrooms)
- [ ] Criar `app/domains/schedules/schemas.py`
- [ ] Criar `app/domains/schedules/helpers.py` (get_current_teacher)
- [ ] Criar `app/domains/schedules/routers.py`
- [ ] Adicionar `SCHEDULES_VIEW` e `SCHEDULES_MANAGE` em `permissions.py`
- [ ] Atualizar `ROLE_PERMISSIONS` para incluir `SCHEDULES_VIEW` nas roles corretas
- [ ] Registrar router em `app/main.py`
- [ ] Importar models em `migrations/env.py`
- [ ] Gerar e aplicar migration
- [ ] Criar `tests/test_schedules.py`
