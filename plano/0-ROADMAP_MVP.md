# 🎯 Roadmap do MVP — EduPBL

> Quando o sistema estará **funcional** e pronto para teste piloto com usuários reais?

---

## ✅ O QUE JÁ ESTÁ PRONTO

### 1. Infraestrutura (100%) ✅
- [x] Estrutura de pastas modular por domínio
- [x] FastAPI configurado com lifespan
- [x] PostgreSQL + SQLAlchemy async
- [x] Alembic (migrations)
- [x] Scripts de setup (`init_db.py`, `seed_db.py`)
- [x] Testes configurados (pytest)

### 2. Autenticação (100%) ✅
- [x] JWT com access token + refresh token
- [x] Login / Logout
- [x] Refresh token em cookie HttpOnly (path restrito)
- [x] `GET /auth/me` e `GET /auth/me/permissions`
- [x] Testes completos

### 3. Sistema RBAC (100%) ✅
- [x] 6 roles: STUDENT, GUARDIAN, TEACHER, COORDINATOR, PORTER, ADMIN
- [x] 30+ permissões mapeadas em `SystemPermissions`
- [x] Flag `is_tutor` para Professor Diretor de Turma
- [x] `PermissionChecker` e `role_required` como FastAPI dependencies
- [x] Helpers `get_user_permissions`, `user_has_permission`, etc.
- [x] Testes abrangentes

### 4. CRUD de Usuários (100%) ✅
- [x] Create, Read, Update, Delete
- [x] Listagem com paginação (offset/limit)
- [x] Troca de senha com confirmação da senha atual
- [x] Proteção por permissões
- [x] Testes completos

### 5. Ocorrências (100%) ✅
- [x] Model + Schemas + Routers
- [x] POST `/occurrences` (professor cria)
- [x] GET `/occurrences` (coordenação vê todas)
- [x] GET `/occurrences/me` (aluno/professor vê as suas)
- [x] GET `/occurrences/{id}` (detalhe)
- [x] PUT `/occurrences/{id}` (editar)
- [x] DELETE `/occurrences/{id}` (deletar)
- [x] Migration
- [x] Testes

---

## 🚧 O QUE FALTA PARA O MVP FUNCIONAL

### Feature 1: Dashboard por Permissões (Frontend) 🔜 PRÓXIMO

> Controle quais cards aparecem na `HomePage` com base nas permissões reais do
> usuário, obtidas de `GET /auth/me/permissions`. Consulte o guia completo em
> `plano/0-DASHBOARD-PERMISSOES-FRONTEND.md`.

**Escopo:**
- [ ] Criar `src/features/auth/models/Permissions.ts` (espelho do `SystemPermissions` do backend)
- [ ] Criar `src/features/auth/hooks/usePermissions.ts` (hook com `can` e `canAny`)
- [ ] Alterar `useLogout` para invalidar o cache de permissões
- [ ] Criar `src/features/dashboard/featureCards.tsx` (configuração declarativa dos cards)
- [ ] Alterar `HomePage` para filtrar cards com `canAny`
- [ ] Criar `src/routes/PermissionRoute.tsx` (guard de rota)
- [ ] Alterar `src/routes/index.tsx` para envolver rotas com `PermissionRoute`

**Tempo estimado:** 1 dia

---

### Feature 2: Horários (Schedules) 🔜

> **Por que horários antes dos atrasos?**
> O fluxo de atrasos precisa saber qual professor está dando aula *agora* para
> notificá-lo quando a entrada for aprovada. Sem horários no banco, isso é
> impossível sem hardcode. Consulte `plano/1-SCHEDULES.md` para o guia completo.

**Escopo mínimo:**
- [ ] Criar domínio `app/domains/schedules/`
- [ ] `periods.py` — constante `PERIODS` calculada automaticamente (50 min, com intervalos)
- [ ] Model `ScheduleSlot` (classroom + teacher + weekday + period + subject)
- [ ] Model `ScheduleOverride` (exceções pontuais: eventos, simulados)
- [ ] Helper `get_current_teacher(classroom_id, at)` — usado pelo fluxo de atrasos
- [ ] Endpoints CRUD de slots e overrides
- [ ] Permissões: `SCHEDULES_VIEW` e `SCHEDULES_MANAGE` (adicionar em `permissions.py`)
- [ ] Migration
- [ ] Testes

**Tempo estimado:** 2 dias

---

### Feature 3: Delays (Atrasos) 🔜

> Consulte `plano/2-FEATURE_DELAYS.md` para o guia detalhado de implementação.

