# 🕐 Feature: Delays (Atrasos) — Guia de Implementação

> Sistema de registro e aprovação de atrasos de alunos, envolvendo porteiro, coordenação, professor e notificação aos pais.

---

## 🎯 Objetivo

Registrar quando um aluno chega atrasado, controlar a aprovação da entrada, notificar as partes envolvidas e integrar com o registro de frequência do professor.

---

## 📊 Fluxo Completo

```
1. Aluno chega atrasado na escola
   ↓
2. PORTEIRO registra o atraso no sistema
   ↓
3. Sistema notifica COORDENAÇÃO
   ↓
4. COORDENAÇÃO aprova/rejeita a entrada
   ↓
   ├─ Se APROVADO:
   │   ├─ Sistema notifica PROFESSOR da turma
   │   ├─ Sistema notifica RESPONSÁVEL do aluno
   │   └─ Aluno pode entrar
   │
   └─ Se REJEITADO:
       ├─ Sistema notifica RESPONSÁVEL do aluno
       └─ Aluno não entra (volta pra casa)
```

---

## 🗂️ Modelo de Dados

### **Tabela: `delays`**

**Campos básicos:**
- `id` (PK)
- `student_id` (FK → users) — aluno que atrasou
- `registered_by_id` (FK → users) — quem registrou (porteiro)
- `approved_by_id` (FK → users, nullable) — coordenador que aprovou/rejeitou
- `delay_date` — data do atraso (YYYY-MM-DD)
- `arrival_time` — hora que o aluno chegou (HH:MM:SS)
- `expected_time` — hora esperada (HH:MM:SS) — pode vir de uma tabela de horários
- `delay_minutes` — diferença calculada automaticamente
- `status` — ENUM: `PENDING`, `APPROVED`, `REJECTED`
- `reason` — motivo do atraso (opcional, texto livre)
- `rejection_reason` — motivo da rejeição (se aplicável)
- `created_at`, `updated_at`

**Status possíveis:**
- `PENDING` — aguardando decisão da coordenação
- `APPROVED` — coordenação aprovou a entrada
- `REJECTED` — coordenação rejeitou (aluno não entra)

---

## 🔐 Permissões Necessárias (RBAC)

Você já definiu as permissões em `permissions.py`:

```python
DELAYS_CREATE       # Porteiro registra
DELAYS_APPROVE      # Coordenação aprova
DELAYS_REJECT       # Coordenação rejeita (pode ser mesma que APPROVE)
DELAYS_VIEW_ALL     # Coordenação/Admin vê todos
DELAYS_VIEW_OWN     # Aluno vê seus próprios
DELAYS_VIEW_CHILD   # Responsável vê do filho
```

**Mapeamento:**
- **Porteiro:** `DELAYS_CREATE`, `DELAYS_VIEW_ALL`
- **Coordenador:** `DELAYS_APPROVE`, `DELAYS_VIEW_ALL`
- **Aluno:** `DELAYS_VIEW_OWN`
- **Responsável:** `DELAYS_VIEW_CHILD`
- **Professor:** Pode ter `DELAYS_VIEW_OWN_CLASS` (ver da turma dele)

---

## 📋 Passo a Passo de Implementação

### **Fase 1: Modelo e Schemas**

#### **Passo 1.1: Criar estrutura**
```
app/domains/delays/
├── __init__.py
├── models.py
├── schemas.py
└── routers.py
```

#### **Passo 1.2: Criar Model (`models.py`)**
- Tabela `delays` com todos os campos listados acima
- FKs para `users` (student, registered_by, approved_by)
- Enum `DelayStatus` (PENDING, APPROVED, REJECTED)
- Usar `mapper_registry` compartilhado

#### **Passo 1.3: Criar Schemas (`schemas.py`)**

**Schemas necessários:**

1. **`DelayCreate`** — usado pelo porteiro ao registrar
   - Campos: `student_id`, `arrival_time`, `reason` (opcional)
   - `delay_date` pega data de hoje automaticamente
   - `expected_time` pode ser calculado ou fixo (ex: 7:30)

2. **`DelayUpdate`** — usado pela coordenação ao aprovar/rejeitar
   - Campos: `status`, `rejection_reason` (opcional)
   - `approved_by_id` preenchido automaticamente com usuário logado

3. **`DelayPublic`** — retorno da API
   - Todos os campos, incluindo IDs, status, timestamps
   - `model_config = ConfigDict(from_attributes=True)`

4. **`DelayList`** — wrapper de lista
   - `delays: list[DelayPublic]`

5. **`DelayWithDetails`** — versão expandida (opcional)
   - Inclui dados do aluno, porteiro, coordenador
   - Útil para frontend mostrar nomes ao invés de IDs

---

### **Fase 2: Endpoints**

#### **Passo 2.1: Criar routers (`routers.py`)**

Prefixo: `/delays`

**Endpoints:**

1. **`POST /delays`** — Registrar atraso (Porteiro)
   - Permissão: `DELAYS_CREATE`
   - Body: `DelayCreate`
   - Lógica:
     - Pega `student_id` do body
     - Pega `registered_by_id` do usuário logado
     - Define `status = PENDING`
     - Calcula `delay_minutes` (arrival_time - expected_time)
     - Salva no banco
     - **Notifica coordenação** (ver Fase 4)
   - Retorna: `DelayPublic`

