# Feature: Delays (Atrasos) — Guia de Implementação

> Sistema de registro e aprovação de atrasos de alunos, envolvendo porteiro,
> coordenação, professor DT e notificação aos responsáveis.

---

## Objetivo

Registrar quando um aluno chega atrasado, controlar a aprovação da entrada e notificar as partes envolvidas (coordenação, professor DT, responsável).

---

## Fluxo Completo

```
1. Aluno chega atrasado na escola
   ↓
2. PORTEIRO registra o atraso no sistema
   ↓
3. Sistema notifica COORDENAÇÃO (pendente)
   ↓
4. COORDENAÇÃO aprova ou rejeita a entrada
   ↓
   ├─ Se APROVADO:
   │   ├─ Notifica PROFESSOR DT da turma  ← via get_current_teacher()
   │   ├─ Notifica RESPONSÁVEL do aluno
   │   └─ Aluno entra
   └─ Se REJEITADO:
       ├─ Notifica RESPONSÁVEL do aluno
       └─ Aluno não entra
```

---

## Modelo de Dados

### Tabela: `delays`

| Campo                | Tipo           | Observação                                         |
| -------------------- | -------------- | ---------------------------------------------------- |
| `id`               | PK             |                                                      |
| `student_id`       | FK → users    | CASCADE DELETE — atraso some se aluno for deletado  |
| `registered_by_id` | FK → users    | SET NULL — atraso fica se porteiro for deletado     |
| `approved_by_id`   | FK → users    | Nullable — preenchido só ao aprovar/rejeitar       |
| `delay_date`       | Date           | Data do atraso (YYYY-MM-DD)                          |
| `arrival_time`     | Time           | Hora que o aluno chegou                              |
| `expected_time`    | Time           | Hora esperada (07:30 fixo no MVP)                    |
| `delay_minutes`    | Integer        | Calculado automaticamente ao registrar               |
| `status`           | Enum           | PENDING / APPROVED / REJECTED                        |
| `reason`           | Text, nullable | Motivo informado pelo aluno/porteiro                 |
| `rejection_reason` | Text, nullable | Motivo da rejeição (preenchido pela coordenação) |
| `created_at`       | Datetime       | Auto                                                 |
| `updated_at`       | Datetime       | Auto                                                 |

### Enum `DelayStatus`

Três estados: `PENDING` (aguardando decisão), `APPROVED` (entrada autorizada), `REJECTED` (entrada negada).

### Transições de estado permitidas

```
PENDING → APPROVED  (estado final)
PENDING → REJECTED  (estado final)
```

Uma vez decidido, o status não pode ser alterado. Isso simplifica a lógica e evita conflitos.

---

## Permissões RBAC

As permissões estão definidas em `app/shared/rbac/permissions.py`.
As permissões do domínio de delays que precisam ser adicionadas/verificadas:

| Permissão                    | Quem tem                     | Para quê                             |
| ----------------------------- | ---------------------------- | ------------------------------------ |
| `DELAYS_CREATE`             | Porteiro                     | Registrar atraso                     |
| `DELAYS_REVIEW`             | Coordenador, Admin           | Aprovar **e** rejeitar entrada       |
| `DELAYS_VIEW_ALL`           | Porteiro, Coordenador, Admin | Ver todos os atrasos                 |
| `DELAYS_VIEW_OWN`           | Aluno                        | Ver os próprios atrasos             |
| `DELAYS_VIEW_CHILD`         | Responsável                 | Ver atrasos do(s) filho(s)           |
| `DELAYS_VIEW_OWN_CLASSROOM` | Professor DT (is_tutor=True) | Ver atrasos da própria turma        |

> **Nota de design:** A permissão de aprovar e rejeitar é única — `DELAYS_REVIEW`. O
> tipo de ação (aprovar vs rejeitar) é determinado pela URL (`/approve` vs `/reject`),
> não por permissões diferentes. Isso simplifica o RBAC e o `PermissionChecker`.
>
> O plano original mencionava `DELAYS_APPROVE` e `DELAYS_REJECT` separados.
> A implementação usa `DELAYS_REVIEW` para ambos — essa decisão é válida e preferível.

