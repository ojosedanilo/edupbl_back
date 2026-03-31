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

Todas as permissões já estão definidas em `app/shared/rbac/permissions.py`. Basta usá-las nos endpoints:

| Permissão                | Quem tem           | Para quê                   |
| ------------------------- | ------------------ | --------------------------- |
| `DELAYS_CREATE`         | Porteiro           | Registrar atraso            |
| `DELAYS_APPROVE`        | Coordenador, Admin | Aprovar ou rejeitar entrada |
| `DELAYS_VIEW_ALL`       | Coordenador, Admin | Ver todos os atrasos        |
| `DELAYS_VIEW_OWN`       | Aluno              | Ver os próprios atrasos    |
| `DELAYS_VIEW_CHILD`     | Responsável       | Ver atrasos do(s) filho(s)  |
| `DELAYS_VIEW_OWN_CLASS` | Professor DT       | Ver atrasos da sua turma    |

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

**`DelayPublic`** — retorno completo da API, incluindo todos os campos escalares e os timestamps. Requer `from_attributes=True`.

**`DelayList`** — wrapper `{ delays: [...] }`.

---

## Endpoints

Prefixo: `/delays`

### `POST /delays` — Registrar atraso

- **Permissão:** `DELAYS_CREATE`
- **Lógica:**
  1. Verifica se `student_id` existe e tem `role=STUDENT` — 404 se não existir, 422 se não for aluno
  2. Impede registro duplicado: mesmo `student_id` no mesmo `delay_date` — 409 Conflict
  3. Calcula `delay_minutes` a partir da diferença entre `arrival_time` e `expected_time`
  4. Cria o registro com `status=PENDING` e `registered_by_id=current_user.id`
  5. Chama `notify_delay_registered(delay.id)` (placeholder)

### `GET /delays` — Listar todos

- **Permissão:** `DELAYS_VIEW_ALL`
- **Query params opcionais:** `status` (filtrar por PENDING/APPROVED/REJECTED), `date` (filtrar por data)

### `GET /delays/pending` — Listar pendentes

- **Permissão:** `DELAYS_APPROVE`
- Retorna apenas registros com `status=PENDING`
- Atalho útil para a tela de aprovação da coordenação

### `GET /delays/me` — Meus atrasos

- **Permissão:** `DELAYS_VIEW_OWN`
- Filtra por `student_id=current_user.id`

### `GET /delays/{id}` — Detalhes

- **Lógica de verificação por role:**
  - Aluno: só pode ver se `student_id == current_user.id` — 403 caso contrário
  - Responsável: só pode ver se o aluno é filho dele (verificar tabela `guardian_student`) — 403 caso contrário
  - Coordenador/Admin: pode ver qualquer registro

### `PATCH /delays/{id}/approve` — Aprovar

- **Permissão:** `DELAYS_APPROVE`
- **Lógica:**
  1. Busca o delay — 404 se não existir
  2. Verifica que `status == PENDING` — 409 se já foi decidido
  3. Atualiza: `status=APPROVED`, `approved_by_id=current_user.id`
  4. Chama `notify_delay_approved(delay.id)` (placeholder)

### `PATCH /delays/{id}/reject` — Rejeitar

- **Permissão:** `DELAYS_APPROVE` (mesma permissão de aprovar)
- **Lógica similar ao approve**, com: `status=REJECTED` + `rejection_reason`
- Chama `notify_delay_rejected(delay.id)` (placeholder)

---

## Notificações (Placeholders)

Crie `app/domains/delays/notifications.py` com três funções assíncronas vazias:

- `notify_delay_registered(delay_id)` — chamada após o POST
- `notify_delay_approved(delay_id)` — chamada após o PATCH /approve
- `notify_delay_rejected(delay_id)` — chamada após o PATCH /reject

Essas funções serão implementadas na feature de Notificações (veja `5-INTEGRACAO_WHATSAPP.md`). Por enquanto, apenas existir e ser chamada é suficiente para não bloquear o desenvolvimento.

---

## Simplificações para o MVP

1. **Horário fixo:** `expected_time = 07:30` hardcoded — depois evolui para horário por turma via `class_schedules`
2. **Sem reversão:** status é final — coordenação decide uma vez, acabou
3. **Sem auditoria de mudanças:** basta o campo `approved_by_id`, não precisa de histórico completo por ora

---

## Passo a Passo de Implementação

### Passo 1 — Criar estrutura de pastas

Crie `app/domains/delays/` com `__init__.py`, `models.py`, `schemas.py`, `routers.py` e `notifications.py`.

### Passo 2 — Model

Crie a tabela `delays` com todos os campos acima, o Enum `DelayStatus` e o `mapper_registry` compartilhado. Atenção às políticas de deleção das FKs: `CASCADE` para `student_id`, `SET NULL` para `registered_by_id` e `approved_by_id`.

### Passo 3 — Schemas

Crie os quatro schemas conforme descrito: `DelayCreate`, `DelayApprove`, `DelayPublic`, `DelayList`.

### Passo 4 — Routers

Implemente todos os endpoints seguindo o padrão de `occurrences/routers.py`. Use um helper interno `_get_delay_or_404` para centralizar a busca e evitar repetição nos endpoints de approve, reject e GET por ID.

### Passo 5 — Notificações

Crie `notifications.py` com as três funções vazias e as chame nos endpoints corretos. Não implemente o envio real ainda.

### Passo 6 — Registrar no `app/main.py`

Importe o router do domínio `delays` e registre com `app.include_router(...)`.

### Passo 7 — Atualizar `migrations/env.py`

Importe o model `Delay` para que o Alembic o detecte.

### Passo 8 — Gerar e aplicar migration

Execute `alembic revision --autogenerate` com uma mensagem descritiva, inspecione o arquivo gerado e aplique com `alembic upgrade head`.

### Passo 9 — Testes

Crie `tests/test_delays.py` cobrindo:

**Permissões:**

- Porteiro pode registrar atraso
- Aluno não pode registrar atraso
- Coordenador pode aprovar e rejeitar
- Professor não pode aprovar nem rejeitar
- Aluno só vê os seus próprios atrasos

**Fluxo:**

- Registro cria com `status=PENDING`
- Aprovação muda para `APPROVED` e preenche `approved_by_id`
- Rejeição muda para `REJECTED` e preenche `rejection_reason`
- Não pode aprovar/rejeitar um delay já decidido (409)
- Cálculo de `delay_minutes` está correto

**Validações:**

- Não pode registrar atraso para usuário que não é STUDENT
- Não pode registrar atraso duplicado no mesmo dia para o mesmo aluno

---

## Checklist de Implementação

- [ ] Criar `app/domains/delays/__init__.py`
- [ ] Criar `app/domains/delays/models.py` (Delay + DelayStatus)
- [ ] Criar `app/domains/delays/schemas.py` (Create, Approve, Public, List)
- [ ] Criar `app/domains/delays/routers.py` (todos os endpoints)
- [ ] Criar `app/domains/delays/notifications.py` (placeholders)
- [ ] Registrar router em `app/main.py`
- [ ] Importar model em `migrations/env.py`
- [ ] Gerar e aplicar migration
- [ ] Criar `tests/test_delays.py`
- [ ] Testar fluxo completo: porteiro registra → coordenação aprova → aluno vê
