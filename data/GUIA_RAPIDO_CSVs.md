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
├── avatars/           ← gerado automaticamente pelo seed/upload
│   ├── 1.webp
│   ├── 2.webp
│   └── ...
├── fotos/             ← opcional: coloque aqui as fotos originais antes do import
│   └── alunos/
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
nome,sobrenome,email,senha,role,sala,avatar
Carlos,Diretor,carlos.dt@escola.com,ProfDT2024!,teacher,1,fotos/carlos.jpg
Fernanda,Tutora,fernanda.dt@escola.com,ProfDT2024!,teacher,5,
```

**Nota:** `sala` é o número da sala (1–12). `avatar` segue as mesmas regras do `alunos.csv`.

---

### 5. `alunos.csv` — Alunos

```csv
nome,sobrenome,email,senha,role,sala,avatar
Pedro,Lima,pedro.lima@escola.com,Aluno2024!,student,1,fotos/alunos/pedro.jpg
Lucia,Ferreira,lucia.ferreira@escola.com,Aluno2024!,student,1,
```

A coluna `avatar` é **opcional**: deixe vazia ou omita a coluna inteiramente para pular.
O caminho é **relativo à pasta `data/`** do projeto (nunca use caminhos absolutos).

**Formatos aceitos:** JPEG, PNG ou WebP. A imagem é redimensionada automaticamente
para 256×256 px e salva como WebP em `data/avatars/`.

---

### 6. `porteiros.csv` e `responsaveis.csv`

```csv
nome,sobrenome,email,senha,role
José,Porteiro,jose.porteiro@escola.com,Port2024!,porter
```

---

## 📅 CSVs de Horário (`data/horarios/`)

### Arquivos de grade por turma

Um arquivo por turma: `horario_sala_1.csv`, ..., `horario_sala_12.csv`

Cada linha representa um slot de **aula ou intervalo da turma**. Slots de folga
e planejamento do professor **não entram aqui** — veja `folgas_professores.csv` abaixo.

```csv
email_professor,dia_semana,numero_periodo,tipo,titulo
maria.silva@escola.com,2,1,class_period,Matemática
maria.silva@escola.com,2,2,class_period,Matemática
joao.santos@escola.com,2,3,class_period,Português
,2,,snack_break,Intervalo
ana.costa@escola.com,2,4,class_period,Ciências
ana.costa@escola.com,2,5,class_period,Ciências
,2,,lunch_break,Almoço
pedro.prof@escola.com,2,6,class_period,História
```

**Dias:** 2=segunda, 3=terça, 4=quarta, 5=quinta, 6=sexta

**Tipos válidos neste arquivo:**
- `class_period` → aula normal (e-mail do professor obrigatório)
- `snack_break` → intervalo de lanche (e-mail vazio)
- `lunch_break` → intervalo de almoço (e-mail vazio)

> ⚠️ **Não use `planning` nem `free` aqui.** Esses tipos são de responsabilidade
> do professor, não da turma. Use `folgas_professores.csv` para isso.

---

### `folgas_professores.csv` — Folgas por professor

Arquivo único para declarar os slots de **folga semanal** de cada professor.
O sistema gera automaticamente os slots de **planejamento** para todos os
demais períodos que não sejam aula nem folga.

```
data/horarios/folgas_professores.csv
```

```csv
email,dia_semana,numero_slot
maria.silva@escola.com,2,5
maria.silva@escola.com,4,5
maria.silva@escola.com,6,5
joao.santos@escola.com,3,4
joao.santos@escola.com,3,5
joao.santos@escola.com,5,4
joao.santos@escola.com,5,5
```

**Colunas:**
- `email` — e-mail do professor (deve existir no banco)
- `dia_semana` — 2=segunda … 6=sexta
- `numero_slot` — número do período de aula (1–9)

**Como funciona o planejamento automático:**
Após importar as folgas, o sistema percorre todos os professores com aulas
cadastradas e cria um slot `planning` em cada combinação (dia × período) que
**não** esteja marcada como `class_period` nem como `free`. Não é necessário
listar os planejamentos manualmente.

---

## ▶️ Como Importar

### Tudo de uma vez (recomendado):
```bash
uv run python scripts/seed_db.py --real
```
Importa usuários + horários de turmas + folgas/planejamentos na ordem correta.

### Por etapas (quando necessário):
```bash
# 1. Usuários
uv run python scripts/seed_db.py --real-users

# 2. Horários de turmas (requer professores no banco)
uv run python scripts/seed_db.py --real-schedules

# 3. Folgas e planejamentos (requer aulas no banco)
uv run python scripts/seed_db.py --real-free-periods
```

### Dados de teste (desenvolvimento):
```bash
uv run python scripts/seed_db.py --tests
```
Cria 7 usuários com senhas simples. Não misture com `--real`.

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
9. **folgas_professores.csv** → Folgas por professor (gera planejamentos automaticamente)

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