### Atualizar `ROLE_PERMISSIONS`

As seguintes entradas precisam ser adicionadas/verificadas em `permissions.py`:

```python
UserRole.PORTER: {
    SystemPermissions.DELAYS_CREATE,
    SystemPermissions.DELAYS_VIEW_ALL,
    # ... já existentes
},
UserRole.STUDENT: {
    SystemPermissions.DELAYS_VIEW_OWN,
    # ... já existentes
},
UserRole.GUARDIAN: {
    SystemPermissions.DELAYS_VIEW_CHILD,
    # ... já existentes
},
# TEACHER com is_tutor=True recebe DELAYS_VIEW_OWN_CLASSROOM via TUTOR_EXTRA_PERMISSIONS
# COORDINATOR e ADMIN já recebem tudo automaticamente (incluindo DELAYS_REVIEW)
```

> **Nota:** `DELAYS_VIEW_OWN_CLASSROOM` é concedida via `TUTOR_EXTRA_PERMISSIONS` (já
> definido em `permissions.py`), não via `ROLE_PERMISSIONS` do TEACHER padrão.
> Verificar que `DELAYS_REVIEW` está em `SystemPermissions` e que Coordenador/Admin
> o recebem via `{*SystemPermissions}`.

---

## Estrutura de arquivos

```
app/domains/delays/
├── __init__.py
├── models.py          ← Model Delay + Enum DelayStatus
├── schemas.py         ← DelayCreate, DelayApprove, DelayPublic, DelayList
├── routers.py         ← Endpoints com RBAC
└── notifications.py   ← Placeholders de notificação

tests/
└── test_delays.py
```

---

## Controle de Acesso por Endpoint

A permissão RBAC é o primeiro filtro. As regras abaixo se aplicam **depois** que o
`PermissionChecker` já aprovou o acesso, restringindo quais registros cada role pode
ver ou manipular.

### `POST /delays` — Registrar atraso

Apenas Porteiro tem `DELAYS_CREATE`. Sem verificações secundárias — o porteiro pode
registrar atraso para qualquer aluno.

### `GET /delays` — Listar todos

Apenas Coordenador, Admin e Porteiro têm `DELAYS_VIEW_ALL`. Retorna todos os registros
sem filtro de ownership. Sem verificações secundárias.

### `GET /delays/pending` — Listar pendentes

Apenas quem tem `DELAYS_REVIEW` (Coordenador e Admin). Sem verificações secundárias —
é um atalho da tela de aprovação.

### `GET /delays/me` — Meus atrasos

Apenas Aluno tem `DELAYS_VIEW_OWN`. Filtra obrigatoriamente por
`student_id == current_user.id` — o aluno nunca vê atrasos de outro aluno por
construção da query.

### `GET /delays/{id}` — Detalhe de um atraso

Este endpoint aceita múltiplas permissões — qualquer uma delas libera o acesso:
`DELAYS_VIEW_ALL`, `DELAYS_VIEW_OWN`, `DELAYS_VIEW_CHILD`, `DELAYS_VIEW_OWN_CLASSROOM`.
O `PermissionChecker` recebe o conjunto completo. Depois, aplica-se a regra secundária
conforme o role:

| Role                | Condição de acesso                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------ |
| Coordenador / Admin | Qualquer registro                                                                                      |
| Porteiro            | Qualquer registro (tem `DELAYS_VIEW_ALL`)                                                             |
| Aluno               | Apenas se `delay.student_id == current_user.id` — 403 caso contrário                                |
| Responsável        | Apenas se o aluno do atraso for filho seu (verificar `guardian_student`) — 403 caso contrário        |
| Professor DT        | Apenas se `aluno.classroom_id == current_user.classroom_id` — 403 caso contrário                     |

> A implementação deve buscar o delay, identificar o role do `current_user` e aplicar
> a verificação correspondente antes de retornar.

### `PATCH /delays/{id}/approve` — Aprovar

Apenas Coordenador e Admin têm `DELAYS_REVIEW`. Sem verificações secundárias.

