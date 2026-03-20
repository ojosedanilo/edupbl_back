# 📂 Pasta de Dados — Usuários Reais

> Esta pasta contém os CSVs com dados reais dos usuários da escola.  
> **NUNCA commite esses arquivos no Git!**

---

## 🔒 Segurança

### ✅ O QUE ESTÁ NO GIT:
- `.gitkeep` — mantém a pasta vazia no repositório
- `*.example` — exemplos de formato (sem dados reais)
- `README.md` — este arquivo

### ❌ O QUE NUNCA DEVE IR PRO GIT:
- `*.csv` — CSVs com dados reais (ignorados pelo `.gitignore`)
- Qualquer arquivo com nomes, e-mails ou senhas reais

---

## 📋 Formato dos CSVs

Todos os CSVs seguem o mesmo formato base:

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

**Nota:** A coluna `role` é opcional. Se não for fornecida, o sistema usa o padrão baseado no nome do arquivo.

---

## 📁 Arquivos Esperados

| Arquivo | Role Padrão | is_tutor | Descrição |
|---------|-------------|----------|-----------|
| `admins.csv` | `admin` | `false` | Administradores do sistema (devs) |
| `coordenadores.csv` | `coordinator` | `false` | Coordenadores/Diretoria |
| `professores.csv` | `teacher` | `false` | Professores normais |
| `professores_dt.csv` | `teacher` | `true` | Professores Diretores de Turma |
| `alunos.csv` | `student` | `false` | Alunos das turmas |
| `porteiros.csv` | `porter` | `false` | Porteiros/Seguranças |
| `responsaveis.csv` | `guardian` | `false` | Pais/Responsáveis |

### 🔑 Diferença: ADMIN vs COORDINATOR

**ADMIN:**
- Desenvolvedores e mantenedores do sistema
- Acesso total (incluindo mudar roles de usuários)
- **Exemplo:** Você e seu professor orientador

**COORDINATOR:**
- Coordenadores pedagógicos e diretoria
- Acesso quase total às funcionalidades da escola
- **NÃO pode** mudar roles de usuários (só ADMIN pode)
- **Exemplo:** Coordenadores pedagógicos, Diretora

---

## 📝 Exemplos

### admins.csv
```csv
nome,sobrenome,email,senha,role
Jose,Danilo,jose.danilo@edupbl.com,AdminDev2024!,admin
Professor,Orientador,prof.orientador@edupbl.com,AdminDev2024!,admin
```

### coordenadores.csv
```csv
nome,sobrenome,email,senha,role
Larissa,Coordenadora,larissa.coord@escola.com,Coord2024!,coordinator
Maria,Diretora,maria.diretora@escola.com,Coord2024!,coordinator
```

### professores.csv
```csv
nome,sobrenome,email,senha,role
Maria,Silva,maria.silva@escola.com,TempProf2024!,teacher
João,Santos,joao.santos@escola.com,TempProf2024!,teacher
```

### professores_dt.csv
```csv
nome,sobrenome,email,senha,role,sala
Carlos,Diretor,carlos.diretor@escola.com,TempDT2024!,teacher,1
Fernanda,Tutora,fernanda.dt@escola.com,TempDT2024!,teacher,5
```

### alunos.csv
```csv
nome,sobrenome,email,senha,role,sala
Pedro,Lima,pedro.lima@escola.com,Aluno2024!,student,1
Lucia,Ferreira,lucia.ferreira@escola.com,Aluno2024!,student,1
```

### porteiros.csv
```csv
nome,sobrenome,email,senha,role
José,Porteiro,jose.porteiro@escola.com,Port2024!,porter
```

### responsaveis.csv
```csv
nome,sobrenome,email,senha,role
Maria,Responsável,maria.resp@email.com,Resp2024!,guardian
```

---

## ▶️ Como Usar

### 1. Preparar CSVs

Crie os arquivos CSV nesta pasta com os dados reais:

```bash
cd backend/data
# Crie professores.csv, alunos.csv, etc.
```

### 2. Importar Usuários

Execute o script de importação:

```bash
cd backend
uv run python scripts/seed_db.py --real
```

### 3. Verificar Importação

O script mostrará:
- Quantos usuários foram criados
- Quantos já existiam (pulados)
- Erros encontrados (se houver)

### 4. Instruir Usuários

Todos os usuários importados via CSV são criados com `must_change_password=True`. O front-end detecta esse campo na resposta do login e redireciona automaticamente para a tela de troca de senha antes de liberar o acesso. O endpoint responsável pela troca é `PATCH /users/me/password`.

---

## 🔐 Sobre Senhas Temporárias

### Recomendações:

**Opção A: Senha padrão simples**
- Todos começam com a mesma senha (ex: `EduPBL2024!`)
- Sistema **força** troca no primeiro login
- Mais fácil de gerenciar

**Opção B: Senha baseada em dados pessoais**
- Ex: últimos 6 dígitos do CPF
- Mais seguro que senha padrão
- Requer que você tenha o CPF de todos

**Opção C: Senhas aleatórias**
- Gera senha única para cada usuário
- Envia por e-mail
- Mais seguro, mas requer infraestrutura de e-mail

**Para o MVP:** Use Opção A (senha padrão).

---

## ⚠️ Importante

1. **Senhas temporárias são visíveis nos CSVs**
   - Guarde os CSVs em local seguro
   - Não compartilhe CSVs por e-mail/WhatsApp
   - Apague os CSVs após importação (opcional)

2. **Usuários devem trocar senha**
   - Todos os usuários importados via CSV são criados com `must_change_password=True`
   - O front-end redireciona automaticamente para troca de senha no primeiro login
   - Endpoint: `PATCH /users/me/password`

3. **Backups**
   - Guarde backup dos CSVs fora do repositório
   - Não faça backup no Git
   - Use pen drive, nuvem pessoal, etc.

---

## 🧪 Modo de Desenvolvimento

Para desenvolvimento/testes, use usuários fake:

```bash
uv run python scripts/seed_db.py
```

Isso cria 7 usuários de teste sem precisar dos CSVs.

---

## 📊 Checklist de Importação

Antes de rodar em produção:

- [ ] CSVs criados e validados
- [ ] Todas as senhas temporárias definidas
- [ ] E-mails institucionais corretos
- [ ] Banco de dados criado (`scripts/init_db.py`)
- [ ] Migrations rodadas (`alembic upgrade head`)
- [ ] Script testado em ambiente de desenvolvimento
- [ ] Plano de comunicação com usuários (avisar senha temporária)
- [ ] Endpoint de troca de senha implementado

---

## 🆘 Solução de Problemas

### Erro: "CSV inválido"
- Verifique se o CSV tem header: `nome,sobrenome,email,senha,role`
- Verifique se não há linhas vazias
- Certifique-se que está salvando como UTF-8

### Erro: "Email inválido"
- Todos os e-mails devem ter `@`
- E-mails devem ser únicos

### Erro: "Role inválida"
- Roles válidos: `student`, `teacher`, `coordinator`, `porter`, `guardian`, `admin`
- Minúsculas apenas
- Se omitir, usa padrão do arquivo

### Usuários não foram criados
- Verifique se já existem (importação é idempotente)
- Veja os erros no output do script
- Confirme que migrations foram rodadas

---

## 📞 Dúvidas?

Revise o guia `backend/docs/SEGURANCA_DADOS_REAIS.md` para mais detalhes sobre segurança e boas práticas.
