import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User, UserRole
from app.shared.security import get_password_hash


async def seed_test_users(session: AsyncSession):
    """Cria usuários de teste para cada role (idempotente — pula se já existir)"""
    # !!! Para testes !!!

    users = [
        User(
            username='admin',
            email='admin@edupbl.com',
            password=get_password_hash('admin'),
            first_name='Admin',
            last_name='Sistema',
            role=UserRole.ADMIN,
            is_tutor=False,
            is_active=True,
        ),
        User(
            username='coordenador',
            email='coordenador@edupbl.com',
            password=get_password_hash('coordenador'),
            first_name='Larissa',
            last_name='Coordenadora',
            role=UserRole.COORDINATOR,
            is_tutor=False,
            is_active=True,
        ),
        User(
            username='professor',
            email='professor@edupbl.com',
            password=get_password_hash('professor'),
            first_name='Lucas',
            last_name='Professor',
            role=UserRole.TEACHER,
            is_tutor=False,
            is_active=True,
        ),
        User(
            username='professor_dt',
            email='professor_dt@edupbl.com',
            password=get_password_hash('professor_dt'),
            first_name='Maria',
            last_name='Professor DT',
            role=UserRole.TEACHER,
            is_tutor=True,  # <- Professor DT
            is_active=True,
        ),
        User(
            username='porteiro',
            email='porteiro@edupbl.com',
            password=get_password_hash('porteiro'),
            first_name='Lucas',
            last_name='Porteiro',
            role=UserRole.PORTER,
            is_tutor=False,
            is_active=True,
        ),
        User(
            username='aluno',
            email='aluno@edupbl.com',
            password=get_password_hash('aluno'),
            first_name='Danilo',
            last_name='Aluno',
            role=UserRole.STUDENT,
            is_tutor=False,
            is_active=True,
        ),
        User(
            username='responsavel',
            email='responsavel@edupbl.com',
            password=get_password_hash('responsavel'),
            first_name='Joao',
            last_name='Responsavel',
            role=UserRole.GUARDIAN,
            is_tutor=False,
            is_active=True,
        ),
    ]

    criados = 0
    for user in users:
        # Verifica se ja existe pelo email para ser idempotente
        existing = await session.scalar(
            select(User).where(User.email == user.email)
        )
        if not existing:
            session.add(user)
            criados += 1

    if criados:
        await session.commit()
        print(f'✅ {criados} usuarios de teste criados com sucesso!')
    else:
        print('ℹ️  Todos os usuarios de teste ja existem. Nenhum criado.')