### `PATCH /delays/{id}/reject` — Rejeitar

Mesma permissão `DELAYS_REVIEW`. Sem verificações secundárias.

---

## Schemas

**`DelayCreate`** — campos preenchidos pelo porteiro ao registrar:

- `student_id` — aluno que atrasou
- `arrival_time` — hora que chegou
- `reason` — motivo (opcional, informado pelo aluno/porteiro)
- O campo `delay_date` é preenchido automaticamente com a data de hoje no router
- O campo `expected_time` é fixo (07:30) no MVP

**`DelayApprove`** — body usado nos endpoints de aprovação e rejeição:

- `rejection_reason` — motivo da rejeição (opcional; relevante só no `/reject`)
- O novo status (APPROVED ou REJECTED) vem da URL, não do body
- `approved_by_id` é preenchido automaticamente com `current_user.id` no router

**`DelayPublic`** — retorno completo da API, incluindo todos os campos escalares e os
timestamps. Requer `from_attributes=True`.

**`DelayList`** — wrapper `{ delays: [...] }`.

---

## Endpoints

Prefixo: `/delays`

| Método | Rota                     | Permissão           | Comportamento                      |
| ------- | ------------------------ | -------------------- | ---------------------------------- |
| POST    | `/delays`              | DELAYS_CREATE        | Registrar atraso                   |
| GET     | `/delays`              | DELAYS_VIEW_ALL      | Listar todos (com filtros)         |
| GET     | `/delays/pending`      | DELAYS_REVIEW        | Listar pendentes                   |
| GET     | `/delays/me`           | DELAYS_VIEW_OWN      | Meus atrasos (aluno)               |
| GET     | `/delays/{id}`         | vários (ver acima)   | Detalhe de um atraso               |
| PATCH   | `/delays/{id}/approve` | DELAYS_REVIEW        | Aprovar entrada                    |
| PATCH   | `/delays/{id}/reject`  | DELAYS_REVIEW        | Rejeitar entrada                   |

---

## Lógica dos Endpoints (Passo a Passo)

### `POST /delays`

1. Verificar que `DELAYS_CREATE` está satisfeita (apenas Porteiro).
2. Buscar o `User` com `student_id` — 404 se não existir.
3. Verificar que `student.role == STUDENT` — 422 se não for aluno.
4. Verificar se já existe um `Delay` com o mesmo `student_id` e `delay_date == date.today()` — 409 Conflict se existir.
5. Calcular `delay_minutes` como a diferença em minutos entre `arrival_time` e `expected_time` (07:30).
6. Criar o registro com `status=PENDING`, `delay_date=date.today()`, `expected_time=time(7,30)` e `registered_by_id=current_user.id`.
7. Fazer `commit`, `refresh` e chamar `notify_delay_registered(delay.id)`.
8. Retornar o delay em `DelayPublic` com status 201.

### `GET /delays`

1. Verificar que `DELAYS_VIEW_ALL` está satisfeita (Porteiro, Coordenador e Admin).
2. Construir a query base sobre `Delay`. Aplicar filtros opcionais:
   - `?status=PENDING|APPROVED|REJECTED`
   - `?date=YYYY-MM-DD`
3. Retornar encapsulado em `DelayList`.

### `GET /delays/pending`

1. Verificar que `DELAYS_REVIEW` está satisfeita (Coordenador e Admin).
2. Buscar todos os `Delay` onde `status == PENDING`, ordenados por `created_at` ASC.
3. Retornar encapsulado em `DelayList`.

> **Atenção ao roteamento:** `/delays/pending` deve ser declarado **antes** de
> `/delays/{id}` no router. O FastAPI roteia de cima para baixo — se `/{id}` vier
> antes, a string `"pending"` será capturada como `id`, causando erro de conversão.

### `GET /delays/me`

1. Verificar que `DELAYS_VIEW_OWN` está satisfeita (Aluno).
2. Buscar todos os `Delay` onde `student_id == current_user.id`.
3. Retornar encapsulado em `DelayList`.

