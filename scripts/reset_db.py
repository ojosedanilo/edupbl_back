#!/usr/bin/env python3
"""
Script para resetar o banco de dados.

ATENCAO: Apaga todas as tabelas e recria do zero.
Uso: uv run python scripts/reset_db.py
"""

import asyncio

from app.shared.db.database import engine
from app.shared.db.registry import mapper_registry


async def reset_database():
    async with engine.begin() as conn:
        print('Removendo tabelas...')
        await conn.run_sync(mapper_registry.metadata.drop_all)

        print('Criando tabelas...')
        await conn.run_sync(mapper_registry.metadata.create_all)

    print('Banco resetado com sucesso!')


async def main():
    confirm = input('Tem certeza que deseja apagar o banco? (y/n): ')

    if confirm.lower() != 'y':
        print('Operacao cancelada.')
        return

    await reset_database()


if __name__ == '__main__':
    asyncio.run(main())
