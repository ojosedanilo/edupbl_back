# 🎯 Roadmap do MVP — EduPBL

> Quando o sistema estará **funcional** e pronto para teste piloto com usuários reais?

---

## ✅ **O QUE JÁ ESTÁ PRONTO**

### **1. Infraestrutura (100%)** ✅

- [X] Estrutura de pastas modular
- [X] FastAPI configurado
- [X] PostgreSQL + SQLAlchemy
- [X] Alembic (migrations)
- [X] Scripts de setup (`init_db.py`, `seed_db.py`)
- [X] Testes configurados (pytest)

### **2. Autenticação (100%)** ✅

- [X] JWT com access token + refresh token
- [X] Login/Logout
- [X] Refresh token em cookie HttpOnly
- [X] Endpoint `/auth/me`
- [X] Endpoint `/auth/me/permissions`
- [X] Testes completos

### **3. Sistema RBAC (100%)** ✅

- [X] 6 roles definidos (STUDENT, GUARDIAN, TEACHER, COORDINATOR, PORTER, ADMIN)
- [X] 30+ permissões mapeadas
- [X] Flag `is_tutor` para Professor DT
- [X] Decorators FastAPI prontos (`permission_required`, `role_required`)
- [X] Helpers de verificação (`user_has_permission`)
- [X] Testes abrangentes (501 linhas)

### **4. CRUD de Usuários (100%)** ✅

- [X] Create, Read, Update, Delete
- [X] Listagem com paginação
- [X] Proteção por permissões
- [X] Testes completos

---

## 🚧 **O QUE FALTA PARA O MVP FUNCIONAL**

### **Feature 1: Occurrences (Ocorrências)** ⏳ EM ANDAMENTO

**Status:** Você está implementando agora

**Escopo mínimo:**

- [X] Criar domínio `occurrences/`
- [ ] Model + Schemas + Routers
- [ ] Endpoints:
  - [ ] POST `/occurrences` (professor cria)
  - [ ] GET `/occurrences` (coordenação vê todas)
  - [ ] GET `/occurrences/me` (aluno/professor vê suas)
  - [ ] GET `/occurrences/{id}` (detalhes)
  - [ ] PUT `/occurrences/{id}` (editar)
  - [ ] DELETE `/occurrences/{id}` (deletar)
- [ ] Migration
- [ ] Testes
- [ ] (Opcional) Notificação por e-mail ao responsável

**Tempo estimado:** 1-2 dias

---

### **Feature 2: Delays (Atrasos)** 🔜 PRÓXIMO

**Escopo mínimo:**

- [ ] Criar domínio `delays/`
- [ ] Model com status (PENDING, APPROVED, REJECTED)
- [ ] Endpoints:
  - [ ] POST `/delays` (porteiro registra)
  - [ ] GET `/delays/pending` (coordenação vê pendentes)
  - [ ] PATCH `/delays/{id}/approve` (coordenação aprova)
  - [ ] PATCH `/delays/{id}/reject` (coordenação rejeita)
  - [ ] GET `/delays/me` (aluno vê seus atrasos)
- [ ] Horário fixo de entrada (7:30) — sem tabela de horários
- [ ] Migration
- [ ] Testes
- [ ] (Opcional) Notificação por e-mail

**Tempo estimado:** 2-3 dias

---

### **Feature 3: Importação de Usuários Reais** 📋 ESSENCIAL

**Escopo:**

- [ ] Criar `scripts/import_real_users.py`
- [ ] Ler CSVs de `data/` (professores, alunos, coordenadores)
- [ ] Validar dados
- [ ] Criar usuários no banco
- [ ] Gerar senhas temporárias
- [ ] (Opcional) Enviar e-mail com senha

**Tempo estimado:** 1 dia

---

### **Feature 4: Notificações Básicas** 📧 DESEJÁVEL

**Escopo mínimo (E-mail):**

- [ ] Configurar SMTP
- [ ] Criar `app/shared/notifications/email.py`
- [ ] Templates de e-mail simples
- [ ] Notificar responsável sobre ocorrência
- [ ] Notificar responsável sobre atraso aprovado/rejeitado
- [ ] Notificar coordenação sobre novo atraso

**Tempo estimado:** 1-2 dias

**Nota:** WhatsApp pode vir depois, e-mail já resolve para MVP

---

## 🎯 **DEFINIÇÃO DE "SISTEMA FUNCIONAL"**

O sistema estará **funcionalmente completo** para teste piloto quando tiver:

### **Funcionalidades Essenciais:**

1. ✅ Login de diferentes usuários (aluno, professor, coordenador, porteiro)
2. ✅ Permissões funcionando (cada um vê só o que pode)
3. ✅ Professor pode registrar ocorrências
4. ✅ Coordenação pode ver todas as ocorrências
5. ✅ Alunos/Responsáveis podem ver suas ocorrências
6. ✅ Porteiro pode registrar atrasos
7. ✅ Coordenação pode aprovar/rejeitar atrasos
8. ✅ Responsáveis são notificados (e-mail mínimo)

### **Usuários de Teste:**

- ✅ Admin
- ✅ Coordenador
- ✅ Professor
- ✅ Professor DT
- ✅ Porteiro
- ✅ Aluno
- ✅ Responsável

### **Dados Reais Importados:**

- ✅ Professores da escola
- ✅ Coordenadores
- ✅ Diretora
- ✅ Alunos das 2 turmas piloto
- ✅ Responsáveis vinculados aos alunos

---

## 📅 **CRONOGRAMA ESTIMADO**

