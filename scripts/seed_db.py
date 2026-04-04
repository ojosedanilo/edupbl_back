#!/usr/bin/env python3
"""
Popula o banco de dados com usuários e horários.

Uso
---
sem argumentos            Popula tudo com dados reais (usuários + horários).
                          Equivalente a --real.

--real                    Popula todos os domínios com dados reais.
--real-users              Popula apenas usuários com dados reais (CSVs).
--real-schedules          Popula apenas horários com dados reais (CSVs).

--tests                   Popula todos os domínios com dados de teste.
--tests-users             Popula apenas usuários com dados de teste.
--tests-schedules         (não há seed de teste para horários — exibe aviso)

Exemplos
--------
uv run python scripts/seed_db.py
uv run python scripts/seed_db.py --real
uv run python scripts/seed_db.py --real-users
uv run python scripts/seed_db.py --real-schedules
uv run python scripts/seed_db.py --tests
uv run python scripts/seed_db.py --tests-users

Dados reais
-----------
Usuários lidos de data/usuarios/:
  admins.csv, coordenadores.csv, professores.csv, professores_dt.csv,
  alunos.csv, porteiros.csv, responsaveis.csv

Horários lidos de data/horarios/:
  horario_sala_1.csv … horario_sala_12.csv

Os usuários (professores) devem estar no banco antes de importar horários.

Dados de teste
--------------
Cria 7 usuários com senhas simples (must_change_password=False):
  admin@edupbl.com / admin
  coordenador@edupbl.com / coordenador
  professor@edupbl.com / professor
  professor_dt@edupbl.com / professor_dt
  porteiro@edupbl.com / porteiro
  aluno@edupbl.com / aluno
  responsavel@edupbl.com / responsavel
"""

import argparse
import asyncio
import sys

from app.shared.db.database import SessionLocal
from app.shared.db.seed import seed_real_users, seed_test_users
from app.shared.db.seed_schedules import seed_schedules

# ---------------------------------------------------------------------------
# Helpers de exibição
# ---------------------------------------------------------------------------

SEP = '=' * 60


def _header(title: str) -> None:
    print(f'\n{SEP}')
    print(f'🌱 {title}')
    print(SEP)


def _success() -> None:
    print(f'\n{SEP}')
    print('✨ Seed concluído com sucesso!')
    print(SEP)


def _warn_real_users() -> None:
    print(
        '\n⚠️  Usuários reais criados com must_change_password=True.'
        '\n   Eles serão forçados a trocar a senha no primeiro login.'
        '\n   Endpoint: PATCH /users/me/password'
    )


# ---------------------------------------------------------------------------
# Ações atômicas
# ---------------------------------------------------------------------------


async def _run_real_users(session) -> None:
    print('\n📂 Importando usuários reais...')
    await seed_real_users(session)


async def _run_real_schedules(session) -> None:
    print('\n📅 Importando horários reais...')
    await seed_schedules(session)


async def _run_test_users(session) -> None:
    print('\n👤 Criando usuários de teste...')
    await seed_test_users(session)


def _warn_no_test_schedules() -> None:
    print(
        '\n⚠️  Não há seed de teste para horários.'
        '\n   Use --real-schedules para importar via CSV.'
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description='Popula o banco de dados com usuários e/ou horários.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'sem argumentos  →  equivalente a --real\n'
            '--real          →  todos os domínios reais\n'
            '--tests         →  todos os domínios de teste\n'
            '--real-{dom}    →  apenas aquele domínio real\n'
            '--tests-{dom}   →  apenas aquele domínio de teste\n'
            '\nDomínios disponíveis: users, schedules'
        ),
    )

    # flags de grupo completo
    parser.add_argument(
        '--real',
        action='store_true',
        help='Importa todos os dados reais (usuários + horários via CSV).',
    )
    parser.add_argument(
        '--tests',
        action='store_true',
        help='Cria todos os dados de teste (apenas usuários).',
    )

    # flags por domínio — real
    parser.add_argument(
        '--real-users',
        action='store_true',
        dest='real_users',
        help='Importa apenas usuários reais (CSVs de data/usuarios/).',
    )
    parser.add_argument(
        '--real-schedules',
        action='store_true',
        dest='real_schedules',
        help='Importa apenas horários reais (CSVs de data/horarios/).',
    )

    # flags por domínio — tests
    parser.add_argument(
        '--tests-users',
        action='store_true',
        dest='tests_users',
        help='Cria apenas os usuários de teste (desenvolvimento).',
    )
    parser.add_argument(
        '--tests-schedules',
        action='store_true',
        dest='tests_schedules',
        help='(sem efeito — não há seed de teste para horários)',
    )

    args = parser.parse_args()

    # Determina o que executar
    no_args = not any(vars(args).values())
    run_real_users = no_args or args.real or args.real_users
    run_real_schedules = no_args or args.real or args.real_schedules
    run_test_users = args.tests or args.tests_users
    warn_no_test_schedules = args.tests or args.tests_schedules

    # Conflito: real e tests ao mesmo tempo
    if (run_real_users or run_real_schedules) and (
        run_test_users or warn_no_test_schedules
    ):
        print('❌ Não é possível combinar flags --real e --tests.')
        print('   Execute separadamente se precisar dos dois.')
        sys.exit(1)

    try:
        async with SessionLocal() as session:
            if run_real_users and run_real_schedules:
                _header('Modo: DADOS REAIS COMPLETOS (usuários + horários)')
                await _run_real_users(session)
                await _run_real_schedules(session)
                _warn_real_users()

            elif run_real_users:
                _header('Modo: USUÁRIOS REAIS')
                await _run_real_users(session)
                _warn_real_users()

            elif run_real_schedules:
                _header('Modo: HORÁRIOS REAIS')
                await _run_real_schedules(session)

            elif run_test_users:
                _header('Modo: DADOS DE TESTE')
                await _run_test_users(session)
                if warn_no_test_schedules:
                    _warn_no_test_schedules()

            elif warn_no_test_schedules:
                # --tests-schedules sozinho
                _warn_no_test_schedules()

        _success()

    except Exception as e:
        print(f'\n❌ Erro durante seed: {e}')
        print('\n💡 Possíveis causas:')
        print('   • Banco não foi criado (rode scripts/init_db.py)')
        print('   • Migrations não rodadas (alembic upgrade head)')
        print('   • CSVs em formato incorreto ou ausentes')
        print('   • Professores não importados antes dos horários')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
