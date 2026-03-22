# EduPBL

## 🧠 Tecnologias do Back-End

- **Python** -> linguagem ensinada no curso + rápida prototipação
- **uv** -> gerenciador de pacotes
- **FastAPI** -> API
- **Pydantic** -> schemas/contratos
- **SQLAlchemy 2.0** -> ORM de banco de dados
- **PostgreSQL** -> banco de dados

## 🧩 Camadas

|           Coluna 1           |
| :--------------------------: |
|    React + TS + Tailwind    |
|              ↓              |
| TanStack Query (HTTP State) |
|              ↓              |
| FastAPI (Rules / Validation) |
|              ↓              |
|   SQLAlchemy (Persistence)   |
|              ↓              |
|          PostgreSQL          |

## 📁 Estrutura geral do repositório

```

```

## 📦 Instalação

## 🚀 Setup do Backend

### 1. Criar banco de dados no Docker

```bash
cd backend
docker compose up -d
```

### 2. Inicializar banco de dados

```bash
uv run python scripts/init_db.py
```

### 3. Gerar migration inicial (primeira vez)

```bash
alembic revision --autogenerate -m "create initial tables"
```

### 4. Rodar migrations

```bash
alembic upgrade head
```

### 5. Popular com dados de teste

```bash
uv run python scripts/seed_db.py
```

### 6. Rodar servidor

```bash
uv run fastapi dev app/app.py
```