| Semana       | Tarefas                                          | Status |
| ------------ | ------------------------------------------------ | ------ |
| **1**  | Occurrences (backend completo)                   | ⏳     |
| **2**  | Delays (backend completo)                        | 🔜     |
| **3**  | Importação de usuários reais + Notificações | 🔜     |
| **4**  | Testes, ajustes, deploy                          | 🔜     |
| **5**  | Teste piloto com 2 turmas                        | 🔜     |
| **6+** | Feedback, ajustes, novas features                | 🔜     |

**Total até MVP funcional:** ~3-4 semanas

---

## 🚀 **DEPOIS DO MVP: Features Complementares**

Após validar com usuários reais, você pode adicionar:

### **Curto Prazo (1-2 meses):**

- [ ] Atestados (aluno/responsável submete → DT valida → coordenação aprova)
- [ ] Notificações WhatsApp (migrar de e-mail)
- [ ] Dashboard com estatísticas
- [ ] Horários de aula (tabela `class_schedules`)
- [ ] Filtros avançados (datas, turmas, tipos)

### **Médio Prazo (3-6 meses):**

- [ ] Gerenciamento de espaços (biblioteca, auditório)
- [ ] Reserva de mídias (projetores, notebooks)
- [ ] Planos de aula para professores
- [ ] Banco de questões
- [ ] Gerador de atividades

### **Longo Prazo (6+ meses):**

- [ ] Projetos da escola (Revista Rabisco, Jornada Antirracista)
- [ ] Sistema de sugestões (com moderação por IA)
- [ ] Relatórios avançados (frequência, desempenho)
- [ ] Integração com outros sistemas da escola
- [ ] App mobile (React Native)

---

## 🎓 **RESPOSTA DIRETA: "O SISTEMA ESTÁ FUNCIONAL?"**

### **Status Atual:**

❌ **Não ainda** — Falta Occurrences + Delays + Usuários Reais

### **Quando estará funcional:**

✅ **Em ~3-4 semanas** se você seguir o cronograma acima

### **O que define "funcional":**

✅ Professor registra ocorrência → Responsável vê e é notificado
✅ Porteiro registra atraso → Coordenação aprova → Responsável é notificado
✅ Usuários reais conseguem fazer login e usar o sistema

**Após isso, o sistema está pronto para teste piloto!**

---

## 📊 **PROGRESSO ATUAL**

```
███████░░░░░░░░░░░░░░░░░ 30% — MVP Funcional

✅ Infraestrutura
✅ Auth
✅ RBAC
✅ Users CRUD
⏳ Occurrences (em andamento)
🔜 Delays
🔜 Import usuários reais
🔜 Notificações básicas
```

---

## 🎯 **FOCO TOTAL: MVP Mínimo Viável**

**Não adicione nada além de:**

1. Occurrences
2. Delays
3. Import de usuários
4. Notificações básicas (e-mail)

**Deixe para depois:**

- WhatsApp (use e-mail primeiro)
- Horários de aula (use horário fixo)
- Dashboard (use listagens simples)
- Atestados (segunda fase)
- Espaços/Mídias (segunda fase)

**Por quê?**

- Validar com usuários reais o mais rápido possível
- Descobrir o que realmente importa vs. o que é "nice to have"
- Evitar desperdício de tempo em features que ninguém vai usar

---

## 🔥 **PRIORIZAÇÃO: O QUE FAZER AGORA**

### **Esta semana:**

1. ✅ Terminar Occurrences (você está fazendo)
2. ✅ Testar Occurrences com usuários de teste
3. ✅ Corrigir bugs encontrados

### **Próxima semana:**

1. ✅ Implementar Delays
2. ✅ Testar Delays
3. ✅ Integrar notificações por e-mail

### **Terceira semana:**

1. ✅ Criar script de importação de usuários
2. ✅ Importar dados reais
3. ✅ Testar com dados reais internamente

### **Quarta semana:**

1. ✅ Deploy em servidor (Heroku, Railway, VPS)
2. ✅ Treinar equipe (coordenação, porteiro)
3. ✅ Iniciar teste piloto com 2 turmas

---

## 💡 **DICA FINAL**

**Sistema funcional ≠ Sistema perfeito**

Seu objetivo agora é:

- ✅ Resolver o problema real (ocorrências + atrasos)
- ✅ Funcionar bem o suficiente para teste
- ✅ Coletar feedback de usuários reais

**Depois** você melhora:

- Interface mais bonita
- WhatsApp ao invés de e-mail
- Dashboards com gráficos
- Features extras

**Lembre-se:** É melhor ter um sistema simples funcionando em 1 mês do que um sistema perfeito que nunca fica pronto.

---

## ✅ **PRÓXIMOS PASSOS IMEDIATOS**

1. **Termine Occurrences** (você está fazendo agora)
2. **Teste manualmente** com usuários fake
3. **Siga para Delays** (use o guia `FEATURE_DELAYS.md`)
4. **Crie script de importação** (use o guia `SEGURANCA_DADOS_REAIS.md`)
5. **Adicione notificações básicas** (use o guia `INTEGRACAO_WHATSAPP.md` — seção E-mail)

**Em 3-4 semanas você terá um MVP funcional rodando!** 🚀

---

## 📞 **QUANDO CONSIDERAR "FUNCIONAL"**

### **Critério de Aceitação:**

Faça o seguinte teste:

1. Professor faz login → Registra ocorrência do aluno João
2. Responsável do João faz login → Vê a ocorrência
3. Responsável recebe e-mail notificando
4. Porteiro faz login → Registra atraso do João
5. Coordenação faz login → Aprova o atraso
6. Professor faz login → Vê que João foi autorizado a entrar
7. Responsável recebe e-mail sobre o atraso

**Se esse fluxo funcionar de ponta a ponta = SISTEMA FUNCIONAL! ✅**

Aí você já pode começar o teste piloto com as 2 turmas reais.

---

**Boa sorte! Você está no caminho certo. Foco no MVP, valide com usuários, depois expande!** 🎯
