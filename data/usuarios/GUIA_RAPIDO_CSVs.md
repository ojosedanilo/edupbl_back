# 📋 Guia Rápido: Preparando os CSVs

> Como preparar os CSVs com dados reais da escola para importação.

---

## 📂 CSVs Necessários

Crie esses arquivos em `backend/data/`:

### 1. `admins.csv` — Administradores do Sistema
**Quem vai aqui:** Você e seu professor orientador

```csv
nome,sobrenome,email,senha,role
Jose,Danilo,seu.email@edupbl.com,SenhaSegura123!,admin
Professor,Nome,professor.email@edupbl.com,SenhaSegura123!,admin
```

**Permissões:** Controle total do sistema, incluindo mudar roles

---

### 2. `coordenadores.csv` — Coordenação + Diretoria
**Quem vai aqui:** Coordenadores pedagógicos e a diretora

```csv
nome,sobrenome,email,senha,role
Maria,Diretora,diretora@escola.com,Coord2024!,coordinator
Larissa,Coordenadora,coord1@escola.com,Coord2024!,coordinator
Roberto,Coordenador,coord2@escola.com,Coord2024!,coordinator
```

**Permissões:** Quase tudo (menos mudar roles de usuários)

---

### 3. `professores.csv` — Professores Normais
**Quem vai aqui:** Todos os professores que NÃO são Diretores de Turma

```csv
nome,sobrenome,email,senha,role
Maria,Silva,maria.silva@escola.com,Prof2024!,teacher
João,Santos,joao.santos@escola.com,Prof2024!,teacher
Ana,Costa,ana.costa@escola.com,Prof2024!,teacher
```

**Permissões:** Criar ocorrências, reservar espaços, ver relatórios da turma

---

### 4. `professores_dt.csv` — Professores Diretores de Turma
**Quem vai aqui:** Professores que são DT (um por turma)

```csv
nome,sobrenome,email,senha,role,sala
Carlos,Diretor,carlos.dt@escola.com,ProfDT2024!,teacher,1
Fernanda,Tutora,fernanda.dt@escola.com,ProfDT2024!,teacher,5
```

**Permissões:** Tudo que professor tem + validar atestados + ver relatórios da turma deles

**Nota:** `is_tutor` é setado automaticamente para `true` neste arquivo. O campo `sala` é o número da sala (1–12) — veja tabela em `data/README.md`.

---

### 5. `alunos.csv` — Alunos das Turmas Piloto
**Quem vai aqui:** Alunos das 2 turmas que vão testar o sistema

```csv
nome,sobrenome,email,senha,role,sala
Pedro,Lima,pedro.lima@escola.com,Aluno2024!,student,1
Lucia,Ferreira,lucia.ferreira@escola.com,Aluno2024!,student,1
Rafael,Oliveira,rafael.oliveira@escola.com,Aluno2024!,student,5
Beatriz,Martins,beatriz.martins@escola.com,Aluno2024!,student,9
```

**Permissões:** Ver suas próprias ocorrências e atrasos

**Nota:** O campo `sala` é o número da sala (1–12). Alunos sem sala definida ficam com `classroom_id = NULL`.

---

### 6. `porteiros.csv` — Porteiros
**Quem vai aqui:** Porteiros/seguranças da escola

```csv
nome,sobrenome,email,senha,role
José,Porteiro,jose.porteiro@escola.com,Port2024!,porter
Antonio,Segurança,antonio.seguranca@escola.com,Port2024!,porter
```

**Permissões:** Registrar atrasos, ver lista de atrasos

---

### 7. `responsaveis.csv` — Pais/Responsáveis
**Quem vai aqui:** Pais dos alunos das turmas piloto

```csv
nome,sobrenome,email,senha,role
Maria,Mae,maria.mae@email.com,Resp2024!,guardian
João,Pai,joao.pai@email.com,Resp2024!,guardian
Sandra,Responsavel,sandra.resp@email.com,Resp2024!,guardian
```

**Permissões:** Ver ocorrências e atrasos dos filhos, enviar atestados

---

## 🔑 Sobre as Senhas

### Recomendações:

**Opção 1: Senha padrão por grupo (RECOMENDADO)**
```
Admins: AdminDev2024!
Coordenadores: Coord2024!
Professores: Prof2024!
Professores DT: ProfDT2024!
Alunos: Aluno2024!
Porteiros: Port2024!
Responsáveis: Resp2024!
```

