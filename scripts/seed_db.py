#!/usr/bin/env python3
"""
Script para popular o banco de dados com usuários e horários.

Modos de uso:

1. Usuários de teste (desenvolvimento):
   uv run python scripts/seed_db.py

   Cria 7 usuários fake
   (must_change_password=False — sem obrigação de trocar senha):
   - admin@edupbl.com (senha: admin)
   - coordenador@edupbl.com (senha: coordenador)
   - professor@edupbl.com (senha: professor)
   - professor_dt@edupbl.com (senha: professor_dt)
   - porteiro@edupbl.com (senha: porteiro)
   - aluno@edupbl.com (senha: aluno)
   - responsavel@edupbl.com (senha: responsavel)

2. Usuários reais (importar CSVs):
   uv run python scripts/seed_db.py --real

   Importa de backend/data/usuarios/:
   - admins.csv
   - coordenadores.csv
   - professores.csv
   - professores_dt.csv
   - alunos.csv
   - porteiros.csv
   - responsaveis.csv

3. Horários (importar CSVs de horário por turma):
   uv run python scripts/seed_db.py --schedules

   Importa de backend/data/horarios/:
   - horario_sala_1.csv  →  1º ano A
   - horario_sala_2.csv  →  1º ano B
   - ...
   - horario_sala_12.csv →  3º ano D

   Os usuários (professores) devem estar no banco antes de importar horários.

4. Ambos (usuários reais + horários):
   uv run python scripts/seed_db.py --real --schedules

5. Tudo (teste + reais + horários):
   uv run python scripts/seed_db.py --all
"""

import argparse
import asyncio
import sys

from app.shared.db.database import SessionLocal
from app.shared.db.seed import seed_real_users, seed_test_users
from app.shared.db.seed_schedules import seed_schedules


async def main():
    """Função principal"""
    # Parse de argumentos
    parser = argparse.ArgumentParser(
        description='Popula banco de dados com usuários e horários'
    )
    parser.add_argument(
        '--real',
        action='store_true',
        help='Importa usuários reais de CSVs em backend/data/',
    )
    parser.add_argument(
        '--schedules',
        action='store_true',
        help='Importa horários de horario_sala_{N}.csv em backend/data/horarios/',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Cria usuários de teste E importa usuários reais E horários',
    )

    args = parser.parse_args()

    try:
        async with SessionLocal() as session:
            # Decide qual seed executar
            if args.all:
                # Tudo: teste + reais + horários
                print('=' * 60)
                print('🌱 Modo: COMPLETO (Teste + Reais + Horários)')
                print('=' * 60)

                print('\n1️⃣  Criando usuários de teste...')
                await seed_test_users(session)

                print('\n2️⃣  Importando usuários reais...')
                await seed_real_users(session)

                print('\n3️⃣  Importando horários...')
                await seed_schedules(session)

            elif args.real and args.schedules:
                # Usuários reais + horários
                print('=' * 60)
                print('🌱 Modo: USUÁRIOS REAIS + HORÁRIOS')
                print('=' * 60)

                print('\n1️⃣  Importando usuários reais...')
                await seed_real_users(session)

                print('\n2️⃣  Importando horários...')
                await seed_schedules(session)

            elif args.real:
                # Apenas usuários reais
                print('=' * 60)
                print('🌱 Modo: USUÁRIOS REAIS (CSVs)')
                print('=' * 60)
                await seed_real_users(session)

            elif args.schedules:
                # Apenas horários
                print('=' * 60)
                print('🌱 Modo: HORÁRIOS (CSVs)')
                print('=' * 60)
                await seed_schedules(session)

            else:
                # Padrão: apenas usuários de teste
                print('=' * 60)
                print('🌱 Modo: USUÁRIOS DE TESTE (Desenvolvimento)')
                print('=' * 60)
                print('\n💡 Use --real para importar usuários de CSVs')
                print('💡 Use --schedules para importar horários de CSVs')
                print('💡 Use --all para criar tudo\n')
                await seed_test_users(session)

        print('\n' + '=' * 60)
        print('✨ Seed concluído com sucesso!')
        print('=' * 60)

        # Instruções pós-seed
        if args.real or args.all:
            print(
                '\n⚠️  IMPORTANTE: Usuários reais foram criados com'
                ' must_change_password=True!'
            )
            print('   Eles serão forçados a trocar a senha no primeiro login.')
            print('   Endpoint de troca: PATCH /users/me/password')

    except Exception as e:
        print(f'\n❌ Erro durante seed: {e}')
        print('\n💡 Possíveis causas:')
        print('   • Banco de dados não foi criado (rode scripts/init_db.py)')
        print('   • Migrations não foram rodadas (rode alembic upgrade head)')
        print('   • CSVs estão em formato incorreto')
        print('   • Professores não foram importados antes dos horários')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
