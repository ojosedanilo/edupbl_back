import asyncio

from app.shared.database import engine
from app.shared.database import Base


async def reset_database():
    async with engine.begin() as conn:
        print('Removendo tabelas...')
        await conn.run_sync(Base.metadata.drop_all)

        print('Criando tabelas...')
        await conn.run_sync(Base.metadata.create_all)

    print('Banco resetado com sucesso!')


async def main():
    confirm = input('Tem certeza que deseja apagar o banco? (y/n): ')

    if confirm.lower() != 'y':
        print('Operação cancelada.')
        return

    await reset_database()


if __name__ == '__main__':
    asyncio.run(main())
