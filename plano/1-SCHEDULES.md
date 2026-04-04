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

| Campo           | Tipo                                                | Observação                               |
| --------------- | --------------------------------------------------- | ---------------------------------------- |
| `id`            | PK                                                  |                                          |
| `classroom_id`  | FK → classrooms                                     | CASCADE DELETE                           |
| `teacher_id`    | FK → users (TEACHER)                                | SET NULL se professor for deletado       |
| `type`          | Enum (`class_period`, `snack_break`, `lunch_break`) | Tipo do período                          |
| `title`         | String(200)                                         | Nome do período (ex: "Matemática")       |
| `weekday`       | Integer (1=dom … 7=sáb)                             | Dia da semana via enum `WeekdayEnum`     |
| `period_number` | Integer (1–9), nullable                             | Número do período (None para intervalos) |

Adicione um índice único em `(classroom_id, weekday, period_number, type)` — uma turma não pode ter dois professores no mesmo período do mesmo dia.

> **Nota:** O campo `subject` (disciplina) **não existe** na implementação atual. O campo equivalente é `title` (String 200), que armazena o nome do período/disciplina. O campo `type` distingue aulas de intervalos.

### `schedule_overrides` — exceções pontuais

| Campo           | Tipo        | Observação                                        |
| --------------- | ----------- | ------------------------------------------------- |
| `id`            | PK          |                                                   |
| `title`         | String(200) | Ex: "Simulado ENEM", "Festa Junina"               |
| `override_date` | Date        | Data específica do evento                         |
| `starts_at`     | Time        | Início do horário modificado                      |
| `ends_at`       | Time        | Fim do horário modificado                         |
| `affects_all`   | Boolean     | True = toda a escola; False = só turmas definidas |
| `created_at`    | Datetime    | Auto                                              |

> **Nota:** O campo chama-se `title`, não `description`. Use `title` nos schemas e consultas.

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
| ------- | ------ | ----- |
| 1       | 07:30  | 08:20 |
| 2       | 08:20  | 09:10 |
| 3       | 09:30  | 10:20 |
| 4       | 10:20  | 11:10 |
| 5       | 11:10  | 12:00 |
| 6       | 13:20  | 14:10 |
| 7       | 14:10  | 15:00 |
| 8       | 15:20  | 16:10 |
| 9       | 16:10  | 17:00 |

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

| Método | Rota                                        | Permissão        | Comportamento                          |
| ------ | ------------------------------------------- | ---------------- | -------------------------------------- |
| GET    | `/schedules/periods`                        | qualquer logado  | Retorna a tabela de períodos como JSON |
| GET    | `/schedules/classroom/{id}`                 | SCHEDULES_VIEW   | Grade completa de uma turma            |
| GET    | `/schedules/teacher/{id}`                   | SCHEDULES_VIEW   | Grade completa de um professor         |
| GET    | `/schedules/current-teacher/{classroom_id}` | SCHEDULES_VIEW   | Professor em aula agora nesta turma    |
| POST   | `/schedules/slots`                          | SCHEDULES_MANAGE | Criar slot                             |
| PUT    | `/schedules/slots/{id}`                     | SCHEDULES_MANAGE | Editar slot                            |
| DELETE | `/schedules/slots/{id}`                     | SCHEDULES_MANAGE | Remover slot                           |
| GET    | `/schedules/overrides`                      | SCHEDULES_VIEW   | Listar eventos especiais               |
| POST   | `/schedules/overrides`                      | SCHEDULES_MANAGE | Criar evento especial                  |
| DELETE | `/schedules/overrides/{id}`                 | SCHEDULES_MANAGE | Remover evento especial                |

**`GET /schedules/periods`** é consumido pelo frontend para montar a tabela visual da grade. Retorna diretamente a constante `PERIODS` (do tipo `PeriodsList`) calculada em memória — sem consulta ao banco. O `response_model` correto é `PeriodsList`, não `SlotList`. Não precisa de `session`.

**`GET /schedules/current-teacher/{classroom_id}`** é o endpoint público do helper — retorna o professor atual (`UserPublic`) ou 404 se não houver aula no momento. O `response_model` correto é `UserPublic`, não `User` (model SQLAlchemy).

