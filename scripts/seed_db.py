#!/usr/bin/env python3
"""
Script para popular o banco de dados com usuários de teste.

Cria 7 usuários (um de cada role):
- admin@edupbl.com (senha: admin)
- coordenador@edupbl.com (senha: coordenador)
- professor@edupbl.com (senha: professor)
- professor_dt@edupbl.com (senha: professor_dt)
- porteiro@edupbl.com (senha: porteiro)
- aluno@edupbl.com (senha: aluno)
- responsavel@edupbl.com (senha: responsavel)

Uso: uv run python seed_db.py
"""

import asyncio
import sys

from app.shared.database import SessionLocal
from app.shared.seed import seed_test_users


async def main():
    """Função principal"""
    try:
        print('=' * 60)
        print('🌱 Populando banco de dados com usuários de teste')
        print('=' * 60)

        async with SessionLocal() as session:
            await seed_test_users(session)

        print('=' * 60)
        print('✨ Seed concluído com sucesso!')
        print('=' * 60)

    except Exception as e:
        print(f'\n❌ Erro durante seed: {e}')
        print('💡 Dica: Talvez os usuários já existam no banco.')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