**Escopo mínimo:**
- [ ] Criar domínio `app/domains/delays/`
- [ ] Model com status (PENDING, APPROVED, REJECTED)
- [ ] Endpoints:
  - [ ] `POST /delays` — porteiro registra atraso
  - [ ] `GET /delays` — coordenação vê todos os atrasos
  - [ ] `GET /delays/pending` — coordenação vê pendentes
  - [ ] `PATCH /delays/{id}/approve` — coordenação aprova
  - [ ] `PATCH /delays/{id}/reject` — coordenação rejeita
  - [ ] `GET /delays/me` — aluno vê seus próprios atrasos
- [ ] Migration
- [ ] Testes

**Tempo estimado:** 2 dias

---

### Feature 4: Notificações Básicas 📧

> Consulte `plano/4-INTEGRACAO_WHATSAPP.md` para o guia completo.

**Fluxo completo de notificações dos atrasos:**

```
Porteiro registra atraso
  → notifica COORDENAÇÃO (atraso pendente)

Coordenação aprova
  → notifica RESPONSÁVEL do aluno (entrada autorizada)
  → notifica PROFESSOR em aula agora via get_current_teacher() (aluno vai chegar)

Coordenação rejeita
  → notifica RESPONSÁVEL do aluno (entrada negada)
```

**Escopo:**
- [ ] Configurar SMTP nas settings
- [ ] `app/shared/notifications/email.py`
- [ ] Templates simples de e-mail (texto puro no MVP)
- [ ] Substituir os placeholders de notificação em `delays/routers.py`

**Tempo estimado:** 1–2 dias

---

### Feature 5: Importação de Usuários Reais 📋

> Consulte `plano/3-SEGURANCA_DADOS_REAIS.md` para o guia de segurança.

**Escopo:**
- [ ] `scripts/import_real_users.py`
- [ ] Lê CSVs de `data/` (professores, alunos, coordenadores)
- [ ] Valida dados e cria usuários no banco
- [ ] Gera senhas temporárias + seta `must_change_password=True`

**Tempo estimado:** 1 dia

---

## 🎯 Critério de "Sistema Funcional"

O sistema estará pronto para teste piloto quando este fluxo funcionar de ponta a ponta:

1. Coordenação cadastra os horários de cada turma
2. Porteiro faz login → vê apenas os cards relevantes (Atrasos) → registra atraso do João
3. Coordenação recebe notificação (e-mail) → aprova a entrada
4. Professor que está em aula agora recebe notificação → sabe que João vai chegar
5. Responsável do João recebe e-mail sobre o atraso aprovado
6. Professor faz login → registra ocorrência do João por comportamento
7. Responsável vê a ocorrência no sistema

---

## 📅 Cronograma Estimado (atualizado)

| Semana | Tarefas                                                | Status |
|--------|--------------------------------------------------------|--------|
| **1**  | ✅ Occurrences (concluído)                             | ✅     |
| **2**  | Dashboard por permissões (frontend) + Horários         | 🔜     |
| **3**  | Delays: model, endpoints, testes                       | 🔜     |
| **4**  | Notificações: e-mail + integração com delays           | 🔜     |
| **5**  | Importação de usuários reais + testes piloto           | 🔜     |
| **6+** | Feedback, ajustes, novas features                      | 🔜     |

**Total até MVP funcional:** ~3–4 semanas restantes

---

## 📊 Progresso Atual

```
████████████░░░░░░░░░░░░ 50% — MVP Funcional

✅ Infraestrutura
✅ Auth
✅ RBAC
✅ Users CRUD
✅ Occurrences
🔜 Dashboard por permissões (frontend)
🔜 Schedules (horários) — necessário para delays
🔜 Delays
🔜 Notificações básicas
🔜 Importação de usuários reais
```

---

## 🚀 Depois do MVP: Features Complementares

### Curto Prazo (1–2 meses)
- [ ] Tela de horários no frontend (usando `GET /schedules/classroom/{id}`)
- [ ] Atestados (aluno/responsável submete → DT valida → coordenação aprova)
- [ ] Notificações WhatsApp (migrar de e-mail)
- [ ] Dashboard com estatísticas básicas

### Médio Prazo (3–6 meses)
- [ ] Gerenciamento de espaços (biblioteca, auditório)
- [ ] Reserva de mídias (projetores, notebooks)
- [ ] Banco de questões e planos de aula
- [ ] Filtros avançados (datas, turmas, tipos)

### Longo Prazo (6+ meses)
- [ ] Sistema de sugestões com moderação
- [ ] Relatórios avançados (frequência, desempenho)
- [ ] App mobile (React Native)
- [ ] Integração com outros sistemas da escola

---

## 💡 Lembre-se

**Sistema funcional ≠ Sistema perfeito.**

Foco agora:
1. Dashboard por permissões (1 dia — já temos tudo no backend)
2. Horários (2 dias — desbloqueiam os delays)
3. Delays (2 dias)
4. Notificações (1–2 dias)
5. Importação de usuários reais (1 dia)