async def seed_real_users(session: AsyncSession):
    """
    Importa usuários reais dos CSVs em backend/data/
    
    CSVs esperados:
    - professores.csv
    - professores_dt.csv
    - alunos.csv
    - coordenadores.csv
    - porteiros.csv
    - responsaveis.csv
    
    Formato de cada CSV: nome,sobrenome,email,senha,role
    
    Exemplo:
    Maria,Silva,maria.silva@escola.com,Temp2024!,teacher
    
    Nota: A coluna 'role' é opcional. Se não fornecida, usa o padrão
    baseado no nome do arquivo (professores.csv → teacher).
    """
    # Caminho base dos CSVs
    data_dir = Path(__file__).parent.parent.parent / 'data'
    
    # Mapeamento de função para role
    ROLE_MAP = {
        'admin': UserRole.ADMIN,
        'coordinator': UserRole.COORDINATOR,
        'teacher': UserRole.TEACHER,
        'porter': UserRole.PORTER,
        'student': UserRole.STUDENT,
        'guardian': UserRole.GUARDIAN,
    }
    
    # CSVs a importar com role padrão e flag is_tutor
    # Formato: (arquivo, role_padrão, is_tutor)
    csv_configs = [
        ('admins.csv', UserRole.ADMIN, False),
        ('coordenadores.csv', UserRole.COORDINATOR, False),
        ('professores.csv', UserRole.TEACHER, False),
        ('professores_dt.csv', UserRole.TEACHER, True),
        ('alunos.csv', UserRole.STUDENT, False),
        ('porteiros.csv', UserRole.PORTER, False),
        ('responsaveis.csv', UserRole.GUARDIAN, False),
    ]
    
    total_criados = 0
    total_existentes = 0
    total_erros = 0
    
    print('=' * 60)
    print('📂 Importando usuários reais de CSVs...')
    print('=' * 60)
    
    for csv_file, default_role, is_tutor in csv_configs:
        csv_path = data_dir / csv_file
        
        # Pula se arquivo não existir
        if not csv_path.exists():
            print(f'\nℹ️  {csv_file} não encontrado (pulando)')
            continue
        
        print(f'\n📄 Processando: {csv_file}')
        criados_arquivo = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Valida header
                expected_cols = {'nome', 'sobrenome', 'email', 'senha'}
                if not expected_cols.issubset(set(reader.fieldnames)):
                    print(f'  ❌ CSV inválido! Esperado: nome,sobrenome,email,senha')
                    print(f'     Encontrado: {",".join(reader.fieldnames)}')
                    total_erros += 1
                    continue
                
                for linha_num, row in enumerate(reader, start=2):
                    try:
                        # Extrai dados da linha
                        nome = row['nome'].strip()
                        sobrenome = row['sobrenome'].strip()
                        email = row['email'].strip().lower()
                        senha = row['senha'].strip()
                        
                        # Role: pega do CSV se fornecido, senão usa padrão
                        role_str = row.get('role', '').strip().lower()
                        if role_str and role_str in ROLE_MAP:
                            role = ROLE_MAP[role_str]
                        elif role_str and role_str not in ROLE_MAP:
                            print(f'  ⚠️  Linha {linha_num}: Role "{role_str}" inválida. Usando {default_role.value}')
                            role = default_role
                        else:
                            role = default_role
                        
                        # Validações básicas
                        if not nome or not sobrenome or not email or not senha:
                            print(f'  ⚠️  Linha {linha_num}: Campos vazios (pulando)')
                            total_erros += 1
                            continue
                        
                        if '@' not in email:
                            print(f'  ⚠️  Linha {linha_num}: Email inválido "{email}" (pulando)')
                            total_erros += 1
                            continue
                        
                        # Username = parte antes do @
                        username = email.split('@')[0]
                        
                        # Verifica se username já existe (pode conflitar)
                        existing_username = await session.scalar(
                            select(User).where(User.username == username)
                        )
                        
                        # Se existir, adiciona sufixo numérico
                        if existing_username:
                            counter = 1
                            original_username = username
                            while existing_username:
                                username = f'{original_username}{counter}'
                                existing_username = await session.scalar(
                                    select(User).where(User.username == username)
                                )
                                counter += 1
                        
                        # Verifica se email já existe
                        existing = await session.scalar(
                            select(User).where(User.email == email)
                        )
                        
                        if existing:
                            total_existentes += 1
                            continue  # Pula sem mensagem (muitos usuários)
                        
                        # Cria usuário
                        user = User(
                            username=username,
                            email=email,
                            password=get_password_hash(senha),
                            first_name=nome,
                            last_name=sobrenome,
                            role=role,
                            is_tutor=is_tutor if role == UserRole.TEACHER else False,
                            is_active=True,
                        )
                        
                        session.add(user)
                        criados_arquivo += 1
                        total_criados += 1
                        
                    except Exception as e:
                        print(f'  ❌ Linha {linha_num}: Erro - {e}')
                        total_erros += 1
                        continue
        
        except Exception as e:
            print(f'  ❌ Erro ao processar {csv_file}: {e}')
            total_erros += 1
            continue
        
        # Mostra resumo do arquivo
        if criados_arquivo > 0:
            dt_suffix = ' [Professores DT]' if is_tutor else ''
            print(f'  ✅ {criados_arquivo} usuários criados{dt_suffix}')
    
    # Commit final
    if total_criados > 0:
        await session.commit()
    
    # Resumo final
    print('\n' + '=' * 60)
    if total_criados > 0:
        print(f'✅ {total_criados} usuários reais importados com sucesso!')
    if total_existentes > 0:
        print(f'ℹ️  {total_existentes} usuários já existiam (pulados)')
    if total_erros > 0:
        print(f'⚠️  {total_erros} erros encontrados')
    
    if total_criados == 0 and total_existentes == 0:
        print('⚠️  Nenhum usuário foi importado!')
        print('\n💡 Dica: Verifique se os CSVs existem em backend/data/')
        print('   Formato esperado: nome,sobrenome,email,senha,role')
    
    print('=' * 60)
