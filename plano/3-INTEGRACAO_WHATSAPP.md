# Notificações — Guia Completo (E-mail e WhatsApp)

> Como implementar notificações para pais, professores e coordenação no EduPBL.

---

## Casos de uso

### Ocorrências
- Responsável é notificado quando professor registra uma ocorrência sobre o filho

### Atrasos
- Coordenação é notificada quando porteiro registra um atraso (pendente)
- Professor DT e responsável são notificados quando coordenação aprova a entrada
- Responsável é notificado quando entrada é rejeitada

### Atestados (futuro)
- Professor DT é notificado quando responsável envia atestado
- Coordenação é notificada após validação do DT
- Responsável é notificado sobre aprovação ou rejeição

---

## Opções de canal

### Opção 1 — E-mail ✅ Recomendado para o MVP

**Prós:** Simples de implementar, sem custo, sem risco de bloqueio, sem aprovação de templates, todos os usuários já têm e-mail institucional.

**Contras:** Menos imediato que WhatsApp; pais podem não ver rápido.

**Quando usar:** MVP e teste piloto. Depois que o fluxo estiver validado, migra para WhatsApp.

---

### Opção 2 — Twilio WhatsApp

**Prós:** Mais fácil que a API oficial, boa documentação, sandbox gratuita para testes.

**Contras:** Custo por mensagem (~R$ 0,20), templates precisam ser aprovados para produção.

**Quando usar:** Depois do MVP, quando houver orçamento e o sistema estiver validado.

**Link:** https://www.twilio.com/whatsapp

---

### Opção 3 — WhatsApp Business API (Oficial)

**Prós:** Canal oficial, estável, ideal para longo prazo.

**Contras:** Precisa de conta Business verificada e CNPJ, templates precisam de aprovação do WhatsApp (pode levar semanas), custo (~R$ 0,10/mensagem), setup complexo.

**Quando usar:** Produção de longo prazo, após validar com usuários reais.

---

### Opção 4 — Baileys (Não-oficial) ⚠️

**Prós:** Grátis, sem aprovação de templates.

**Contras:** Risco real de ban do número, não é oficial, pode parar de funcionar a qualquer momento.

**Nunca usar em produção.** Apenas para prototipagem pessoal e descartável.

---

## Roadmap de notificações

### Fase 1 — MVP: E-mail
Implementação simples, sem custo, valida o fluxo de notificação.

### Fase 2 — Twilio Sandbox
WhatsApp para equipe interna (professores, coordenação) enquanto e-mail cobre os pais.

### Fase 3 — Twilio Produção
WhatsApp automatizado para todos, com templates customizados e monitoramento de entrega.

### Fase 4 — WhatsApp Business API
Conta oficial verificada, templates aprovados, custos otimizados para grande escala.

---

## Implementação: E-mail (Fase 1)

### Estrutura de arquivos

```
app/shared/notifications/
├── __init__.py
├── email.py           ← Serviço de envio de e-mail
└── templates/
    ├── occurrence_created.txt
    ├── delay_registered.txt
    ├── delay_approved.txt
    └── delay_rejected.txt
```

### Passo 1 — Configurar SMTP nas settings

Adicione em `app/core/settings.py` as variáveis: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM`. Todas lidas do `.env` — nunca hardcoded. O arquivo `.env.example` já deve documentar essas variáveis.

**Provedor sugerido para a escola:** Gmail com uma conta dedicada (ex: `edupbl.notificacoes@gmail.com`) e App Password gerada nas configurações de segurança do Google. Simples e gratuito para o volume do MVP.

### Passo 2 — Criar `email.py`

O módulo deve ter:
- Uma função genérica de baixo nível que recebe destinatário, assunto e corpo e faz o envio via SMTP
- Funções de alto nível específicas para cada evento: `send_occurrence_notification(occurrence_id, db)`, `send_delay_registered_notification(delay_id, db)`, `send_delay_approved_notification(delay_id, db)`, `send_delay_rejected_notification(delay_id, db)`
- As funções de alto nível buscam os dados necessários no banco (nome do aluno, e-mail do responsável, etc.) e montam a mensagem antes de chamar a função genérica

### Passo 3 — Templates de mensagem

Use arquivos de texto simples em `templates/`. Sem HTML no MVP — texto puro é suficiente e mais fácil de manter. Cada template define assunto e corpo com marcadores que a função substitui pelos valores reais (ex: `{aluno_nome}`, `{data}`, `{link}`).

### Passo 4 — Integrar nos routers

Nos routers de occurrences e delays, substitua as chamadas aos placeholders de notificação pelas funções reais do módulo `email.py`. As funções são assíncronas — use `await`.

### Passo 5 — Tratar erros de envio

Erros de e-mail não devem cancelar a operação principal. Envolva a chamada de notificação em `try/except` e registre o erro em log, sem relançar a exceção. O atraso foi aprovado — isso não deve ser desfeito por falha no e-mail.

---

## Implementação: Twilio WhatsApp (Fase 2)

### Pré-requisitos

1. Criar conta em https://www.twilio.com/try-twilio
2. Anotar `ACCOUNT_SID` e `AUTH_TOKEN`
3. No dashboard: ir em Messaging → Try it out → Send a WhatsApp message
4. Configurar o Sandbox: adicionar o número Twilio no WhatsApp pessoal e enviar o código de join
5. Autorizar os números de teste que vão receber mensagens (até 5 no trial)

### Configuração

Adicione em `settings.py` as variáveis: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` e `TWILIO_WHATSAPP_FROM`. Lidas do `.env`.

