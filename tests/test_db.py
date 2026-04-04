"""
Testes de integracao com o banco de dados (SQLite em memoria).
"""

from sqlalchemy import select

from app.domains.users.models import User
from app.shared.rbac.roles import UserRole


async def test_create_user(session, mock_db_time):
    with mock_db_time(model=User) as time:
        new_user = User(
            username='alice',
            first_name='alice',
            last_name='liddell',
            password='secret',
            email='teste@test',
            role=UserRole.TEACHER,
            is_tutor=True,
        )
        session.add(new_user)
        await session.commit()

    user = await session.scalar(select(User).where(User.username == 'alice'))

    # Verifica campos escalares individualmente — asdict() não e usado porque
    # o modelo agora tem relationship fields (students, guardians, classroom)
    # que não devem (e não podem) ser serializados por asdict() neste contexto.
    assert user.id == 1
    assert user.username == 'alice'
    assert user.password == 'secret'
    assert user.first_name == 'alice'
    assert user.last_name == 'liddell'
    assert user.email == 'teste@test'
    assert user.role == UserRole.TEACHER
    assert user.is_active is True
    assert user.is_tutor is True
    assert user.must_change_password is False
    assert user.classroom_id is None
    assert user.created_at == time
    assert user.updated_at == time