> **Nota:** O parâmetro de rota é `classroom_id` (ID da turma), não `slot_id`. O stub original usava `slot_id` como alias — o nome canônico correto é `classroom_id`, alinhado com o restante da API.

> **Atenção — prefixo duplicado:** O router usa `prefix='/schedules'`, então os decoradores das rotas devem usar apenas o sufixo (ex: `'/periods'`, `'/slots'`, `'/overrides/{override_id}'`). O stub original duplicava o prefixo escrevendo `'/schedules/periods'` dentro do router — isso geraria `/schedules/schedules/periods`. Use apenas `'/periods'` etc.

---

## Controle de Acesso por Endpoint

A permissão RBAC (`SCHEDULES_VIEW` ou `SCHEDULES_MANAGE`) é verificada primeiro pelo `PermissionChecker`. Se ela for satisfeita, aplicam-se as regras secundárias abaixo, que restringem **o que** cada role pode ver ou fazer dentro da permissão concedida.

### Leitura de slots

**`GET /schedules/classroom/{classroom_id}`**

| Role                | Pode acessar                                                                              |
| ------------------- | ----------------------------------------------------------------------------------------- |
| Coordenador / Admin | Qualquer turma                                                                            |
| Professor           | Qualquer turma — a grade é informação pública da escola                                   |
| Aluno               | Apenas a própria turma (`current_user.classroom_id == classroom_id`) — 403 caso contrário |
| Responsável         | Apenas a turma de um filho seu (verificar `guardian_student`) — 403 caso contrário        |
| Porteiro            | Qualquer turma (recebe `SCHEDULES_VIEW` via `_BASE_PERMISSIONS`)                          |

> Alunos e responsáveis não devem conseguir consultar a grade de turmas alheias. A verificação deve ser feita no corpo do endpoint após o `PermissionChecker`.

**`GET /schedules/teacher/{user_id}`**

| Role                           | Pode acessar                                                               |
| ------------------------------ | -------------------------------------------------------------------------- |
| Coordenador / Admin            | Grade de qualquer professor                                                |
| Professor                      | Apenas a própria grade (`user_id == current_user.id`) — 403 caso contrário |
| Aluno / Responsável / Porteiro | Acesso negado — 403                                                        |

> Esta rota expõe a grade completa de um professor individual. Alunos e responsáveis não têm necessidade legítima de consultar isso; a grade da turma deles é suficiente.

**`GET /schedules/current-teacher/{classroom_id}`**

| Role                           | Pode acessar                                                                              |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| Coordenador / Admin / Porteiro | Qualquer turma                                                                            |
| Professor                      | Qualquer turma — útil para saber quem está em aula numa sala vizinha                      |
| Aluno                          | Apenas a própria turma (`current_user.classroom_id == classroom_id`) — 403 caso contrário |
| Responsável                    | Apenas a turma de um filho seu — 403 caso contrário                                       |

### Escrita de slots (SCHEDULES_MANAGE)

`POST /schedules/slots`, `PUT /schedules/slots/{slot_id}` e `DELETE /schedules/slots/{slot_id}` são restritos a Coordenador e Admin por definição da permissão `SCHEDULES_MANAGE`. Nenhuma verificação secundária é necessária — qualquer usuário que passar pelo `PermissionChecker` já tem autorização total sobre slots de qualquer turma.

### Overrides

**`GET /schedules/overrides`** — sem restrição secundária. Overrides afetam a escola inteira ou turmas específicas, mas a lista é informação institucional acessível a todos com `SCHEDULES_VIEW`.

**`POST /schedules/overrides`** e **`DELETE /schedules/overrides/{override_id}`** — restritos a Coordenador e Admin por `SCHEDULES_MANAGE`. Sem verificação secundária.

---

## Schemas

**`SlotCreate`** — campos obrigatórios para criar um slot: `classroom_id`, `teacher_id` (nullable), `type` (`class_period` | `snack_break` | `lunch_break`), `title` (String 200), `weekday` (enum `WeekdayEnum`, 1=dom…7=sáb), `period_number` (1–9, nullable para intervalos).

