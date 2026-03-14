#!/usr/bin/env python3
"""
Script para inicializar o banco de dados.

Este script:
1. Cria o banco de dados se não existir
2. Cria o tipo ENUM userrole se não existir
3. Roda as migrations pendentes

Uso: uv run python init_db.py
"""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import settings


async def create_database_if_not_exists():
    """Cria o banco de dados se não existir"""

    # URL sem o nome do banco (conecta no postgres padrão)
    base_url = settings.DATABASE_URL.rsplit('/', 1)[0]
    db_name = settings.DATABASE_URL.rsplit('/', 1)[1]

    # Remove parâmetros de query se houver
    if '?' in db_name:
        db_name = db_name.split('?')[0]

    print(f'📊 Verificando banco de dados: {db_name}')

    # Conecta no banco postgres padrão
    engine = create_async_engine(
        base_url + '/postgres', isolation_level='AUTOCOMMIT'
    )

    try:
        async with engine.connect() as conn:
            # Verifica se banco existe
            result = await conn.execute(
                text('SELECT 1 FROM pg_database WHERE datname = :db_name'),
                {'db_name': db_name},
            )
            exists = result.scalar()

            if not exists:
                print(f'⚠️  Banco de dados não existe. Criando: {db_name}')
                await conn.execute(text(f'CREATE DATABASE {db_name}'))
                print(f'✅ Banco de dados criado: {db_name}')
            else:
                print(f'✅ Banco de dados já existe: {db_name}')

    except Exception as e:
        print(f'❌ Erro ao criar banco de dados: {e}')
        raise
    finally:
        await engine.dispose()


async def create_enum_if_not_exists():
    """Cria o tipo ENUM userrole se não existir"""

    print('🔧 Verificando tipo ENUM userrole...')

    engine = create_async_engine(settings.DATABASE_URL)

    try:
        async with engine.connect() as conn:
            # Verifica se enum existe
            result = await conn.execute(
                text("SELECT 1 FROM pg_type WHERE typname = 'userrole'")
            )
            exists = result.scalar()

            if not exists:
                print('⚠️  Tipo ENUM userrole não existe. Criando...')
                await conn.execute(
                    text(
                        'CREATE TYPE userrole AS ENUM '
                        "('student', 'guardian', 'teacher',"
                        "'coordinator', 'porter', 'admin')"
                    )
                )
                await conn.commit()
                print('✅ Tipo ENUM userrole criado')
            else:
                print('✅ Tipo ENUM userrole já existe')

    except Exception as e:
        print(f'❌ Erro ao criar ENUM: {e}')
        raise
    finally:
        await engine.dispose()


async def main():
    """Função principal"""
    try:
        print('=' * 60)
        print('🚀 Inicializando banco de dados EduPBL')
        print('=' * 60)

        # Passo 1: Criar banco de dados
        await create_database_if_not_exists()

        # Passo 2: Criar ENUM
        await create_enum_if_not_exists()

        # Passo 3: Rodar migrations
        print('\n📦 Rodando migrations...')
        print('Execute: alembic upgrade head')
        print('\n' + '=' * 60)
        print('✨ Inicialização concluída!')
        print('=' * 60)

    except Exception as e:
        print(f'\n❌ Erro durante inicialização: {e}')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
