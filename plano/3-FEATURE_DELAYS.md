# 🕐 Feature: Delays (Atrasos) — Guia de Implementação

> Sistema de registro e aprovação de atrasos de alunos, envolvendo porteiro,
> coordenação, professor DT e notificação aos responsáveis.

---

## 🎯 Objetivo

Registrar quando um aluno chega atrasado, controlar a aprovação da entrada
e notificar as partes envolvidas (coordenação, professor DT, responsável).

---

## 📊 Fluxo Completo

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
   │   ├─ Notifica PROFESSOR DT da turma
   │   ├─ Notifica RESPONSÁVEL do aluno
   │   └─ Aluno entra
   │
   └─ Se REJEITADO:
       ├─ Notifica RESPONSÁVEL do aluno
       └─ Aluno não entra
```

---

## 🗂️ Modelo de Dados

### Tabela: `delays`

| Campo              | Tipo           | Observação                                      |
|--------------------|----------------|-------------------------------------------------|
| `id`               | PK             |                                                 |
| `student_id`       | FK → users     | CASCADE DELETE                                  |
| `registered_by_id` | FK → users     | SET NULL se porteiro for deletado               |
| `approved_by_id`   | FK → users     | Nullable — preenchido só ao aprovar/rejeitar    |
| `delay_date`       | Date           | Data do atraso (YYYY-MM-DD)                     |
| `arrival_time`     | Time           | Hora que o aluno chegou (HH:MM:SS)              |
| `expected_time`    | Time           | Hora esperada de chegada (fixo: 07:30 no MVP)   |
| `delay_minutes`    | Integer        | Calculado: (arrival_time - expected_time)       |
| `status`           | Enum           | PENDING / APPROVED / REJECTED                   |
| `reason`           | Text, nullable | Motivo informado pelo aluno/porteiro             |
| `rejection_reason` | Text, nullable | Motivo da rejeição (preenchido pela coordenação)|
| `created_at`       | Datetime       | Auto                                            |
| `updated_at`       | Datetime       | Auto                                            |

### Enum `DelayStatus`
```python
class DelayStatus(str, Enum):
    PENDING  = 'pending'   # Aguardando decisão
    APPROVED = 'approved'  # Entrada autorizada
    REJECTED = 'rejected'  # Entrada negada
```

---

## 🔐 Permissões RBAC

Todas as permissões já estão definidas em `app/shared/rbac/permissions.py`:

| Permissão              | Quem tem              | Para quê                             |
|------------------------|-----------------------|--------------------------------------|
| `DELAYS_CREATE`        | Porteiro              | Registrar atraso                     |
| `DELAYS_APPROVE`       | Coordenador           | Aprovar entrada                      |
| `DELAYS_REJECT`        | Coordenador           | Rejeitar entrada                     |
| `DELAYS_VIEW_ALL`      | Coordenador, Admin    | Ver todos os atrasos                 |
| `DELAYS_VIEW_OWN`      | Aluno                 | Ver seus próprios atrasos            |
| `DELAYS_VIEW_CHILD`    | Responsável           | Ver atrasos do(s) filho(s)           |
| `DELAYS_VIEW_OWN_CLASS`| Professor DT          | Ver atrasos da sua turma             |

---

## 📋 Estrutura de Arquivos

```
app/domains/delays/
├── __init__.py
├── models.py    ← Model Delay + Enum DelayStatus
├── schemas.py   ← DelayCreate, DelayApprove, DelayPublic, DelayList
└── routers.py   ← Endpoints com RBAC
tests/
└── test_delays.py
```

---

## 🛠️ Passo a Passo de Implementação

### Passo 1 — Criar estrutura de pastas

```
app/domains/delays/
├── __init__.py   (vazio)
├── models.py
├── schemas.py
└── routers.py
```

---

### Passo 2 — Model (`models.py`)

- Tabela `delays` com todos os campos do modelo de dados acima
- Enum `DelayStatus` (PENDING, APPROVED, REJECTED)
- Use `mapper_registry` de `app/shared/db/registry.py`
- FKs:
  - `student_id` → `CASCADE` (atraso some se aluno for deletado)
  - `registered_by_id` → `SET NULL` (atraso fica, porteiro pode ser deletado)
  - `approved_by_id` → `SET NULL`

---

### Passo 3 — Schemas (`schemas.py`)

Crie os seguintes schemas:

**`DelayCreate`** — usado pelo porteiro ao registrar:
- Campos: `student_id`, `arrival_time`, `reason` (opcional)
- `delay_date` é preenchido automaticamente com `date.today()` no router
- `expected_time` é fixo (07:30) no MVP — mude para buscado por turma depois

**`DelayApprove`** — usado pela coordenação:
- Campos: `rejection_reason` (opcional, usado só na rejeição)
- O novo `status` (APPROVED ou REJECTED) vem da URL (`/approve` ou `/reject`)
- `approved_by_id` preenchido automaticamente com `current_user.id` no router

**`DelayPublic`** — retorno da API:
- Todos os campos escalares, incluindo status e timestamps
- `model_config = ConfigDict(from_attributes=True)`

**`DelayList`** — wrapper de listagem:
- `delays: list[DelayPublic]`

---

### Passo 4 — Endpoints (`routers.py`)

Prefixo: `/delays`

#### `POST /delays` — Registrar atraso
- Permissão: `DELAYS_CREATE`
- Body: `DelayCreate`
- Lógica:
  1. Verifica se `student_id` existe e é `role=STUDENT`
  2. Impede registro duplicado no mesmo dia (mesmo `student_id + delay_date`)
  3. Calcula `delay_minutes = (arrival_time - expected_time).seconds // 60`
  4. Cria o registro com `status=PENDING` e `registered_by_id=current_user.id`
  5. (Placeholder) Notifica coordenação
