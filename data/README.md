# 📂 Pasta de Dados

> Esta pasta contém os CSVs com dados reais da escola.  
> **NUNCA commite esses arquivos no Git!**

---

## 📁 Estrutura

```
data/
├── usuarios/          # CSVs de usuários (professores, alunos, etc.)
│   ├── admins.csv
│   ├── coordenadores.csv
│   ├── professores.csv
│   ├── professores_dt.csv
│   ├── alunos.csv
│   ├── porteiros.csv
│   └── responsaveis.csv
│
└── horarios/          # CSVs de grade horária (um por turma)
    ├── horario_sala_1.csv   →  1º ano A
    ├── horario_sala_2.csv   →  1º ano B
    ├── ...
    └── horario_sala_12.csv  →  3º ano D
```

---

## 🔒 Segurança

### ✅ O QUE ESTÁ NO GIT:
- `.gitkeep` — mantém as subpastas no repositório
- `*.example` — exemplos de formato (sem dados reais)
- `README.md` — este arquivo

### ❌ O QUE NUNCA DEVE IR PRO GIT:
- `*.csv` — CSVs com dados reais (ignorados pelo `.gitignore`)
- Qualquer arquivo com nomes, e-mails ou senhas reais

---

## 📋 Formato dos CSVs de Usuários

Todos os CSVs de `usuarios/` seguem o mesmo formato base:

```csv
nome,sobrenome,email,senha,role
```

**Colunas:**
- `nome` — Primeiro nome do usuário
- `sobrenome` — Sobrenome do usuário
- `email` — E-mail institucional (único)
- `senha` — Senha temporária inicial
- `role` — (Opcional) Role do usuário: `student`, `teacher`, `coordinator`, `porter`, `guardian`, `admin`

**Coluna extra para alunos e professores DT:**
- `sala` — Número da sala de 1 a 12 (ver tabela abaixo)

### 🏫 Mapeamento de Salas

| Número | Nome |
|--------|------|
| 1 | 1º ano A |
| 2 | 1º ano B |
| 3 | 1º ano C |
| 4 | 1º ano D |
| 5 | 2º ano A |
| 6 | 2º ano B |
| 7 | 2º ano C |
| 8 | 2º ano D |
| 9 | 3º ano A |
| 10 | 3º ano B |
| 11 | 3º ano C |
| 12 | 3º ano D |

### 📁 Arquivos de Usuários

| Arquivo | Role Padrão | is_tutor | Descrição |
|---------|-------------|----------|-----------|
| `admins.csv` | `admin` | `false` | Administradores do sistema (devs) |
| `coordenadores.csv` | `coordinator` | `false` | Coordenadores/Diretoria |
| `professores.csv` | `teacher` | `false` | Professores normais |
| `professores_dt.csv` | `teacher` | `true` | Professores Diretores de Turma |
| `alunos.csv` | `student` | `false` | Alunos das turmas |
| `porteiros.csv` | `porter` | `false` | Porteiros/Seguranças |
| `responsaveis.csv` | `guardian` | `false` | Pais/Responsáveis |

---

## 📅 Formato dos CSVs de Horário

Cada arquivo em `horarios/` representa a grade semanal de uma turma:

```csv
email_professor,dia_semana,numero_periodo,tipo,titulo
```

**Colunas:**

| Coluna | Obrigatório | Descrição |
|--------|-------------|-----------|
| `email_professor` | Só para `class_period` | E-mail do professor. Vazio para folga/planejamento/intervalos. |
| `dia_semana` | Sim | 2=segunda, 3=terça, 4=quarta, 5=quinta, 6=sexta |
| `numero_periodo` | Não | Número da aula (1–9). Vazio para intervalos e folgas. |
| `tipo` | Sim | Ver tabela abaixo |
| `titulo` | Não | Texto exibido. Se vazio, usa o padrão do tipo. |

**Tipos disponíveis:**

| Tipo | Significado | Professor? |
|------|-------------|------------|
| `class_period` | Aula normal | ✅ obrigatório |
| `planning` | Horário de planejamento (fora da sala) | opcional |
| `free` | Turno de folga (fora da escola) | vazio |
| `snack_break` | Intervalo de lanche | vazio |
| `lunch_break` | Intervalo de almoço | vazio |

---

## ▶️ Como Usar

### 1. Preparar CSVs

```bash
# Crie os CSVs nas subpastas corretas:
data/usuarios/professores.csv
data/usuarios/alunos.csv
data/horarios/horario_sala_1.csv
# etc.
```

### 2. Importar Usuários

```bash
cd backend
uv run python scripts/seed_db.py --real
```

### 3. Importar Horários

```bash
# Os professores devem estar no banco antes!
uv run python scripts/seed_db.py --schedules
```

### 4. Ambos de uma vez

```bash
uv run python scripts/seed_db.py --real --schedules
```

O script mostrará quantos registros foram criados, ignorados ou com erro.

---

## 🔐 Sobre Senhas Temporárias

Todos os usuários importados via CSV são criados com `must_change_password=True`.
O front-end redireciona automaticamente para troca de senha no primeiro login.
Endpoint: `PATCH /users/me/password`

---

## 🧪 Modo de Desenvolvimento

Para desenvolvimento/testes, use usuários fake (sem CSVs):

```bash
uv run python scripts/seed_db.py
```

Isso cria 7 usuários de teste sem precisar de nenhum CSV.
