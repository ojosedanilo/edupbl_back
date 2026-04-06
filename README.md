# EduPBL — Backend

## 🧠 Tecnologias

- **Python** → linguagem ensinada no curso + rápida prototipação
- **uv** → gerenciador de pacotes e ambientes virtuais
- **FastAPI** → API
- **Pydantic** → schemas/contratos
- **SQLAlchemy 2.0** → ORM de banco de dados
- **PostgreSQL** → banco de dados
- **Alembic** → migrations
- **Taskipy** → atalhos de tarefas (lint, format, run, test)

## 🧩 Camadas

|           Coluna 1           |
| :--------------------------: |
| React + TS + Tailwind + MUI |
|              ↓              |
| TanStack Query (HTTP State) |
|              ↓              |
| FastAPI (Rules / Validation) |
|              ↓              |
|   SQLAlchemy (Persistence)   |
|              ↓              |
|          PostgreSQL          |

## 📁 Estrutura

```
backend/
├── app/
│   ├── core/         → configurações (settings)
│   ├── domains/      → domínios da aplicação (users, auth, schedules…)
│   └── shared/       → utilitários compartilhados (db, rbac, schemas)
├── migrations/       → migrations Alembic
├── scripts/          → scripts auxiliares (seed, reset)
├── data/             → arquivos de dados (fotos, horários CSV)
├── docker-compose.yml
├── pyproject.toml
└── alembic.ini
```

## 📋 Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) (para o PostgreSQL)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (gerenciador de pacotes Python)

## 🚀 Setup

### 1. Copiar e configurar variáveis de ambiente

```bash
cp .env.example .env
# Edite o .env com suas credenciais, se necessário
```

### 2. Subir o banco de dados via Docker

```bash
docker compose up -d
```

> O Docker Compose sobe um container PostgreSQL já com o banco criado (via `POSTGRES_DB` no `.env`).

### 3. Criar ambiente virtual e instalar dependências

```bash
uv sync
```

> O `uv sync` cria o `.venv` automaticamente e instala todas as dependências do `pyproject.toml` (incluindo as de dev).

### 4. Ativar o ambiente virtual

```bash
# Linux/macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 5. Rodar as migrations

```bash
alembic upgrade head
```

### 6. Popular o banco com dados de teste

```bash
python scripts/seed_db.py
```

### 7. Iniciar o servidor

```bash
task run
```

> Equivalente a `fastapi dev app/main.py`.

---

## 🛠️ Comandos úteis (Taskipy)

| Comando          | Descrição                              |
|------------------|----------------------------------------|
| `task run`       | Inicia o servidor em modo dev          |
| `task lint`      | Verifica estilo com Ruff               |
| `task format`    | Formata o código com Ruff              |
| `task test`      | Roda os testes em paralelo             |
| `task test_all`  | Testes + relatório de cobertura        |
| `task coverage`  | Relatório de cobertura resumido        |

---

## ⚠️ Solução de problemas

### Erro: `type "userrole" already exists`

Esse erro ocorre ao rodar `alembic upgrade head` em um banco que já foi inicializado com o script `init_db.py` legado (que criava o ENUM manualmente). O fluxo correto **não usa mais** o `init_db.py` — o ENUM é criado pela própria migration inicial.

Para resolver, recrie o banco do zero:

```bash
docker compose down -v   # remove o container E o volume de dados
docker compose up -d     # sobe novamente com banco limpo
alembic upgrade head
python scripts/seed_db.py
```

### Resetar o banco (desenvolvimento)

```bash
python scripts/reset_db.py
alembic upgrade head
python scripts/seed_db.py
```