**Vantagens:**
- ✅ Fácil de gerenciar
- ✅ Fácil de comunicar
- ✅ Todos do mesmo grupo usam a mesma senha inicial

**Opção 2: Senha única para todos**
```
EduPBL2026!
```

**Vantagens:**
- ✅ Mais simples ainda
- ✅ Uma única senha para comunicar

**⚠️ IMPORTANTE:** Independente da opção, **instrua todos a trocarem no primeiro login!**

---

## 📝 Checklist de Preparação

### Antes de criar os CSVs:

- [ ] Colete nomes completos de todos
- [ ] Colete e-mails institucionais
- [ ] Decida estratégia de senha temporária
- [ ] Separe professores normais de DT
- [ ] Identifique quem é coordenador vs diretora

### Ao criar os CSVs:

- [ ] Use formato exato: `nome,sobrenome,email,senha,role`
- [ ] Primeira linha = header (não pule!)
- [ ] E-mails únicos (não pode repetir)
- [ ] Salve como UTF-8
- [ ] Sem linhas vazias no meio

### Após criar os CSVs:

- [ ] Guarde em local seguro (não compartilhe)
- [ ] Não commite no Git (já está no .gitignore)
- [ ] Teste importação com dados de exemplo primeiro
- [ ] Importe dados reais
- [ ] Comunique senhas temporárias aos usuários
- [ ] (Opcional) Apague CSVs após importação

---

## ▶️ Como Importar

### 1. Coloque CSVs na pasta correta
```bash
cd backend/data
# Crie os CSVs aqui
```

### 2. Rode importação
```bash
cd backend
uv run python scripts/seed_db.py --real
```

### 3. Verifique resultado
```
📂 Importando usuários reais de CSVs...

📄 Processando: admins.csv
  ✅ 2 usuários criados

📄 Processando: coordenadores.csv
  ✅ 3 usuários criados

📄 Processando: professores.csv
  ✅ 15 usuários criados

📄 Processando: professores_dt.csv
  ✅ 2 usuários criados [Professores DT]

📄 Processando: alunos.csv
  ✅ 45 usuários criados

📄 Processando: porteiros.csv
  ✅ 2 usuários criados

📄 Processando: responsaveis.csv
  ✅ 45 usuários criados

✅ 114 usuários reais importados com sucesso!

⚠️  IMPORTANTE: Usuários reais foram criados com must_change_password=True!
   Eles serão forçados a trocar a senha no primeiro login.
   Endpoint de troca: PATCH /users/me/password
```

---

## 🎯 Ordem de Criação Sugerida

1. **admins.csv** → Você e professor (mais importante!)
2. **coordenadores.csv** → Diretora e coordenadores
3. **professores_dt.csv** → Professores DT das 2 turmas
4. **professores.csv** → Outros professores
5. **alunos.csv** → Alunos das 2 turmas piloto
6. **porteiros.csv** → Porteiros
7. **responsaveis.csv** → Pais dos alunos

---

## ⚠️ Erros Comuns

### "CSV inválido"
❌ **Problema:** Header errado ou ausente
✅ **Solução:** Primeira linha deve ser: `nome,sobrenome,email,senha,role`

### "Email inválido"
❌ **Problema:** E-mail sem `@`
✅ **Solução:** Todos e-mails devem ter formato: `nome@dominio.com`

### "Nenhum usuário foi importado"
❌ **Problema:** Arquivos não estão em `backend/data/`
✅ **Solução:** Confirme o caminho e rode de `backend/`

### "Usuário já existe"
ℹ️ **Não é erro!** Sistema é idempotente — ignora duplicatas automaticamente

---

## 💡 Dicas

1. **Use planilha Excel/Google Sheets primeiro**
   - Edite tudo lá
   - Exporte como CSV
   - Mais fácil de organizar

2. **Teste com poucos usuários primeiro**
   - Crie CSV com 2-3 usuários
   - Importe e teste
   - Se funcionar, adicione o resto

3. **Não apague os exemplos (.example)**
   - São referência útil
   - Vão pro Git para documentação

4. **Backup dos CSVs originais**
   - Guarde cópia fora do projeto
   - Pen drive, nuvem pessoal, etc.
   - Não no Git!

---

## 🚀 Próximo Passo

Após importar com sucesso:
1. Teste login com cada tipo de usuário
2. Verifique permissões
3. Instrua todos a trocarem senha
4. Comece teste piloto!

---

Dúvidas? Consulte `backend/data/README.md` para documentação completa.