> **Nota:** Os campos `subject` e `period` **não existem**. Os nomes corretos são `title` e `period_number`. O `weekday` abrange de domingo (1) a sábado (7), não apenas 2–6.

**`SlotPublic`** — mesmos campos + `id`, com `from_attributes=True`.

**`SlotList`** — wrapper `{ slots: [...] }`.

**`OverrideCreate`** — campos para criar um evento: `title` (String 200), `override_date`, `starts_at`, `ends_at`, `affects_all` (padrão `True`), `classroom_ids` (lista de IDs para quando `affects_all=False`, nullable).

> **Nota:** O campo chama-se `title`, não `description`.

**`OverridePublic`** — campos escalares do override + `id` e `created_at`, com `from_attributes=True`. Inclui `classroom_ids` nullable.

**`OverrideList`** — wrapper `{ overrides: [...] }`.

---

## Lógica dos Endpoints (Passo a Passo)

### `GET /schedules/periods`

1. Verificar que há um usuário logado (`current_user` — sem permissão específica).
2. Retornar diretamente a constante `PERIODS` (tipo `PeriodsList`), gerada em memória por `periods.py` na inicialização do módulo.
3. Não há consulta ao banco. `session` não é necessário neste endpoint.

### `GET /schedules/classroom/{classroom_id}`

1. Verificar que a permissão `SCHEDULES_VIEW` está satisfeita.
2. Aplicar controle de acesso secundário pelo role:
   - **Aluno:** verificar se `current_user.classroom_id == classroom_id` — 403 caso contrário.
   - **Responsável:** carregar os filhos via `guardian_student` e verificar se algum tem `classroom_id == classroom_id` — 403 caso contrário.
   - **Coordenador, Admin, Professor, Porteiro:** sem restrição adicional.
3. Buscar no banco todos os `ScheduleSlot` onde `classroom_id == :classroom_id`.
4. Retornar a lista encapsulada no schema `SlotList`.

### `GET /schedules/teacher/{user_id}`

1. Verificar que a permissão `SCHEDULES_VIEW` está satisfeita.
2. Aplicar controle de acesso secundário pelo role:
   - **Professor:** verificar se `user_id == current_user.id` — 403 caso contrário.
   - **Aluno / Responsável / Porteiro:** acesso negado — 403 incondicionalmente.
   - **Coordenador / Admin:** sem restrição adicional.
3. Buscar no banco todos os `ScheduleSlot` onde `teacher_id == :user_id`.
4. Retornar a lista encapsulada no schema `SlotList`.

### `GET /schedules/current-teacher/{classroom_id}`

1. Verificar que a permissão `SCHEDULES_VIEW` está satisfeita.
2. Aplicar controle de acesso secundário pelo role:
   - **Aluno:** verificar se `current_user.classroom_id == classroom_id` — 403 caso contrário.
   - **Responsável:** carregar os filhos via `guardian_student` e verificar se algum tem `classroom_id == classroom_id` — 403 caso contrário.
   - **Coordenador, Admin, Professor, Porteiro:** sem restrição adicional.
3. Obter o horário atual com `datetime.now().time()`.
4. Delegar ao helper `get_current_teacher(classroom_id, at_time, session)`.
   - O helper verifica primeiro se há um `ScheduleOverride` ativo para hoje que afeta essa turma (por `affects_all=True` ou pelo vínculo em `override_classrooms`). Se houver, retorna `None`.
   - Em seguida, verifica se o horário atual cai em um `class_period` na constante `PERIODS`. Se cair em intervalo ou fora do horário escolar, retorna `None`.
   - Por último, busca o `ScheduleSlot` correspondente a `(classroom_id, weekday_hoje, period_number_atual)` com `teacher_id IS NOT NULL`. Se não existir, retorna `None`.
   - Se encontrou, busca e retorna o `User` com aquele `teacher_id`.
5. Se o helper retornar `None`, lançar 404 com `detail='No teacher in class at this time'`.
6. Se retornar um `User`, serializá-lo em `UserPublic` e retornar.

