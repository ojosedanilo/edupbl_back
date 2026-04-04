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
├── fotos/       # Fotos originais fornecidas por você para o seed
│   └── foto.jpg       # Ex: referenciado como "foto.jpg" na coluna avatar do CSV
│
├── avatars/           # ⚙️ Gerado automaticamente em runtime — NÃO editar
│   └── {user_id}.webp # Criado pelo seed ou pelo endpoint PATCH /users/me/avatar
│
└── horarios/          # CSVs de grade horária (um por turma)
    ├── horario_sala_1.csv   →  1º ano A
    └── horario_sala_12.csv  →  3º ano D
```

---

## 🖼️ Separação de diretórios de imagens

| Diretório          | O que guarda                        | Quem gerencia   | No Git? |
|--------------------|-------------------------------------|-----------------|---------|
| `data/fotos/`| Fotos originais que você fornece    | Você manualmente | ❌ Nunca |
| `data/avatars/`    | Avatares processados (256×256 WebP) | Sistema (runtime)| ❌ Nunca |

**Por que separar?**  
- `fotos/` contém fotos reais (LGPD) — nunca devem ir ao repositório  
- `avatars/` é gerado pelo sistema e pode ser recriado a qualquer momento rodando o seed  
- Avatares enviados via upload pelo próprio usuário também vão para `avatars/`

---

## 🔒 Segurança

### ✅ O QUE ESTÁ NO GIT:
- `.gitkeep` — mantém as subpastas no repositório
- `*.example` — exemplos de formato (sem dados reais)
- `README.md` — este arquivo

### ❌ O QUE NUNCA DEVE IR PRO GIT:
- `*.csv` — CSVs com dados reais
- `data/avatars/` — avatares processados
- `data/fotos/` — fotos originais dos usuários

---

## 📋 Formato dos CSVs de Usuários

Todos os CSVs seguem o formato base:

```csv
nome,sobrenome,email,senha,role,avatar
```

**Colunas:**
- `nome` — Primeiro nome do usuário
- `sobrenome` — Sobrenome do usuário
- `email` — E-mail institucional (único)
- `senha` — Senha temporária inicial (`must_change_password=True`)
- `role` — (Opcional) Role: `student`, `teacher`, `coordinator`, `porter`, `guardian`, `admin`
- `avatar` — (Opcional) Nome do arquivo relativo a `data/fotos/`. Ex: `foto.jpg` ou `turma1/pedro.png`

**Colunas extras para alunos e professores DT:**
- `sala` — Número da sala de 1 a 12

### Como referenciar avatares no CSV

```csv
nome,sobrenome,email,senha,role,avatar
Ana,Costa,ana@escola.com,Senha!,teacher,ana_costa.jpg
Pedro,Lima,pedro@escola.com,Senha!,student,turma1/pedro.png
Maria,Silva,maria@escola.com,Senha!,teacher,
```

O arquivo `ana_costa.jpg` deve estar em `data/fotos/ana_costa.jpg`.  
Deixe a coluna vazia para usuários sem foto.

### 🏫 Mapeamento de Salas

| Número | Nome     | Número | Nome     |
|--------|----------|--------|----------|
| 1      | 1º ano A | 7      | 2º ano C |
| 2      | 1º ano B | 8      | 2º ano D |
| 3      | 1º ano C | 9      | 3º ano A |
| 4      | 1º ano D | 10     | 3º ano B |
| 5      | 2º ano A | 11     | 3º ano C |
| 6      | 2º ano B | 12     | 3º ano D |

### 📁 Arquivos de Usuários

| Arquivo              | Role Padrão   | is_tutor | Descrição                       |
|----------------------|---------------|----------|---------------------------------|
| `admins.csv`         | `admin`       | `false`  | Administradores do sistema      |
| `coordenadores.csv`  | `coordinator` | `false`  | Coordenadores/Diretoria         |
| `professores.csv`    | `teacher`     | `false`  | Professores normais             |
| `professores_dt.csv` | `teacher`     | `true`   | Professores Diretores de Turma  |
| `alunos.csv`         | `student`     | `false`  | Alunos das turmas               |
| `porteiros.csv`      | `porter`      | `false`  | Porteiros/Seguranças            |
| `responsaveis.csv`   | `guardian`    | `false`  | Pais/Responsáveis               |

---

## ▶️ Como Usar

### 1. Preparar CSVs e fotos

```bash
# Coloque as fotos em data/fotos/
cp /sua/pasta/fotos/*.jpg data/fotos/

# Crie os CSVs referenciando os arquivos pelo nome
data/usuarios/alunos.csv
data/horarios/horario_sala_1.csv
```

### 2. Importar Usuários

```bash
cd backend
uv run python scripts/seed_db.py --real
```

### 3. Importar Horários

```bash
uv run python scripts/seed_db.py --schedules
```

### 4. Ambos de uma vez

```bash
uv run python scripts/seed_db.py --real --schedules
```

---

## 🌐 Como o front-end acessa os avatares?

O campo `avatar_url` retornado pela API contém apenas uma string como `"avatars/42.webp"`.  
O front-end deve chamar o endpoint dedicado para obter a imagem:

```
GET /users/{user_id}/avatar
```

- Retorna a imagem diretamente como `image/webp`
- Retorna 404 se o usuário não tiver avatar
- É público (não exige autenticação) — avatares não são dados sensíveis
- O front-end só chama quando precisa exibir a imagem (lazy loading)

---

## 🔐 Sobre Senhas Temporárias

Todos os usuários importados via CSV são criados com `must_change_password=True`.
O front-end redireciona para troca de senha no primeiro login.
Endpoint: `PATCH /users/me/password`

---

## 🧪 Modo de Desenvolvimento

Para desenvolvimento/testes, use usuários fake (sem CSVs):

```bash
uv run python scripts/seed_db.py
```

Isso cria 7 usuários de teste sem precisar de nenhum CSV.
