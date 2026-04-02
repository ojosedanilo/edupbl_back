# 📋 Guia Rápido: Preparando os CSVs

> Como preparar os CSVs com dados reais da escola para importação.

---

## 📁 Onde colocar cada arquivo

```
data/
├── usuarios/
│   ├── admins.csv
│   ├── coordenadores.csv
│   ├── professores.csv
│   ├── professores_dt.csv
│   ├── alunos.csv
│   ├── porteiros.csv
│   └── responsaveis.csv
└── horarios/
    ├── horario_sala_1.csv
    ├── horario_sala_2.csv
    └── ...
```

---

## 👤 CSVs de Usuários (`data/usuarios/`)

### 1. `admins.csv` — Administradores do Sistema
**Quem vai aqui:** Você e seu professor orientador

```csv
nome,sobrenome,email,senha,role
Jose,Danilo,seu.email@edupbl.com,SenhaSegura123!,admin
Professor,Nome,professor.email@edupbl.com,SenhaSegura123!,admin
```

---

### 2. `coordenadores.csv` — Coordenação + Diretoria

```csv
nome,sobrenome,email,senha,role
Maria,Diretora,diretora@escola.com,Coord2024!,coordinator
Larissa,Coordenadora,coord1@escola.com,Coord2024!,coordinator
```

---

### 3. `professores.csv` — Professores Normais

```csv
nome,sobrenome,email,senha,role
Maria,Silva,maria.silva@escola.com,Prof2024!,teacher
João,Santos,joao.santos@escola.com,Prof2024!,teacher
Ana,Costa,ana.costa@escola.com,Prof2024!,teacher
```

---

### 4. `professores_dt.csv` — Professores Diretores de Turma

```csv
nome,sobrenome,email,senha,role,sala
Carlos,Diretor,carlos.dt@escola.com,ProfDT2024!,teacher,1
Fernanda,Tutora,fernanda.dt@escola.com,ProfDT2024!,teacher,5
```

**Nota:** `sala` é o número da sala (1–12).

---

### 5. `alunos.csv` — Alunos

```csv
nome,sobrenome,email,senha,role,sala
Pedro,Lima,pedro.lima@escola.com,Aluno2024!,student,1
Lucia,Ferreira,lucia.ferreira@escola.com,Aluno2024!,student,1
```

---

### 6. `porteiros.csv` e `responsaveis.csv`

```csv
nome,sobrenome,email,senha,role
José,Porteiro,jose.porteiro@escola.com,Port2024!,porter
```

---

## 📅 CSVs de Horário (`data/horarios/`)

Um arquivo por turma: `horario_sala_1.csv`, `horario_sala_2.csv`, ..., `horario_sala_12.csv`

```csv
email_professor,dia_semana,numero_periodo,tipo,titulo
maria.silva@escola.com,2,1,class_period,Matemática
maria.silva@escola.com,2,2,class_period,Matemática
joao.santos@escola.com,2,3,class_period,Português
,2,,snack_break,Intervalo
ana.costa@escola.com,2,4,class_period,Ciências
,2,,lunch_break,Almoço
pedro.prof@escola.com,2,5,class_period,História
joao.santos@escola.com,4,3,planning,Planejamento
,5,,free,Folga
```

**Dias:** 2=segunda, 3=terça, 4=quarta, 5=quinta, 6=sexta

**Tipos:**
- `class_period` → aula (professor obrigatório pelo e-mail)
- `planning` → planejamento (professor fora da sala)
- `free` → folga (professor não está na escola)
- `snack_break` → intervalo de lanche
- `lunch_break` → intervalo de almoço

---

## ▶️ Como Importar

### Só usuários:
```bash
uv run python scripts/seed_db.py --real
```

### Só horários (professores já devem estar no banco):
```bash
uv run python scripts/seed_db.py --schedules
```

### Usuários + horários juntos:
```bash
uv run python scripts/seed_db.py --real --schedules
```

### Tudo (usuários de teste + reais + horários):
```bash
uv run python scripts/seed_db.py --all
```

---

## 🎯 Ordem de Criação Sugerida

1. **admins.csv** → Você e professor (mais importante!)
2. **coordenadores.csv** → Diretora e coordenadores
3. **professores_dt.csv** → Professores DT das turmas
4. **professores.csv** → Outros professores
5. **alunos.csv** → Alunos das turmas piloto
6. **porteiros.csv** → Porteiros
7. **responsaveis.csv** → Pais dos alunos
8. **horario_sala_N.csv** → Grade de cada turma (após importar professores)

---

## 🔑 Sobre as Senhas

**Opção recomendada (senha padrão por grupo):**
```
Admins:          AdminDev2024!
Coordenadores:   Coord2024!
Professores:     Prof2024!
Professores DT:  ProfDT2024!
Alunos:          Aluno2024!
Porteiros:       Port2024!
Responsáveis:    Resp2024!
```

Todos os usuários importados têm `must_change_password=True` — o sistema força troca de senha no primeiro login.

---

## ⚠️ Erros Comuns

### "CSV inválido"
→ Verifique se o header está correto e se o arquivo está em UTF-8.

### "Professor não encontrado"
→ Importe os professores antes dos horários.

### "Usuário já existe"
→ Normal! A importação é idempotente — duplicatas são ignoradas.

### "Nenhum CSV de horário encontrado"
→ Confirme que os arquivos estão em `data/horarios/` (não em `data/`).