Instale o SDK com `uv add twilio`.

### Estrutura

Crie `app/shared/notifications/whatsapp.py` com o mesmo padrão do `email.py`: uma função genérica de baixo nível e funções específicas por evento.

### Templates de mensagem

O sandbox do Twilio não exige templates aprovados. Use mensagens diretas com os dados do evento. Para produção, crie templates na plataforma Twilio e aguarde aprovação antes de ativar.

---

## Obtendo os números de WhatsApp dos responsáveis

### Opção A — Cadastro no primeiro acesso (recomendada)

Adicione o campo `whatsapp_phone` (nullable) na tabela `users`. Após o primeiro login, o sistema exibe um formulário pedindo o número. O responsável preenche voluntariamente — em linha com a LGPD.

### Opção B — Importar dos CSVs

Se os CSVs já tiverem o telefone dos responsáveis, inclua o campo `responsavel_telefone` no CSV de alunos ou em um CSV separado de responsáveis, e o script de importação o associa ao usuário.

### Opção C — Notificação progressiva

Primeira notificação vai por e-mail com um link para o responsável cadastrar o número de WhatsApp. A partir da segunda notificação, usa WhatsApp se o número estiver cadastrado.

---

## Modelo de log de notificações (futuro)

Para monitorar entregas e diagnosticar falhas, crie uma tabela `notifications` com os campos: `id`, `type` (occurrence/delay/certificate), `channel` (email/whatsapp), `recipient`, `status` (sent/delivered/failed), `sent_at`, `delivered_at`, `error_message`.

Isso não é necessário no MVP — adicione quando o volume de notificações justificar o monitoramento.

---

## Estimativa de custos (WhatsApp)

Para uma escola com 500 alunos, estimativa de volume mensal:
- 50 ocorrências → 50 notificações
- 200 atrasos → ~400 notificações (registro + aprovação/rejeição)
- **Total: ~450 mensagens/mês**

| Canal                    | Custo estimado/mês |
|--------------------------|--------------------|
| E-mail (Gmail)           | Grátis             |
| Twilio WhatsApp          | ~R$ 90             |
| WhatsApp Business API    | ~R$ 45             |

---

## Segurança e LGPD

- Obtenha consentimento explícito antes de enviar mensagens WhatsApp
- Ofereça opt-out (o usuário deve poder desativar notificações)
- Não compartilhe números com terceiros
- Armazene números no banco como dado pessoal sensível — documentado na política de privacidade da escola

---

## Checklist de Implementação

**E-mail (MVP):**
- [ ] Configurar variáveis SMTP no `.env` e no `.env.example`
- [ ] Criar `app/shared/notifications/email.py`
- [ ] Criar templates de texto em `templates/`
- [ ] Substituir placeholders em `occurrences/routers.py`
- [ ] Substituir placeholders em `delays/notifications.py`
- [ ] Tratar erros de envio com try/except + log
- [ ] Testar envio real com conta de teste

**WhatsApp — Twilio (Fase 2):**
- [ ] Criar conta Twilio e configurar sandbox
- [ ] Adicionar variáveis Twilio no `.env`
- [ ] Instalar SDK (`uv add twilio`)
- [ ] Adicionar campo `whatsapp_phone` no model `User`
- [ ] Criar migration para o novo campo
- [ ] Criar `app/shared/notifications/whatsapp.py`
- [ ] Criar tela/endpoint para o responsável cadastrar o número
- [ ] Substituir chamadas de e-mail por WhatsApp (ou paralelizar os dois)
- [ ] Testar com números autorizados no sandbox