2. **`GET /delays`** — Listar todos atrasos (Coordenação)
   - Permissão: `DELAYS_VIEW_ALL`
   - Query params: `status` (filtrar por pending/approved/rejected), `date` (filtrar por data)
   - Retorna: `DelayList`

3. **`GET /delays/pending`** — Atrasos aguardando aprovação
   - Permissão: `DELAYS_APPROVE`
   - Retorna apenas atrasos com `status = PENDING`
   - Útil para coordenação ver o que precisa decidir

4. **`GET /delays/me`** — Meus atrasos (Aluno)
   - Permissão: `DELAYS_VIEW_OWN`
   - Retorna atrasos onde `student_id = current_user.id`
   - Aluno vê apenas seus próprios atrasos

5. **`GET /delays/student/{student_id}`** — Atrasos de um aluno específico
   - Permissão: `DELAYS_VIEW_CHILD` ou `DELAYS_VIEW_ALL`
   - Verificação extra:
     - Se `GUARDIAN`, verifica se `student_id` é filho dele
     - Se `COORDINATOR/ADMIN`, pode ver qualquer aluno
   - Retorna: `DelayList`

6. **`PATCH /delays/{id}/approve`** — Aprovar atraso (Coordenação)
   - Permissão: `DELAYS_APPROVE`
   - Body vazio ou `{"reason": "Atestado válido"}`
   - Lógica:
     - Atualiza `status = APPROVED`
     - Preenche `approved_by_id = current_user.id`
     - Salva timestamp de aprovação
     - **Notifica professor da turma** (ver Fase 4)
     - **Notifica responsável** (ver Fase 4)
   - Retorna: `DelayPublic`

7. **`PATCH /delays/{id}/reject`** — Rejeitar atraso (Coordenação)
   - Permissão: `DELAYS_APPROVE`
   - Body: `{"rejection_reason": "Motivo não justifica"}`
   - Lógica similar ao approve, mas:
     - Atualiza `status = REJECTED`
     - Preenche `rejection_reason`
     - **Notifica responsável** sobre rejeição
   - Retorna: `DelayPublic`

8. **`GET /delays/{id}`** — Detalhes de um atraso específico
   - Permissão: depende do contexto (own/child/all)
   - Verificação:
     - Se aluno, só pode ver se for dele
     - Se responsável, só se for do filho
     - Se coordenador/admin, pode ver qualquer um
   - Retorna: `DelayWithDetails` (com nomes)

---

### **Fase 3: Lógica de Negócio**

#### **Passo 3.1: Calcular minutos de atraso**

No momento do registro (`POST /delays`):

```
delay_minutes = (arrival_time - expected_time).total_seconds() / 60
```

**De onde vem `expected_time`?**

**Opção A: Fixo no código (MVP simples)**
- Sempre 7:30 da manhã
- Hardcoded: `expected_time = time(7, 30, 0)`

**Opção B: Configurável por turma (melhor)**
- Tabela `class_schedules` com horário de cada turma
- Busca horário com base na turma do aluno
- Mais flexível, mas precisa de feature extra

**Recomendação para MVP:** Opção A (fixo). Depois evolui para B.

#### **Passo 3.2: Validações**

**No registro (porteiro):**
- Verifica se `student_id` existe e é aluno
- Verifica se `arrival_time` é realmente atrasado (> expected_time)
- Impede registro duplicado no mesmo dia

**Na aprovação/rejeição:**
- Verifica se atraso existe
- Verifica se ainda está `PENDING` (não pode mudar decisão depois)
- Apenas coordenador pode aprovar/rejeitar

#### **Passo 3.3: Notificações (Placeholder)**

Por enquanto, crie uma função placeholder:

```python
async def notify_delay_registered(delay_id: int):
    """TODO: Notificar coordenação sobre novo atraso"""
    pass

async def notify_delay_approved(delay_id: int):
    """TODO: Notificar professor e responsável"""
    pass

async def notify_delay_rejected(delay_id: int):
    """TODO: Notificar responsável"""
    pass
```

Essas funções serão implementadas na **Fase 4** (integração WhatsApp).

---

### **Fase 4: Integração com Horários de Aula (Opcional)**

**Pergunta:** *"Eu provavelmente precisaria dos horários de aulas, né?"*

**Resposta:** Depende do nível de automação que você quer.

#### **Cenário A: MVP sem horários (mais simples)**
- Horário fixo: `expected_time = 07:30`
- Todas as turmas entram no mesmo horário
- Funciona, mas limitado

#### **Cenário B: Com horários de aula (mais robusto)**
- Tabela `class_schedules`
- Cada turma tem seu horário de entrada
- Turmas podem ter horários diferentes
- Suporta turno integral, vespertino, etc.

**Recomendação:**
- **MVP inicial:** Cenário A (fixo)
- **Depois de validar:** Evoluir para Cenário B

Se você quiser fazer Cenário B logo, veja o arquivo `FEATURE_SCHEDULES.md` (vou criar separado).

