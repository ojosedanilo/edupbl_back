from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.users.models import User, UserRole
from app.shared.security import get_password_hash


async def seed_test_users(session: AsyncSession):
    """Cria usuários de teste para cada role"""
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
            is_tutor=True,  # ← Professor DT
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
            first_name='João',
            last_name='Responsável',
            role=UserRole.GUARDIAN,
            is_tutor=False,
            is_active=True,
        ),
    ]

    for user in users:
        session.add(user)

    await session.commit()
    print(f'✅ {len(users)} usuários criados com sucesso!')
