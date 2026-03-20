# 🔒 Segurança com Dados Reais de Usuários

> **CRÍTICO:** Este documento explica como lidar com os CSVs de dados reais (professores, alunos, coordenadores) sem comprometer a segurança.

---

## ⚠️ REGRAS DE OURO

### ❌ **NUNCA FAÇA:**

1. **Commitar CSVs com dados reais no Git**
   - Nomes reais
   - E-mails institucionais
   - CPFs, telefones, endereços
   - Qualquer dado pessoal real

2. **Colocar dados reais diretamente no código**
   ```python
   # ❌ NUNCA FAZER ISSO
   User(email='joao.silva@escola.com', ...)
   ```

3. **Compartilhar o repositório público com dados reais**
   - Mesmo que depois você delete, o Git guarda histórico
   - Uma vez no GitHub público = vazado para sempre

### ✅ **SEMPRE FAÇA:**

1. **Dados reais ficam FORA do repositório**
2. **Use script de importação local**
3. **Adicione os CSVs no `.gitignore`**
4. **Documente o processo, mas não os dados**

---

## 📂 Estrutura Recomendada

```
backend/
├── app/
├── scripts/
│   ├── seed_db.py           # Usuários FAKE para dev
│   └── import_real_users.py # Script de importação (SEM dados reais)
├── data/                     # ← Pasta LOCAL, não vai pro Git
│   ├── .gitkeep              # Mantém a pasta vazia no Git
│   ├── professores.csv       # ← IGNORADO pelo Git
│   ├── alunos_3a.csv         # ← IGNORADO pelo Git
│   ├── alunos_3b.csv         # ← IGNORADO pelo Git
│   └── coordenadores.csv     # ← IGNORADO pelo Git
├── .gitignore                # Ignora data/*.csv
└── README.md
```

---

## 🛠️ Passo a Passo: Importação Segura

### **Passo 1: Configurar `.gitignore`**

Adicione no `.gitignore` do backend:

```gitignore
# Dados reais - NUNCA commitar
data/*.csv
data/*.xlsx
data/*.json
*.env
.env.*

# Mantém a pasta mas não o conteúdo
!data/.gitkeep
```

### **Passo 2: Criar a pasta `data/` local**

```bash
cd backend
mkdir -p data
touch data/.gitkeep
```

### **Passo 3: Colocar os CSVs na pasta `data/`**

Copie os arquivos CSV que você recebeu para `backend/data/`:
- `professores.csv`
- `alunos_3a.csv`
- `alunos_3b.csv`
- `coordenadores.csv`
- `diretora.csv`

**Importante:** Nunca dê `git add data/*.csv`!

### **Passo 4: Criar script de importação**

Crie `scripts/import_real_users.py` que:
- Lê os CSVs da pasta `data/`
- Valida os dados
- Cria usuários no banco
- Gera senhas temporárias seguras
- **Não contém dados reais hardcoded**

### **Passo 5: Documentar formato esperado dos CSVs**

Crie `data/README.md` (esse sim pode ir pro Git):

```markdown
# Formato dos CSVs

## professores.csv
Colunas: nome_completo, email, is_tutor

## alunos_3a.csv e alunos_3b.csv
Colunas: nome_completo, email, turma

## coordenadores.csv
Colunas: nome_completo, email

## diretora.csv
Colunas: nome_completo, email
```

---

## 🔐 Estratégia de Senhas

### **Para usuários reais (primeira vez):**

**Opção A: Senha temporária padrão**
- Todos começam com senha: `EduPBL2026!` (ou similar)
- Sistema **força troca** no primeiro login
- Implementar endpoint `/auth/change-password`

**Opção B: Senha aleatória por e-mail**
- Gera senha aleatória para cada usuário
- Envia por e-mail institucional
- Mais seguro, mas precisa de servidor de e-mail

**Opção C: CPF como senha inicial**
- Senha = últimos 6 dígitos do CPF
- Usuário **deve** trocar no primeiro acesso
- Prático, mas menos seguro

**Recomendação:** Opção A (mais simples pra MVP)

---

## 📋 Formato Sugerido dos CSVs

### `professores.csv`
```csv
nome_completo,email,is_tutor
Maria Silva,maria.silva@escola.com,true
João Santos,joao.santos@escola.com,false
```

### `alunos_3a.csv`
```csv
nome_completo,email,turma
Ana Costa,ana.costa@escola.com,3A
Pedro Lima,pedro.lima@escola.com,3A
```

### `coordenadores.csv`
```csv
nome_completo,email
Larissa Coordenadora,larissa.coord@escola.com
```

### `diretora.csv`
```csv
nome_completo,email
Diretora Nome,diretora@escola.com
```

---

## 🎯 Processo de Importação

### **1. Desenvolvimento (dados fake):**
```bash
uv run python scripts/seed_db.py
# Cria: admin, coordenador, professor, aluno... (dados de teste)
```

### **2. Produção/Teste Piloto (dados reais):**
```bash
# Uma única vez, manualmente
uv run python scripts/import_real_users.py
```

**Importante:**
- Rode `import_real_users.py` **apenas** no servidor de produção
- **Nunca** rode em dev com dados reais
- Mantenha backups dos CSVs originais (fora do Git)

---

## 🚨 Checklist de Segurança

Antes de commitar, verifique:

- [ ] `.gitignore` inclui `data/*.csv`
- [ ] Nenhum CSV com dados reais foi commitado
- [ ] `git status` não mostra arquivos CSV
- [ ] Script de importação não tem dados hardcoded
- [ ] Senhas são geradas, não fixas no código
- [ ] CSVs estão apenas na máquina local

---

## 📝 Para o README do Projeto

Adicione no README:

```markdown
## Importação de Usuários Reais

Para importar usuários reais em produção:

1. Coloque os CSVs na pasta `backend/data/`
2. Execute: `uv run python scripts/import_real_users.py`
3. Informe aos usuários a senha temporária
4. Oriente a troca de senha no primeiro acesso

**Nota:** Os CSVs com dados reais não estão no repositório por questões de privacidade.
```

---

## ⚡ Alternativa: Variáveis de Ambiente

Se você precisar de dados sensíveis no código (como credenciais de API), use variáveis de ambiente:

```python
# settings.py
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")
```

E nunca commite o `.env`:
```bash
# .gitignore
.env
.env.*
```

---

## 🎓 Resumo

✅ **Dados reais = pasta `data/` local (ignorada pelo Git)**  
✅ **Script de importação = no repositório (sem dados reais)**  
✅ **Senhas temporárias = geradas pelo script**  
✅ **CSVs originais = backup fora do Git**  
✅ **Documentação = formato esperado, não dados reais**

**Lembre-se:** LGPD é lei! Dados pessoais vazados podem gerar multas e processos.