### `POST /schedules/slots`

1. Verificar que a permissão `SCHEDULES_MANAGE` está satisfeita.
2. Validar o body com `SlotCreate`.
3. Verificar se já existe um `ScheduleSlot` com a mesma combinação `(classroom_id, weekday, period_number, type)` — retornar 409 Conflict se existir.
4. Criar e persistir a instância de `ScheduleSlot` com os dados recebidos.
5. Fazer `commit`, `refresh` e retornar o slot em `SlotPublic` com status 201.

### `PUT /schedules/slots/{slot_id}`

1. Verificar que a permissão `SCHEDULES_MANAGE` está satisfeita.
2. Buscar o `ScheduleSlot` pelo `slot_id` — 404 se não existir (usar `_get_slot_or_404`).
3. Verificar se a nova combinação `(classroom_id, weekday, period_number, type)` já está em uso por **outro** slot (excluir o próprio `slot_id` da checagem) — retornar 409 Conflict se existir.
4. Atualizar os campos da instância usando `model_dump(exclude_unset=True)`.
5. Fazer `commit`, `refresh` e retornar o slot atualizado em `SlotPublic`.

### `DELETE /schedules/slots/{slot_id}`

1. Verificar que a permissão `SCHEDULES_MANAGE` está satisfeita.
2. Buscar o `ScheduleSlot` pelo `slot_id` — 404 se não existir.
3. Chamar `refresh` para garantir que todos os campos estejam em memória antes do delete.
4. Deletar a instância e fazer `commit`.
5. Retornar o slot deletado em `SlotPublic`.

### `GET /schedules/overrides`

1. Verificar que a permissão `SCHEDULES_VIEW` está satisfeita.
2. Buscar todos os `ScheduleOverride` no banco (pode ordenar por `override_date` DESC).
3. Retornar a lista encapsulada em `OverrideList`.

### `POST /schedules/overrides`

1. Verificar que a permissão `SCHEDULES_MANAGE` está satisfeita.
2. Validar o body com `OverrideCreate`.
3. Criar a instância de `ScheduleOverride` com os campos escalares (`title`, `override_date`, `starts_at`, `ends_at`, `affects_all`).
4. Adicionar à sessão e fazer `flush` (sem commit ainda) para obter o `override.id` gerado pelo banco.
5. Se `affects_all=False` e `classroom_ids` não for vazio, inserir as linhas em `override_classrooms` usando `insert()` com a lista de `{'override_id': ..., 'classroom_id': ...}`.
6. Fazer `commit`, `refresh` e retornar o override em `OverridePublic` com status 201.

### `DELETE /schedules/overrides/{override_id}`

1. Verificar que a permissão `SCHEDULES_MANAGE` está satisfeita.
2. Buscar o `ScheduleOverride` pelo `override_id` — 404 se não existir.
3. Chamar `refresh` para garantir que todos os campos estejam em memória antes do delete.
4. Deletar a instância e fazer `commit`. As linhas em `override_classrooms` são removidas automaticamente pelo `CASCADE` definido na FK.
5. Retornar o override deletado em `OverridePublic`.

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

- [x] Criar `app/domains/schedules/__init__.py`
- [x] Criar `app/domains/schedules/periods.py` + testes unitários dos períodos
- [x] Criar `app/domains/schedules/models.py` (ScheduleSlot, ScheduleOverride, override_classrooms)
- [x] Criar `app/domains/schedules/schemas.py`
- [x] Criar `app/domains/schedules/helpers.py` (get_current_teacher)
- [x] Criar `app/domains/schedules/routers.py`
- [x] Adicionar `SCHEDULES_VIEW` e `SCHEDULES_MANAGE` em `permissions.py`
- [x] Atualizar `ROLE_PERMISSIONS` para incluir `SCHEDULES_VIEW` nas roles corretas
- [x] Registrar router em `app/main.py`
- [x] Importar models em `migrations/env.py`
- [x] Gerar e aplicar migration
- [x] Criar `tests/test_schedules.py`
