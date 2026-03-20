# 📱 Integração com WhatsApp — Guia Completo

> Como implementar notificações via WhatsApp para pais, professores e coordenação no sistema EduPBL.

---

## 🎯 Casos de Uso

**Notificações necessárias:**

1. **Ocorrências**
   - Notificar responsável quando professor registra ocorrência
   - "Seu filho João recebeu uma ocorrência disciplinar. Acesse o sistema para detalhes."

2. **Atrasos**
   - Notificar coordenação quando porteiro registra atraso
   - Notificar professor e responsável quando coordenação aprova entrada
   - Notificar responsável quando entrada é rejeitada

3. **Atestados** (futuro)
   - Notificar DT quando responsável envia atestado
   - Notificar coordenação após validação do DT
   - Notificar responsável sobre aprovação/rejeição

---

## ⚖️ Opções de Integração

### **Opção 1: WhatsApp Business API (Oficial)** ⭐ Recomendado

**Prós:**
- ✅ Oficial e estável
- ✅ Não vai ser banido
- ✅ Suporta templates aprovados
- ✅ Bom para produção

**Contras:**
- ❌ Precisa de conta Business verificada
- ❌ Templates precisam ser aprovados pelo WhatsApp (demora dias)
- ❌ Custo: ~R$ 0,10 por mensagem (conversação)
- ❌ Setup mais complexo

**Quando usar:** Produção, escola vai usar por tempo indeterminado

---

### **Opção 2: Twilio WhatsApp API** 🔶 Meio-termo

**Prós:**
- ✅ Mais fácil que API oficial
- ✅ Documentação excelente
- ✅ Suporte técnico
- ✅ Pode testar com sandbox grátis

**Contras:**
- ❌ Custo: ~R$ 0,20 por mensagem
- ❌ Templates precisam ser aprovados
- ❌ Precisa conta Twilio

**Quando usar:** MVP pagando, quer algo estável sem muito esforço

**Link:** https://www.twilio.com/whatsapp

---

### **Opção 3: Baileys (Não-oficial)** ⚠️ Arriscado

**Prós:**
- ✅ Grátis
- ✅ Não precisa aprovação de templates
- ✅ Rápido de implementar
- ✅ Simula WhatsApp Web

**Contras:**
- ❌ **Risco de ban** — WhatsApp pode bloquear o número
- ❌ Não oficial, pode parar de funcionar
- ❌ Precisa manter conexão sempre ativa
- ❌ Não recomendado para produção

**Quando usar:** Apenas testes/protótipo, **nunca** em produção

**Link:** https://github.com/WhiskeySockets/Baileys

---

### **Opção 4: E-mail** 📧 Alternativa Segura

**Prós:**
- ✅ Simples de implementar
- ✅ Grátis (ou muito barato)
- ✅ Sem risco de ban
- ✅ Todos têm e-mail institucional

**Contras:**
- ❌ Menos imediato que WhatsApp
- ❌ Pais podem não ver notificação rápido
- ❌ Taxa de abertura menor

**Quando usar:** Complemento ao WhatsApp, ou se WhatsApp não for viável agora

---

## 🎯 Recomendação por Cenário

### **Cenário A: MVP para teste piloto (2-3 meses)**
**Solução:** E-mail + WhatsApp manual
- Sistema envia e-mail automaticamente
- Coordenação envia WhatsApp manualmente (copiar mensagem do sistema)
- **Custo:** R$ 0
- **Risco:** Zero
- **Esforço:** Baixo

### **Cenário B: MVP com orçamento pequeno**
**Solução:** Twilio Sandbox
- Twilio oferece sandbox grátis para testes
- Mensagens reais para números autorizados
- Limitado, mas funciona
- **Custo:** R$ 0 (sandbox) ou ~R$ 50/mês (produção pequena)
- **Risco:** Baixo
- **Esforço:** Médio

### **Cenário C: Produção de longo prazo**
**Solução:** WhatsApp Business API oficial
- Conta verificada
- Templates aprovados
- Infraestrutura robusta
- **Custo:** ~R$ 200-500/mês (depende do volume)
- **Risco:** Zero
- **Esforço:** Alto (setup inicial)

---

## 📋 Implementação: E-mail (Solução Rápida)

### **Passo 1: Configurar SMTP**

Adicione no `settings.py`:

```python
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "edupbl@escola.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@edupbl.com")
```

