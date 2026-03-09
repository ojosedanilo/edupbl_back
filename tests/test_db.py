from dataclasses import asdict

import pytest
from sqlalchemy import select

from app.domains.users.models import User
from app.shared.rbac.roles import UserRole


@pytest.mark.asyncio
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

    assert asdict(user) == {
        'id': 1,
        'username': 'alice',
        'password': 'secret',
        'first_name': 'alice',
        'last_name': 'liddell',
        'email': 'teste@test',
        'role': UserRole.TEACHER,
        'is_active': True,
        'is_tutor': True,
        'created_at': time,
        'updated_at': time,
    }
