Deixa eu ler o projeto primeiro para entender o contexto antes de escrever qualquer plano.Tenho tudo que preciso. O plano atual menciona Twilio, mas você quer Neonize. Deixa eu entender o que é Neonize antes de escrever o novo plano:Tenho tudo que preciso. Agora vou escrever o plano atualizado:O plano é um documento para você ler e implementar no seu ritmo, então vou entregar como Markdown direto no chat — sem necessidade de arquivo extra.

---

# Plano: Notificações por E-mail e WhatsApp (Neonize)

---

## Contexto e ponto de partida

O backend já tem os ganchos no lugar certo. Os três placeholders em `app/domains/delays/notifications.py` (`notify_delay_registered`, `notify_delay_approved`, `notify_delay_rejected`) já são chamados nos routers de delays. Ocorrências ainda não têm placeholder — precisa ser adicionado. O campo `phone` já existe no model `User`. O que falta é preencher esses placeholders com lógica real.

A estratégia é: **e-mail primeiro, WhatsApp em paralelo com fallback**. Se o destinatário tem `phone` cadastrado, manda WhatsApp. Se não tem, manda e-mail. Os dois canais usam a mesma interface — o router nunca sabe qual canal está sendo usado.

---

## Fase 1 — Infraestrutura compartilhada

### Passo 1 — Estrutura de arquivos

Crie a seguinte hierarquia dentro de `app/shared/notifications/`:

```
app/shared/notifications/
├── __init__.py
├── dispatcher.py       ← ponto de entrada único (decide e-mail vs WhatsApp)
├── email.py            ← envio via SMTP
├── whatsapp.py         ← envio via Neonize
└── templates/
    ├── delay_registered.txt
    ├── delay_approved.txt
    ├── delay_rejected.txt
    └── occurrence_created.txt
```

O `dispatcher.py` é a peça central: ele recebe os dados de quem notificar e decide qual canal usar. Os routers e o `delays/notifications.py` só importam do `dispatcher` — nunca de `email.py` ou `whatsapp.py` diretamente.

### Passo 2 — Variáveis de ambiente

Adicione em `settings.py` dois blocos novos de configuração, lidos do `.env`:

