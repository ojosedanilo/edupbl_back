# Implementação da Feature de Ocorrências — Back-End

> Guia de tarefas sem código. Cada item descreve **o que** fazer e **por quê**.

---

## Passo 1 — Criar a estrutura de pastas do domínio

Crie a pasta `app/domains/occurrences/` com um arquivo `__init__.py` vazio dentro. Isso transforma a pasta em um módulo Python e mantém a consistência com os outros domínios do projeto (`users`, `auth`).

---

## Passo 2 — Criar o Model

Crie o arquivo `models.py` dentro do novo domínio. O model representa a tabela `occurrences` no banco de dados e deve conter:

- **Chave primária** `id`
- **FK para `users`** referenciando quem *criou* a ocorrência (professor/coordenador) — se o usuário for deletado, o campo vira `NULL`
- **FK para `users`** referenciando o *aluno* sobre quem é a ocorrência — se o aluno for deletado, a ocorrência é deletada junto (`CASCADE`)
- **`title`** — título curto da ocorrência
- **`description`** — descrição detalhada
- **`created_at` e `updated_at`** — gerados automaticamente pelo banco, seguindo o padrão dos outros models

Use o mesmo `table_registry` já existente em `users/models.py` para que o Alembic enxergue todas as tabelas de um lugar só.

---

## Passo 3 — Criar os Schemas

Crie o arquivo `schemas.py`. Os schemas definem o contrato da API — o que ela aceita e o que ela retorna. Você precisará de quatro:

- **`OccurrenceCreate`** — campos obrigatórios para criar: `student_id`, `title` e `description`
- **`OccurrenceUpdate`** — mesmos campos de conteúdo, mas todos opcionais (para permitir atualização parcial)
- **`OccurrencePublic`** — o que a API devolve: todos os campos, incluindo `id`, `created_by_id` e os timestamps. Precisa de `model_config = ConfigDict(from_attributes=True)` para funcionar com o SQLAlchemy
- **`OccurrenceList`** — wrapper com uma lista de `OccurrencePublic`, seguindo o padrão do `UserList`

---

## Passo 4 — Criar os Endpoints

Crie o arquivo `routers.py` com prefixo `/occurrences`. Implemente os seguintes endpoints:

### `POST /occurrences`
Cria uma nova ocorrência. O `created_by_id` deve ser preenchido automaticamente com o `id` do usuário logado — nunca vindo do corpo da requisição. Requer a permissão `OCCURRENCES_CREATE`.

### `GET /occurrences`
Lista todas as ocorrências do sistema. Requer a permissão `OCCURRENCES_VIEW_ALL` (apenas coordenadores e admins).

### `GET /occurrences/me`
Lista as ocorrências do usuário logado. O comportamento varia pela role:
- **Aluno:** ocorrências em que ele é o aluno envolvido
- **Professor:** ocorrências que ele criou

Requer a permissão `OCCURRENCES_VIEW_OWN`.

### `GET /occurrences/{id}`
Retorna uma ocorrência específica. Requer `OCCURRENCES_VIEW_OWN`, mas com uma verificação extra: se o usuário for aluno, ele só pode ver ocorrências sobre si mesmo — caso contrário, retorna `403 Forbidden`.

### `PUT /occurrences/{id}`
Atualiza uma ocorrência existente. Requer `OCCURRENCES_EDIT`. Professores só podem editar ocorrências que eles próprios criaram; coordenadores e admins podem editar qualquer uma. Retorna `404` se não encontrar e `403` se não tiver permissão sobre aquela ocorrência específica.

### `DELETE /occurrences/{id}`
Deleta uma ocorrência. Requer `OCCURRENCES_DELETE`. Mesma regra do `PUT`: professor só deleta as próprias. Retorna `404` se não encontrar.

---

## Passo 5 — Registrar o router em `app.py`

Importe o router de ocorrências e registre-o com `app.include_router(...)`, assim como já foi feito com `users` e `auth`.

---

## Passo 6 — Atualizar o `migrations/env.py`

Importe o model `Occurrence` no arquivo `env.py` do Alembic, junto aos outros imports de models. Sem isso, o Alembic não detecta a nova tabela na hora de gerar a migration.

---

## Passo 7 — Gerar e aplicar a migration

Execute os dois comandos do Alembic: primeiro para gerar o arquivo de migration com `--autogenerate` e depois para aplicá-lo com `upgrade head`. Antes de aplicar, abra o arquivo gerado em `migrations/versions/` e confirme que ele está criando a tabela `occurrences` com todas as colunas e FKs esperadas.

---

## Resumo dos arquivos

| Ação | Arquivo |
|------|---------|
| ✅ Criar | `app/domains/occurrences/__init__.py` |
| ✅ Criar | `app/domains/occurrences/models.py` |
| ✅ Criar | `app/domains/occurrences/schemas.py` |
| ✅ Criar | `app/domains/occurrences/routers.py` |
| ✏️ Editar | `app/app.py` |
| ✏️ Editar | `migrations/env.py` |
| ▶️ Executar | `alembic revision --autogenerate` + `upgrade head` |