> **Atenção ao roteamento:** `/delays/me` também deve ser declarado antes de
> `/delays/{id}` pelo mesmo motivo acima.

### `GET /delays/{id}`

1. Buscar o `Delay` pelo `id` — 404 se não existir (`_get_delay_or_404`).
2. Verificar se o usuário tem pelo menos uma das permissões de visualização.
3. Aplicar regra secundária conforme o role.
4. Retornar em `DelayPublic`.

### `PATCH /delays/{id}/approve`

1. Verificar que `DELAYS_REVIEW` está satisfeita (Coordenador e Admin).
2. Buscar o `Delay` pelo `id` — 404 se não existir.
3. Verificar que `delay.status == PENDING` — 409 Conflict se já foi decidido.
4. Atualizar: `status=APPROVED`, `approved_by_id=current_user.id`.
5. Fazer `commit`, `refresh` e chamar `notify_delay_approved(delay.id)`.
6. Retornar o delay atualizado em `DelayPublic`.

### `PATCH /delays/{id}/reject`

1. Verificar que `DELAYS_REVIEW` está satisfeita.
2. Buscar o `Delay` pelo `id` — 404 se não existir.
3. Verificar que `delay.status == PENDING` — 409 Conflict se já foi decidido.
4. Atualizar: `status=REJECTED`, `approved_by_id=current_user.id`, `rejection_reason=data.rejection_reason`.
5. Fazer `commit`, `refresh` e chamar `notify_delay_rejected(delay.id)`.
6. Retornar o delay atualizado em `DelayPublic`.

---

## Exemplos de Retorno

### `POST /delays` — 201 Created

```json
{
  "id": 47,
  "student_id": 101,
  "registered_by_id": 12,
  "approved_by_id": null,
  "delay_date": "2025-10-15",
  "arrival_time": "08:05:00",
  "expected_time": "07:30:00",
  "delay_minutes": 35,
  "status": "PENDING",
  "reason": "Trânsito na Av. Principal",
  "rejection_reason": null,
  "created_at": "2025-10-15T08:06:12",
  "updated_at": "2025-10-15T08:06:12"
}
```

### `PATCH /delays/{id}/approve` — 200 OK

```json
{
  "id": 47,
  "student_id": 101,
  "registered_by_id": 12,
  "approved_by_id": 5,
  "delay_date": "2025-10-15",
  "arrival_time": "08:05:00",
  "expected_time": "07:30:00",
  "delay_minutes": 35,
  "status": "APPROVED",
  "reason": "Trânsito na Av. Principal",
  "rejection_reason": null,
  "created_at": "2025-10-15T08:06:12",
  "updated_at": "2025-10-15T08:10:00"
}
```

### `PATCH /delays/{id}/reject` — 200 OK

```json
{
  "id": 47,
  "status": "REJECTED",
  "approved_by_id": 5,
  "rejection_reason": "Responsável não atendeu — entrada não autorizada",
  "updated_at": "2025-10-15T08:11:00"
}
```

### `409 Conflict` — delay já decidido

```json
{ "detail": "Delay already decided" }
```

---

## Notificações (Placeholders)

Crie `app/domains/delays/notifications.py` com três funções assíncronas vazias:

- `notify_delay_registered(delay_id)` — chamada após o POST
- `notify_delay_approved(delay_id)` — chamada após o PATCH /approve
- `notify_delay_rejected(delay_id)` — chamada após o PATCH /reject

Essas funções serão implementadas na feature de WhatsApp (veja `3-INTEGRACAO_WHATSAPP.md`).

---

## Simplificações para o MVP

1. **Horário fixo:** `expected_time = 07:30` hardcoded — depois evolui para horário por turma via `schedule_slots`
2. **Sem reversão:** status é final — coordenação decide uma vez, acabou
3. **Sem auditoria de mudanças:** basta o campo `approved_by_id`, não precisa de histórico completo

---

## Passo a Passo de Implementação

### Passo 1 — Verificar permissões em `permissions.py`