---

## 🔄 Fluxo de Estados

```
[PENDING] ──approve──> [APPROVED]
    │
    └───reject───> [REJECTED]
```

**Regras:**
- Uma vez aprovado ou rejeitado, não pode mudar
- Coordenação deve tomar decisão rapidamente
- Sistema pode ter SLA (ex: decidir em 15 minutos)

---

## 📱 Notificações (Visão Geral)

**Quando notificar:**

1. **Atraso registrado** → Coordenação
   - "Novo atraso: João da Silva (3A) chegou às 08:15"

2. **Atraso aprovado** → Professor + Responsável
   - Para professor: "Atraso aprovado: João da Silva entrará na 2ª aula"
   - Para responsável: "Seu filho foi autorizado a entrar na escola"

3. **Atraso rejeitado** → Responsável
   - "Entrada não autorizada. Favor buscar seu filho na escola"

**Como notificar:**
- Ver arquivo `INTEGRACAO_WHATSAPP.md` (próximo)

---

## 🧪 Testes

Crie `tests/test_delays.py` com:

**Testes de permissões:**
- Porteiro pode registrar atraso
- Aluno não pode registrar atraso
- Coordenador pode aprovar/rejeitar
- Professor não pode aprovar/rejeitar
- Aluno só vê seus próprios atrasos
- Responsável só vê atrasos do filho

**Testes de fluxo:**
- Registrar atraso cria com status PENDING
- Aprovar atraso muda status para APPROVED
- Rejeitar atraso muda status para REJECTED
- Não pode aprovar atraso já aprovado/rejeitado
- Cálculo de delay_minutes está correto

**Testes de validação:**
- Não pode registrar atraso para não-aluno
- Não pode registrar atraso duplicado no mesmo dia
- arrival_time deve ser maior que expected_time

---

## 📂 Resumo dos Arquivos

| Ação      | Arquivo                              |
| --------- | ------------------------------------ |
| ✅ Criar  | `app/domains/delays/__init__.py`     |
| ✅ Criar  | `app/domains/delays/models.py`       |
| ✅ Criar  | `app/domains/delays/schemas.py`      |
| ✅ Criar  | `app/domains/delays/routers.py`      |
| ✅ Criar  | `tests/test_delays.py`               |
| ✏️ Editar | `app/app.py` (registrar router)      |
| ✏️ Editar | `migrations/env.py` (importar model) |
| ▶️ Gerar  | Migration com Alembic                |

---

## 🎯 Ordem de Implementação

1. ✅ **Occurrences** (você está fazendo)
2. 📋 **Delays - Fase 1 e 2** (modelo + endpoints básicos)
3. 🧪 **Delays - Testes**
4. 📱 **Notificações** (WhatsApp — próximo arquivo)
5. 🔄 **Delays - Fase 3** (notificações integradas)
6. 📅 **Horários de aula** (opcional, se precisar de flexibilidade)

---

## 💡 Simplificações para MVP

Para acelerar o desenvolvimento:

1. **Horário fixo:** Todos entram às 7:30
2. **Notificações simples:** Log no console ou e-mail (antes do WhatsApp)
3. **Sem histórico de decisões:** Coordenador decide uma vez, sem reversão
4. **Sem workflow complexo:** PENDING → APPROVED/REJECTED (fim)

Depois de validar com usuários reais, você adiciona:
- Horários por turma
- Notificações WhatsApp
- Histórico de mudanças
- Dashboard de atrasos (estatísticas)

---

## 📊 Dashboard Sugerido (Futuro)

Para coordenação:
- Atrasos pendentes hoje
- Total de atrasos por aluno (ranking)
- Taxa de aprovação/rejeição
- Alunos com mais de X atrasos no mês

---

## ✅ Checklist de Implementação

- [ ] Criar pasta `domains/delays/`
- [ ] Criar model `Delay` com todos os campos
- [ ] Criar schemas (Create, Update, Public, List)
- [ ] Criar enum `DelayStatus`
- [ ] Criar endpoint POST `/delays` (porteiro registra)
- [ ] Criar endpoint GET `/delays` (listar todos)
- [ ] Criar endpoint GET `/delays/pending` (pendentes)
- [ ] Criar endpoint GET `/delays/me` (meus atrasos)
- [ ] Criar endpoint PATCH `/delays/{id}/approve`
- [ ] Criar endpoint PATCH `/delays/{id}/reject`
- [ ] Criar endpoint GET `/delays/{id}` (detalhes)
- [ ] Registrar router no `app.py`
- [ ] Atualizar `migrations/env.py`
- [ ] Gerar e aplicar migration
- [ ] Escrever testes
- [ ] Testar fluxo completo com usuários de diferentes roles

---

## 🚀 Próximos Passos

Após concluir Delays:
1. Ver `INTEGRACAO_WHATSAPP.md` para notificações
2. (Opcional) Ver `FEATURE_SCHEDULES.md` para horários de aula
3. Testar com usuários reais (piloto)

---

**Dúvidas?** Revise cada passo antes de implementar. A feature de Delays é mais complexa que Occurrences porque envolve aprovação e notificações.