### **Passo 2: Criar serviço de e-mail**

Crie `app/shared/email.py`:

**Funções principais:**
- `send_email(to, subject, body)`
- `send_occurrence_notification(occurrence_id)`
- `send_delay_notification(delay_id)`

### **Passo 3: Integrar nos endpoints**

Após criar ocorrência:
```python
await send_occurrence_notification(occurrence.id)
```

Após aprovar atraso:
```python
await send_delay_approved_notification(delay.id)
```

### **Passo 4: Templates de e-mail**

Crie templates em `app/shared/email_templates/`:
- `occurrence_created.html`
- `delay_approved.html`
- `delay_rejected.html`

---

## 📋 Implementação: Twilio WhatsApp

### **Passo 1: Criar conta Twilio**

1. Acesse https://www.twilio.com/try-twilio
2. Crie conta gratuita (trial)
3. Pegue `ACCOUNT_SID` e `AUTH_TOKEN`

### **Passo 2: Configurar WhatsApp Sandbox**

1. No dashboard, vá em **Messaging → Try it out → Send a WhatsApp message**
2. Adicione o número Twilio no WhatsApp
3. Envie a mensagem de join code
4. Autorize números de teste (até 5 no trial)

### **Passo 3: Instalar SDK**

```bash
uv add twilio
```

### **Passo 4: Adicionar ao settings**

```python
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
```

### **Passo 5: Criar serviço WhatsApp**

Crie `app/shared/whatsapp.py`:

**Funções principais:**
- `send_whatsapp(to, message)`
- `send_occurrence_whatsapp(occurrence_id)`
- `send_delay_whatsapp(delay_id)`

### **Passo 6: Usar nos endpoints**

Mesmo padrão do e-mail:
```python
await send_occurrence_whatsapp(occurrence.id)
```

### **Passo 7: Templates (Messages)**

Twilio sandbox não requer templates aprovados, mas precisa seguir formato:

```
🔔 EduPBL - Nova Ocorrência

Aluno: João Silva
Data: 20/03/2026
Tipo: Indisciplina

Acesse o sistema para mais detalhes:
https://edupbl.escola.com/occurrences/123
```

---

## 📋 Implementação: WhatsApp Business API (Oficial)

### **Passo 1: Requisitos**

- CNPJ da escola
- Número de telefone exclusivo para o sistema
- Conta Meta Business verificada
- Aguardar aprovação (pode levar semanas)

### **Passo 2: Criar templates**

Templates precisam ser aprovados pelo WhatsApp. Exemplo:

```
Nome: occurrence_created
Categoria: UTILITY
Idioma: pt_BR

Mensagem:
🔔 Nova ocorrência para {{1}}
Data: {{2}}
Acesse: {{3}}
```

Variáveis são substituídas dinamicamente.

### **Passo 3: Provider**

Escolha um provider oficial:
- **360Dialog** (recomendado)
- **MessageBird**
- **Infobip**

Todos cobram por mensagem (~R$ 0,10-0,20 cada).

### **Passo 4: Integração**

Cada provider tem SDK ou API REST. Consulte documentação específica.

---

## 📞 Obter Números de WhatsApp dos Responsáveis

### **Opção A: Cadastro manual**

Adicione campo `whatsapp_phone` na tabela `users`:

```python
whatsapp_phone: Mapped[str | None] = mapped_column(
    String(20), nullable=True
)
```

Responsáveis preenchem no primeiro acesso.

### **Opção B: Importar dos CSVs**

Se os CSVs já têm telefone dos pais:

```csv
aluno_nome,aluno_email,responsavel_telefone
João Silva,joao@escola.com,+5585999999999
```

Script de importação cria user e associa telefone.

### **Opção C: Assumir que e-mail = número**

Se a escola usar padrão como `responsavel.joao@escola.com`, você pode:
- Criar endpoint `/users/me/phone` onde responsável cadastra
- Sistema envia link por e-mail para cadastrar telefone
- Primeira notificação vai por e-mail, pede pra cadastrar WhatsApp

---

## 🔐 Segurança e Privacidade

### **LGPD:**

- ✅ Obtenha consentimento para enviar WhatsApp
- ✅ Permita opt-out (desativar notificações)
- ✅ Não compartilhe números com terceiros
- ✅ Armazene números criptografados (se possível)

