# 🎯 Roadmap do MVP — EduPBL

> Quando o sistema estará **funcional** e pronto para teste piloto com usuários reais?

---

## ✅ O que já está pronto

### 1. Infraestrutura (100%)
- [x] Estrutura de pastas modular por domínio
- [x] FastAPI configurado com lifespan
- [x] PostgreSQL + SQLAlchemy async
- [x] Alembic (migrations)
- [x] Scripts de setup (`init_db.py`, `seed_db.py`)
- [x] Testes configurados (pytest)

### 2. Autenticação (100%)
- [x] JWT com access token + refresh token
- [x] Login / Logout
- [x] Refresh token em cookie HttpOnly (path restrito)
- [x] `GET /auth/me` e `GET /auth/me/permissions`
- [x] Testes completos

### 3. Sistema RBAC (100%)
- [x] 6 roles: STUDENT, GUARDIAN, TEACHER, COORDINATOR, PORTER, ADMIN
- [x] 30+ permissões mapeadas em `SystemPermissions`
- [x] Flag `is_tutor` para Professor Diretor de Turma
- [x] `PermissionChecker` e `role_required` como FastAPI dependencies
- [x] Helpers `get_user_permissions`, `user_has_permission`, etc.
- [x] Testes abrangentes
- [x] `OCCURRENCES_VIEW_OWN_CLASSROOM` e `USER_EDIT_OWN_CLASSROOM` adicionadas ao DT

### 4. CRUD de Usuários (100%)
- [x] Create, Read, Update, Delete
- [x] Listagem com paginação (offset/limit)
- [x] Troca de senha com confirmação da senha atual
- [x] Proteção por permissões
- [x] Testes completos
- [x] Upload de avatar (WebP 256×256, máx 2 MB) — próprio usuário e DT para alunos da turma
- [x] Campo `phone` (opcional) para notificações WhatsApp/SMS

### 5. Ocorrências — Backend (100%)
- [x] Model + Schemas + Routers
- [x] Todos os endpoints CRUD
- [x] Regras de acesso por role (professor só edita as próprias, coordenador vê todas)
- [x] Migration e testes completos

---

## 🚧 O que falta para o MVP funcional

### Feature 1: Dashboard por Permissões (Frontend) 🔜 PRÓXIMO

O backend já expõe `GET /auth/me/permissions`. O frontend precisa consumir esse dado para decidir quais cards aparecem na `HomePage` e quais rotas são acessíveis, em vez de usar a `role` diretamente.

**O que fazer:**
- Criar o tipo `Permissions` no frontend espelhando o `SystemPermissions` do backend
- Criar um hook `usePermissions` que lê as permissões do usuário logado e expõe helpers como `can(permission)` e `canAny(permissions[])`
- Atualizar o `useLogout` para invalidar o cache de permissões ao deslogar
- Criar uma configuração declarativa dos cards da `HomePage` onde cada card define de qual permissão depende
- Criar um guard de rota `PermissionRoute` que redireciona o usuário caso não tenha permissão para a rota
- Atualizar `src/routes/index.tsx` para usar `PermissionRoute` nas rotas protegidas

**Por que fazer isso:**
Usar a `role` diretamente no frontend é frágil — qualquer mudança no RBAC do backend exigiria alterar o frontend também. Com as permissões vindas da API, o frontend se adapta automaticamente a qualquer ajuste de permissão feito no backend.

**Tempo estimado:** 1 dia

---

### Feature 2: Horários (Schedules) 🔜

O fluxo de atrasos precisa identificar qual professor está em aula *agora* para notificá-lo quando uma entrada for aprovada. Sem uma tabela de horários no banco, isso não é possível de forma dinâmica.

**O que fazer:**
- Criar o domínio `app/domains/schedules/` com model, schemas, routers e um módulo de lógica de períodos
- Implementar a grade semanal fixa por turma (`schedule_slots`: turma + professor + dia da semana + período + disciplina)
- Implementar exceções pontuais (`schedule_overrides`: data específica + turmas afetadas + horário modificado — para eventos, simulados, feriados)
- Implementar o helper `get_current_teacher(classroom_id, at)` que recebe um horário e retorna qual professor está em aula naquele momento — este helper é chamado pelo fluxo de atrasos
- Adicionar as permissões `SCHEDULES_VIEW` e `SCHEDULES_MANAGE` em `permissions.py` e mapear nos roles correspondentes
- Criar endpoints CRUD para slots e overrides, e um endpoint de leitura que retorna o professor atual de uma turma

**Por que fazer isso antes dos atrasos:**
O helper `get_current_teacher` é o ponto central que conecta a aprovação de um atraso à notificação do professor. Sem ele, o fluxo de notificação fica incompleto ou depende de dado hardcoded.

**Consulte `1-SCHEDULES.md` para os detalhes completos.**

**Tempo estimado:** 2 dias

---

### Feature 3: Delays (Atrasos) 🔜