- Retorna: `DelayPublic`

#### `GET /delays` — Listar todos
- Permissão: `DELAYS_VIEW_ALL`
- Query params opcionais: `status` (filtrar por status), `date` (filtrar por data)
- Retorna: `DelayList`

#### `GET /delays/pending` — Listar pendentes
- Permissão: `DELAYS_APPROVE`
- Atalho: filtra `status=PENDING` automaticamente
- Retorna: `DelayList`

#### `GET /delays/me` — Meus atrasos (aluno)
- Permissão: `DELAYS_VIEW_OWN`
- Filtra por `student_id=current_user.id`
- Retorna: `DelayList`

#### `GET /delays/{id}` — Detalhes
- Permissão: depende do contexto — veja lógica abaixo
- Lógica de verificação:
  - Aluno: só pode ver se `student_id == current_user.id`
  - Responsável: só pode ver se o aluno é filho dele (`guardian_student`)
  - Coordenador/Admin: pode ver qualquer um
- Retorna: `DelayPublic`

#### `PATCH /delays/{id}/approve` — Aprovar
- Permissão: `DELAYS_APPROVE`
- Lógica:
  1. Busca o delay — 404 se não existir
  2. Verifica que `status == PENDING` — 409 se já decidido
  3. Atualiza: `status=APPROVED`, `approved_by_id=current_user.id`
  4. (Placeholder) Notifica professor DT e responsável
- Retorna: `DelayPublic`

#### `PATCH /delays/{id}/reject` — Rejeitar
- Permissão: `DELAYS_APPROVE` (mesma permissão de aprovar)
- Body: `DelayApprove` (para receber `rejection_reason`)
- Lógica similar ao approve, mas: `status=REJECTED` + `rejection_reason`
- (Placeholder) Notifica responsável
- Retorna: `DelayPublic`

---

### Passo 5 — Registrar router no `app/main.py`

```python
from app.domains.delays import routers as delays_routers
app.include_router(delays_routers.router)
```

---

### Passo 6 — Atualizar `migrations/env.py`

Importe o model `Delay` para que o Alembic o detecte:
```python
from app.domains.delays.models import Delay  # noqa: F401
```

---

### Passo 7 — Gerar e aplicar migration

```bash
alembic revision --autogenerate -m "adicionar tabela delays"
alembic upgrade head
```

Verifique o arquivo gerado antes de aplicar.

---

### Passo 8 — Testes (`tests/test_delays.py`)

**Testes de permissões:**
- Porteiro pode registrar atraso
- Aluno não pode registrar atraso
- Coordenador pode aprovar/rejeitar
- Professor não pode aprovar/rejeitar
- Aluno só vê seus próprios atrasos

**Testes de fluxo:**
- Registro cria com `status=PENDING`
- Aprovação muda para `APPROVED` e preenche `approved_by_id`
- Rejeição muda para `REJECTED` e preenche `rejection_reason`
- Não pode aprovar/rejeitar um delay já decidido
- Cálculo de `delay_minutes` está correto

**Testes de validação:**
- Não pode registrar atraso para não-aluno
- Não pode registrar atraso duplicado no mesmo dia

---

## 💡 Simplificações para o MVP

1. **Horário fixo:** `expected_time = 07:30` (hardcoded) — depois evolui para horário por turma
2. **Notificações placeholder:** funções vazias que serão implementadas com e-mail/WhatsApp
3. **Sem reversão:** uma vez decidido (APPROVED/REJECTED), não pode mudar
4. **Sem histórico de decisões:** status simples sem auditoria de mudanças

---

## 🔄 Fluxo de Estados

```
[PENDING] ──approve──> [APPROVED]  (estado final)
    │
    └───reject───> [REJECTED]      (estado final)
```

Uma vez aprovado ou rejeitado, o status não pode ser alterado.

---

## 📱 Notificações (Placeholders)

Crie estas funções em `app/domains/delays/routers.py` ou em `app/shared/notifications/`:

```python
async def notify_delay_registered(delay_id: int) -> None:
    """TODO: Notificar coordenação sobre novo atraso pendente."""
    pass

async def notify_delay_approved(delay_id: int) -> None:
    """TODO: Notificar professor DT e responsável sobre aprovação."""
    pass

async def notify_delay_rejected(delay_id: int) -> None:
    """TODO: Notificar responsável sobre rejeição."""
    pass
```

A implementação real virá na feature de Notificações.
Consulte `plano/4-INTEGRACAO_WHATSAPP.md` para o plano completo.

---

## ✅ Checklist de Implementação

- [ ] Criar `app/domains/delays/__init__.py`
- [ ] Criar `app/domains/delays/models.py` (Delay + DelayStatus)
- [ ] Criar `app/domains/delays/schemas.py` (Create, Approve, Public, List)
- [ ] Criar `app/domains/delays/routers.py` (todos os endpoints)
- [ ] Registrar router em `app/main.py`
- [ ] Importar model em `migrations/env.py`
- [ ] Gerar e aplicar migration
- [ ] Criar `tests/test_delays.py`
- [ ] Testar fluxo completo (porteiro → coordenação → aluno)