### **Validação de números:**

Use biblioteca `phonenumbers`:
```bash
uv add phonenumbers
```

Valida e formata números internacionais corretamente.

---

## 🧪 Testes

### **Testes de unidade:**
- Mock da função de envio
- Verifica se foi chamada com parâmetros corretos
- Não envia mensagem real durante teste

### **Testes de integração:**
- Sandbox Twilio com números de teste
- Verifica se mensagem realmente chegou
- Valida formato e conteúdo

### **Testes manuais:**
- Crie atraso → verifica se coordenação recebeu
- Aprove atraso → verifica se professor e responsável receberam
- Rejeite atraso → verifica se responsável recebeu

---

## 📊 Monitoramento

### **Métricas importantes:**

- Taxa de entrega (delivered / sent)
- Taxa de erro (failed / sent)
- Tempo médio de entrega
- Custo mensal

### **Logs:**

Guarde no banco:
- `notifications` table
  - `id`
  - `type` (occurrence, delay, certificate)
  - `channel` (email, whatsapp, sms)
  - `recipient`
  - `status` (sent, delivered, failed)
  - `sent_at`
  - `delivered_at`
  - `error_message`

---

## 💰 Estimativa de Custos (WhatsApp)

### **Cenário: Escola com 500 alunos**

**Volume mensal estimado:**
- 50 ocorrências → 50 notificações
- 200 atrasos → 400 notificações (aprovado/rejeitado)
- **Total:** ~450 mensagens/mês

**Custo com Twilio:**
- 450 × R$ 0,20 = **R$ 90/mês**

**Custo com WhatsApp Business API:**
- 450 × R$ 0,10 = **R$ 45/mês**

**Custo com E-mail:**
- Grátis ou R$ 10/mês (se usar serviço como SendGrid)

---

## 🎯 Roadmap de Notificações

### **MVP (Fase 1):** E-mail
- Rápido de implementar
- Sem custo
- Funciona para validar sistema

### **Fase 2:** Twilio Sandbox
- WhatsApp para equipe interna (professores, coordenação)
- E-mail para pais (ou WhatsApp manual)

### **Fase 3:** Twilio Produção
- WhatsApp automatizado para todos
- Templates customizados
- Monitoramento de entregas

### **Fase 4:** WhatsApp Business API
- Conta oficial verificada
- Templates aprovados pelo WhatsApp
- Custos otimizados para grande escala

---

## 📂 Estrutura de Código

```
app/shared/
├── notifications/
│   ├── __init__.py
│   ├── email.py           # Serviço de e-mail
│   ├── whatsapp.py        # Serviço WhatsApp (Twilio)
│   ├── templates/         # Templates de mensagem
│   │   ├── occurrence_created.py
│   │   ├── delay_approved.py
│   │   └── delay_rejected.py
│   └── models.py          # Model Notification (log)
```

---

## ✅ Checklist de Implementação

**E-mail (MVP):**
- [ ] Configurar SMTP no settings
- [ ] Criar `app/shared/notifications/email.py`
- [ ] Criar templates de e-mail
- [ ] Integrar em endpoints de occurrences
- [ ] Integrar em endpoints de delays
- [ ] Testar envio real

**WhatsApp (Twilio):**
- [ ] Criar conta Twilio
- [ ] Configurar sandbox
- [ ] Instalar SDK
- [ ] Criar `app/shared/notifications/whatsapp.py`
- [ ] Criar templates de mensagem
- [ ] Adicionar campo `whatsapp_phone` em users
- [ ] Testar com números autorizados
- [ ] (Opcional) Criar tabela `notifications` para logs

---

## 🚀 Próximos Passos

1. **Comece com e-mail** — mais simples, valida o fluxo
2. **Teste com usuários reais** — eles preferem WhatsApp ou e-mail?
3. **Se aceitarem pagar** → migre para Twilio
4. **Se sistema crescer muito** → migre para WhatsApp Business API oficial

---

## 💡 Dica Final

**Não implemente WhatsApp logo no início!**

Motivos:
- Setup complexo
- Custo (mesmo que baixo)
- Risco de ser bloqueado (se usar Baileys)
- E-mail já resolve 80% do problema

Comece simples, valide com usuários, depois adicione WhatsApp se for realmente necessário.

**Lembre-se:** Sistema funcional é melhor que sistema perfeito que nunca sai do papel!