**O que fazer:**
- Criar o domínio `app/domains/delays/` com model, schemas e routers
- O model precisa de um Enum de status (PENDING / APPROVED / REJECTED) e campos para registrar quem criou, quem decidiu, horário de chegada, horário esperado, minutos de atraso, motivo e motivo da rejeição
- Implementar os endpoints de registro (porteiro), listagem (coordenação/aluno/responsável), aprovação e rejeição
- As funções de notificação devem existir como placeholders desde o início — elas serão preenchidas na feature de notificações

**Por que fazer isso:**
É a segunda feature de maior valor para os usuários reais da escola. Porteiro e coordenação dependem disso no dia a dia.

**Consulte `4-FEATURE_DELAYS.md` para os detalhes completos.**

**Tempo estimado:** 2 dias

---

### Feature 4: Notificações Básicas 📧

**O que fazer:**
- Configurar SMTP nas settings (host, porta, usuário, senha)
- Criar `app/shared/notifications/email.py` com funções de envio
- Criar templates simples de texto para cada evento (nova ocorrência, atraso aprovado, atraso rejeitado)
- Substituir os placeholders de notificação nos routers de ocorrências e atrasos pelas chamadas reais

**Fluxo completo de notificações para atrasos:**
- Porteiro registra → coordenação recebe e-mail (atraso pendente)
- Coordenação aprova → responsável recebe (entrada autorizada) + professor em aula agora recebe (via `get_current_teacher`)
- Coordenação rejeita → responsável recebe (entrada negada)

**Por que e-mail primeiro:**
E-mail não depende de aprovação de templates nem de conta Business, pode ser configurado em minutos e é suficiente para validar o fluxo durante o piloto.

**Consulte `5-INTEGRACAO_WHATSAPP.md` para a estratégia de notificações incluindo o caminho para WhatsApp.**

**Tempo estimado:** 1–2 dias

---

### Feature 5: Importação de Usuários Reais 📋

**O que fazer:**
- Colocar os CSVs dos usuários reais na pasta `data/` (que está no `.gitignore`)
- Executar o script `scripts/seed_db.py` — a função `seed_real_users` já está implementada e lê os arquivos da pasta `data/`
- Verificar os dados criados no banco e corrigir eventuais erros de importação
- Testar login com alguns usuários reais antes do piloto

**Por que só na hora do piloto:**
Dados reais nunca devem circular fora do servidor de produção. Durante o desenvolvimento, os usuários de teste (`seed_test_users`) são suficientes.

**Consulte `3-SEGURANCA_DADOS_REAIS.md` para as regras de segurança e o formato esperado dos CSVs.**

**Tempo estimado:** 1 dia

---

## 🎯 Critério de "Sistema Funcional"

O MVP estará pronto para teste piloto quando este fluxo funcionar de ponta a ponta:

1. Coordenação cadastra os horários de cada turma
2. Porteiro faz login → vê apenas os cards relevantes → registra atraso do João
3. Coordenação recebe notificação → aprova a entrada
4. Professor que está em aula agora recebe notificação e sabe que João vai chegar
5. Responsável do João recebe e-mail sobre o atraso aprovado
6. Professor faz login → registra ocorrência do João
7. Responsável vê a ocorrência no sistema

---

## 📅 Cronograma Estimado

| Semana | Tarefas                                              | Status |
| ------ | ---------------------------------------------------- | ------ |
| **1**  | Dashboard por permissões (frontend) + Horários       | 🔜     |
| **2**  | Delays: model, endpoints, testes                     | 🔜     |
| **3**  | Notificações por e-mail + integração com delays      | 🔜     |
| **4**  | Importação de usuários reais + testes piloto         | 🔜     |

**Total até MVP funcional:** ~3–4 semanas

---

## 📊 Progresso Atual

```
████████████░░░░░░░░░░░░ 50% — MVP Funcional

✅ Infraestrutura
✅ Auth
✅ RBAC
✅ Users CRUD
✅ Occurrences (backend)
🔜 Dashboard por permissões (frontend)
🔜 Schedules (necessário para os delays)
🔜 Delays
🔜 Notificações
🔜 Importação de usuários reais
```

---

## 🚀 Depois do MVP: Features Complementares

### Curto Prazo (1–2 meses)
- [ ] Tela de horários no frontend
- [ ] Atestados (aluno/responsável submete → DT valida → coordenação aprova)
- [ ] Notificações WhatsApp (migrar de e-mail) — campo `phone` já existe no model `User`
- [ ] Dashboard com estatísticas básicas de ocorrências e atrasos

### Médio Prazo (3–6 meses)
- [ ] Gerenciamento de espaços (biblioteca, auditório)
- [ ] Filtros avançados (por data, turma, tipo)
- [ ] Relatórios de frequência e desempenho

### Longo Prazo (6+ meses)
- [ ] Sistema de sugestões com moderação
- [ ] App mobile (React Native)
- [ ] Integração com outros sistemas da escola
