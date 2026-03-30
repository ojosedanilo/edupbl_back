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

### Feature 1: Delays (Atrasos) 🔜 PRÓXIMO

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
- [ ] Consulte `plano/3-FEATURE_DELAYS.md` para o guia completo

**Tempo estimado:** 2–3 dias

---

### Feature 2: Importação de Usuários Reais 📋 ESSENCIAL

**Escopo:**
- [ ] `scripts/import_real_users.py`
- [ ] Lê CSVs de `data/` (professores, alunos, coordenadores)
- [ ] Valida dados e cria usuários no banco
- [ ] Gera senhas temporárias + seta `must_change_password=True`
- [ ] Consulte `plano/2-SEGURANCA_DADOS_REAIS.md` para o guia

**Tempo estimado:** 1 dia

---

### Feature 3: Notificações Básicas 📧 DESEJÁVEL

**Escopo mínimo (e-mail):**
- [ ] Configurar SMTP nas settings
- [ ] `app/shared/notifications/email.py`
- [ ] Templates simples de e-mail
- [ ] Notificar responsável ao criar ocorrência
- [ ] Notificar responsável e professor ao aprovar/rejeitar atraso
- [ ] Notificar coordenação sobre novo atraso pendente

**Nota:** WhatsApp pode vir depois — e-mail já resolve para MVP.
**Consulte:** `plano/4-INTEGRACAO_WHATSAPP.md` (seção E-mail)

**Tempo estimado:** 1–2 dias

---

## 🎯 Critério de "Sistema Funcional"

O sistema estará pronto para teste piloto quando este fluxo funcionar de ponta a ponta:

1. Professor faz login → registra ocorrência do aluno João
2. Responsável do João faz login → vê a ocorrência
3. Responsável recebe e-mail de notificação
4. Porteiro faz login → registra atraso do João
5. Coordenação faz login → aprova o atraso
6. Professor vê que João foi autorizado a entrar
7. Responsável recebe e-mail sobre o atraso

---

## 📅 Cronograma Estimado

| Semana | Tarefas                                        | Status |
|--------|------------------------------------------------|--------|
| **1**  | ✅ Occurrences (concluído)                     | ✅     |
| **2**  | Delays (backend completo + testes)             | 🔜     |
| **3**  | Importação de usuários reais + Notificações    | 🔜     |
| **4**  | Testes, ajustes, deploy                        | 🔜     |
| **5**  | Teste piloto com 2 turmas                      | 🔜     |
| **6+** | Feedback, ajustes, novas features              | 🔜     |

**Total até MVP funcional:** ~2–3 semanas restantes

---

## 📊 Progresso Atual

```
████████████░░░░░░░░░░░░ 50% — MVP Funcional

✅ Infraestrutura
✅ Auth
✅ RBAC
✅ Users CRUD
✅ Occurrences
🔜 Delays
🔜 Importação de usuários reais
🔜 Notificações básicas
```

---

## 🚀 Depois do MVP: Features Complementares

### Curto Prazo (1–2 meses)
- [ ] Atestados (aluno/responsável submete → DT valida → coordenação aprova)
- [ ] Notificações WhatsApp (migrar de e-mail)
- [ ] Dashboard com estatísticas básicas
- [ ] Filtros avançados (datas, turmas, tipos)

### Médio Prazo (3–6 meses)
- [ ] Gerenciamento de espaços (biblioteca, auditório)
- [ ] Reserva de mídias (projetores, notebooks)
- [ ] Horários de aula (tabela `class_schedules`)
- [ ] Banco de questões e planos de aula

### Longo Prazo (6+ meses)
- [ ] Sistema de sugestões com moderação
- [ ] Relatórios avançados (frequência, desempenho)
- [ ] App mobile (React Native)
- [ ] Integração com outros sistemas da escola

---

## 💡 Lembre-se

**Sistema funcional ≠ Sistema perfeito.**

Foco agora:
1. ✅ Delays
2. ✅ Importação de usuários
3. ✅ Notificações básicas (e-mail)

Deixe para depois: WhatsApp, dashboards, horários, atestados, espaços.