**Bloco SMTP:**
`SMTP_HOST`, `SMTP_PORT` (int, default 587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (endereço remetente, ex: `edupbl.notificacoes@gmail.com`), `SMTP_ENABLED` (bool, default False para não explodir em dev sem configurar).

**Bloco WhatsApp/Neonize:**
`WHATSAPP_ENABLED` (bool, default False), `WHATSAPP_DB_PATH` (caminho do arquivo SQLite que o Neonize usa para persistir a sessão, ex: `data/whatsapp_session.db`), `WHATSAPP_DEVICE_NAME` (nome que aparece no WhatsApp ao conectar, ex: `EduPBL`).

Documente todos no `.env.example` com valores de exemplo e comentários explicando cada um.

### Passo 3 — Templates de mensagem

Cada template é um arquivo `.txt` com marcadores `{campo}`. Defina um formato fixo para cada template: primeira linha é o assunto (para e-mail), linha em branco, depois o corpo. As funções de notificação lerão esses arquivos e farão `.format(**dados)` antes de enviar.

Campos sugeridos por template:

- `delay_registered.txt`: `{aluno_nome}`, `{turma}`, `{horario_chegada}`, `{horario_esperado}`, `{minutos_atraso}`, `{motivo}`, `{registrado_por}`
- `delay_approved.txt`: `{aluno_nome}`, `{turma}`, `{data}`, `{aprovado_por}`
- `delay_rejected.txt`: `{aluno_nome}`, `{turma}`, `{data}`, `{motivo_rejeicao}`
- `occurrence_created.txt`: `{aluno_nome}`, `{titulo}`, `{descricao}`, `{data}`, `{registrado_por}`

---

## Fase 2 — Canal de e-mail

### Passo 4 — Criar `email.py`

O módulo tem duas camadas:

**Camada baixa:** uma função assíncrona `send_email(to: str, subject: str, body: str) -> None` que abre conexão SMTP com `aiosmtplib` (a versão async do smtplib — instale com `uv add aiosmtplib`), autentica com `SMTP_USER`/`SMTP_PASSWORD` e envia. Se `SMTP_ENABLED` for False, loga a mensagem e retorna sem enviar — útil para desenvolvimento.

**Camada alta:** funções específicas por evento que recebem o `delay_id` ou `occurrence_id` e uma sessão do banco, buscam os dados necessários (nome do aluno, e-mail dos destinatários, campos do evento), renderizam o template e chamam `send_email`. Cada função sabe quem deve receber: a de `delay_registered` notifica a coordenação, a de `delay_approved` notifica o responsável e o professor DT, a de `delay_rejected` notifica o responsável, a de `occurrence_created` notifica o responsável.

Para buscar o professor DT de uma turma, use o helper `get_current_teacher` que já existe em `schedules`. Para buscar os responsáveis de um aluno, use o relacionamento `student.guardians` do model `User` — já existe como `relationship` many-to-many via `guardian_student`.

### Passo 5 — Tratamento de erros

Todo envio de notificação deve ser envolvido em `try/except` com log de erro. A notificação é secundária — uma falha no envio não deve reverter a transação principal nem retornar erro HTTP para o cliente. Use o módulo `logging` padrão do Python, não `print`.

---

## Fase 3 — Canal WhatsApp com Neonize

Neonize é construído sobre Whatsmeow (Go) e usa uma conexão real de WhatsApp — não a API Business oficial, não Twilio. Funciona como um cliente WhatsApp normal conectado via QR code. Tem suporte a `asyncio` via `neonize.aioze`.

**Importante antes de começar:** Neonize usa um número de WhatsApp real. Recomendado usar um número dedicado para a escola (chip separado), não o número pessoal. O risco de ban existe, mas é baixo para envio de mensagens transacionais de baixo volume.

### Passo 6 — Instalar e entender o ciclo de vida do Neonize

Instale com `uv add neonize`.

O Neonize não é stateless como uma chamada HTTP — ele mantém uma conexão persistente com os servidores do WhatsApp. Precisa ser inicializado uma vez no boot da aplicação e permanecer conectado enquanto a aplicação roda. O client usa um arquivo de banco de dados local (configurado em `WHATSAPP_DB_PATH`) para persistir a sessão entre reinicializações — depois do primeiro QR code, não precisa escanear de novo.

### Passo 7 — Integrar o Neonize no lifespan do FastAPI

No `app/main.py`, no bloco `lifespan`, inicialize o client do Neonize se `WHATSAPP_ENABLED` for True. O client deve ser armazenado em uma variável de estado da aplicação (`app.state.whatsapp_client`) para que os módulos de notificação possam acessá-lo depois.

O fluxo de inicialização é: criar o `NewAClient` com o nome do dispositivo e o caminho do banco de dados, registrar um handler para o evento de QR code (que loga o QR no terminal para o operador escanear), registrar um handler para o evento de conexão estabelecida, e chamar `client.connect()` em uma task assíncrona separada (não `await` direto — isso bloquearia o boot). No encerramento (após o `yield`), desconecte o client.

Na primeira inicialização, o QR code vai aparecer no log do servidor — o operador escaneia com o WhatsApp do número dedicado da escola. Nas próximas inicializações, a sessão já está salva no banco e conecta automaticamente.

### Passo 8 — Criar `whatsapp.py`

Mesma estrutura do `email.py`: uma função de baixo nível `send_whatsapp(phone: str, message: str) -> None` que recebe o número no formato E.164 (ex: `5585999990000`), usa `build_jid(phone)` do Neonize para construir o JID do destinatário, e chama `client.send_message(jid, text=message)`.

Para acessar o client global, importe `app.state.whatsapp_client` — mas atenção ao ciclo de vida: valide que o client está conectado antes de tentar enviar. Se não estiver conectado, logue um aviso e retorne sem erro.

Funções de alto nível com mesma assinatura das do `email.py`, mas montando a mensagem em formato adequado para WhatsApp (texto corrido, sem assunto, pode usar emojis para deixar a mensagem mais clara).

### Passo 9 — Formatar números de telefone

O campo `phone` no banco é livre (String 20). Antes de usar no Neonize, normalize o número: remova caracteres não numéricos, garanta que começa com o DDI do país (55 para Brasil). Crie uma função utilitária `normalize_phone(phone: str) -> str | None` em `app/shared/text_utils.py` (arquivo já existe) que faz essa normalização e retorna `None` se o número for inválido.

Use `client.is_on_whatsapp([phone])` antes de enviar para verificar se o número está cadastrado no WhatsApp — evita falhas silenciosas quando o número existe mas não tem WhatsApp.

---

## Fase 4 — Dispatcher e integração

### Passo 10 — Criar `dispatcher.py`

Este é o módulo que os routers chamam. Ele exporta as mesmas funções de alto nível: `notify_delay_registered`, `notify_delay_approved`, `notify_delay_rejected`, `notify_occurrence_created`.

A lógica interna de cada função é: buscar os destinatários e seus dados, para cada destinatário verificar se tem `phone` — se sim, tentar WhatsApp (se `WHATSAPP_ENABLED`); se não tem `phone` ou WhatsApp falhar, tentar e-mail (se `SMTP_ENABLED`). Cada envio individual em `try/except` com log, sem propagar erros.

### Passo 11 — Substituir os placeholders em `delays/notifications.py`

Importe as funções do `dispatcher` e substitua os `pass` pelas chamadas reais. As funções do dispatcher precisam de acesso ao banco para buscar os dados — passe a sessão como parâmetro. Isso significa mudar a assinatura de `notify_delay_registered(delay_id: int)` para `notify_delay_registered(delay_id: int, session: AsyncSession)`, e ajustar as chamadas nos routers de delays de acordo.

### Passo 12 — Adicionar placeholder de notificação em `occurrences/routers.py`

Siga o mesmo padrão de `delays/routers.py`: crie `app/domains/occurrences/notifications.py` com `notify_occurrence_created(occurrence_id: int, session: AsyncSession)`, importe no router e chame após o `session.commit()` da criação de ocorrência.

---

## Fase 5 — Testes

### Passo 13 — Testes unitários dos módulos de notificação

Para `email.py`: mock do `aiosmtplib` e verifique que `send_email` é chamado com os parâmetros corretos; teste que erros de SMTP são capturados e logados sem propagar; teste que `SMTP_ENABLED=False` retorna sem chamar o SMTP.

Para `whatsapp.py`: mock do `NewAClient` e verifique a chamada a `send_message`; teste a função `normalize_phone` com casos de borda (número com parênteses, traço, espaço, DDI ausente, DDI duplicado).

Para `dispatcher.py`: teste que destinatário com `phone` usa WhatsApp, destinatário sem `phone` usa e-mail, e que falha no WhatsApp faz fallback para e-mail.

### Passo 14 — Testes de integração nos routers existentes

Os testes de delays já existem em `test_delays.py`. Adicione mocks para as funções do dispatcher nos testes de criação, aprovação e rejeição, verificando que o dispatcher é chamado com o `delay_id` correto. Não teste o envio real nos testes de integração — apenas que o dispatcher foi invocado.

---

## Checklist de implementação

**Infraestrutura:**

- [X] Criar `app/shared/notifications/` com `__init__.py`
- [X] Adicionar variáveis SMTP e WhatsApp em `settings.py` e `.env.example`
- [ ] Criar os 4 templates de texto em `notifications/templates/`

**E-mail:**

- [ ] Instalar `aiosmtplib` com `uv add aiosmtplib`
- [ ] Criar `email.py` com camada baixa e camada alta
- [ ] Testar envio real com conta Gmail de teste + App Password

**WhatsApp (Neonize):**

- [ ] Instalar `neonize` com `uv add neonize`
- [ ] Adicionar inicialização do client no `lifespan` do `main.py`
- [ ] Criar `whatsapp.py` com camada baixa e camada alta
- [ ] Adicionar `normalize_phone` em `text_utils.py`
- [ ] Testar conexão via QR code com número dedicado
- [ ] Testar envio com número autorizado

**Integração:**

- [ ] Criar `dispatcher.py` com lógica de fallback
- [ ] Atualizar assinaturas em `delays/notifications.py` para receber `session`
- [ ] Ajustar chamadas nos routers de delays
- [ ] Criar `occurrences/notifications.py` e plugar no router
- [ ] Adicionar testes unitários e mocks nos testes de integração existentes

---

## Decisão de design que vale registrar

O Neonize usa uma conexão persistente (não stateless), o que é uma diferença fundamental em relação ao Twilio. Isso significa que o servidor precisa estar rodando para que o WhatsApp funcione — não dá para enviar uma mensagem em um job isolado sem que o client esteja conectado. Se no futuro o backend rodar em múltiplas instâncias (horizontal scaling), o client do Neonize precisa estar em apenas uma delas, ou você move o canal de WhatsApp para um serviço separado. Para o volume atual da escola, uma única instância é mais do que suficiente — vale documentar essa limitação no `README` do backend.