Confirmar que `DELAYS_REVIEW` existe em `SystemPermissions` e que está presente
no mapeamento de Coordenador e Admin (já está via `{*SystemPermissions}`).
Confirmar que `DELAYS_VIEW_OWN_CLASSROOM` está em `TUTOR_EXTRA_PERMISSIONS`.

### Passo 2 — Model

Crie a tabela `delays` com todos os campos acima, o Enum `DelayStatus` e o
`mapper_registry` compartilhado. Políticas de FK:
- `CASCADE` para `student_id`
- `SET NULL` para `registered_by_id` e `approved_by_id`

O campo `updated_at` deve usar `onupdate=func.now()` além do `server_default`.

### Passo 3 — Schemas

Crie os quatro schemas: `DelayCreate`, `DelayApprove`, `DelayPublic`, `DelayList`.

### Passo 4 — Notifications

Crie `notifications.py` com as três funções async vazias antes de implementar os
routers (evita importar algo que não existe).

### Passo 5 — Routers

Implemente todos os endpoints seguindo o padrão de `occurrences/routers.py`. Use
`_get_delay_or_404` como helper interno. **Atenção à ordem de declaração:** `/pending`
e `/me` devem vir antes de `/{id}`.

### Passo 6 — Registrar no `app/main.py`

Importe o router de delays e adicione com `app.include_router(delays_routers.router)`.

### Passo 7 — Atualizar `migrations/env.py`

Adicione `import app.domains.delays.models  # noqa: F401` ao bloco de imports do
`env.py`.

### Passo 8 — Gerar e aplicar migration

```bash
alembic revision --autogenerate -m "add delays"
alembic upgrade head
```

Inspecione o arquivo gerado e confirme que `delay_status` enum, a tabela `delays` e
todas as FKs estão corretas.

### Passo 9 — Testes

Crie `tests/test_delays.py` importando os models de delays no conftest (ou diretamente
no arquivo de teste, para `metadata.create_all` criar a tabela).

Adicionar ao `tests/conftest.py`:
```python
from app.domains.delays.models import Delay  # noqa: F401
```

Cobrir:

**Permissões:**
- Porteiro pode registrar atraso
- Aluno não pode registrar atraso (403)
- Coordenador pode aprovar e rejeitar
- Professor não pode aprovar nem rejeitar (403)
- Aluno só vê os próprios atrasos no GET /delays/me
- Aluno não vê atraso de outro aluno no GET /delays/{id} (403)
- Responsável não vê atraso de aluno que não é filho (403)
- Professor DT vê atraso de aluno da própria turma
- Professor DT não vê atraso de aluno de outra turma (403)

**Fluxo principal:**
- Registro cria com `status=PENDING`
- Aprovação muda para `APPROVED` e preenche `approved_by_id`
- Rejeição muda para `REJECTED` e preenche `rejection_reason`
- Não pode aprovar/rejeitar delay já decidido (409)
- `delay_minutes` calculado corretamente

**Validações:**
- Não pode registrar atraso para usuário que não é STUDENT (422)
- Não pode registrar atraso duplicado no mesmo dia para o mesmo aluno (409)
- `GET /delays/pending` retorna apenas os PENDING
- Filtros de `GET /delays` por status e data funcionam

---

## Checklist de Implementação

- [ ] Verificar/confirmar `DELAYS_REVIEW` em `SystemPermissions`
- [ ] Criar `app/domains/delays/__init__.py`
- [ ] Criar `app/domains/delays/models.py` (Delay + DelayStatus enum)
- [ ] Criar `app/domains/delays/schemas.py` (Create, Approve, Public, List)
- [ ] Criar `app/domains/delays/notifications.py` (3 funções async vazias)
- [ ] Criar `app/domains/delays/routers.py` (todos os endpoints, ordem correta)
- [ ] Registrar router em `app/main.py`
- [ ] Importar model em `migrations/env.py`
- [ ] Importar model em `tests/conftest.py`
- [ ] Gerar e aplicar migration (`alembic revision --autogenerate -m "add delays"`)
- [ ] Criar `tests/test_delays.py` (permissões, fluxo, validações)
- [ ] Testar fluxo completo: porteiro registra → coordenação aprova → aluno vê
