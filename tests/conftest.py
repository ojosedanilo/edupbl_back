import inspect  # noqa: F401, I001


from contextlib import contextmanager  # noqa: E402, I001
from datetime import datetime  # noqa: E402

import factory  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.main import app  # noqa: E402
from app.shared.db.registry import mapper_registry  # noqa: E402, I001

# import app.shared.db.models  # noqa: E402, I001
from app.domains.users.models import User  # noqa: E402, I001
from app.domains.occurrences.models import Occurrence  # noqa: E402, F401, I001
from app.shared.db.database import get_session  # noqa: E402, I001
from app.shared.rbac.roles import UserRole  # noqa: E402, I001
from app.shared.security import (  # noqa: E402, I001
    create_access_token,
    create_refresh_token,
    get_password_hash,
)

# --------------------------------------------------------------------------- #
# Engine compartilhada entre session de teste e requests HTTP                 #
# --------------------------------------------------------------------------- #
#
# Arquitetura:
#   engine  ->  cria as tabelas, compartilhada por TODOS do mesmo teste
#   session ->  AsyncSession para o codigo do teste (fixtures, _make_user, etc.)
#   client  ->  TestClient cujo get_session abre uma NOVA AsyncSession
#               da mesma engine a cada request
#
# Por que nova sessao por request?
# O TestClient despacha requests em uma thread/event-loop separada (anyio).
# Compartilhar o mesmo objeto AsyncSession entre a corrotina do teste e
# a corrotina do request causa "another operation is in progress" no aiosqlite.
# Com StaticPool, todas as conexoes apontam para o mesmo banco em memoria,
# entao dados commitados pelo fixture ficam visiveis para o request.
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture(loop_scope='function')
async def engine():
    _engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
        # echo=True,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.create_all)

    yield _engine

    async with _engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.drop_all)

    await _engine.dispose()


@pytest_asyncio.fixture(loop_scope='function')
async def session(engine):
    async with AsyncSession(engine, expire_on_commit=False) as _session:
        yield _session


@pytest_asyncio.fixture(loop_scope='function')
async def client(engine):
    async def get_session_override():
        async with AsyncSession(engine, expire_on_commit=False) as _session:
            yield _session

    print(app, type(app))
    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as _client:
        yield _client

    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Helper de tempo mockado                                                     #
# --------------------------------------------------------------------------- #


@contextmanager
def _mock_db_time(*, model, time=datetime(2024, 1, 1)):
    def fake_time_handler(mapper, connection, target):
        if hasattr(target, 'created_at'):
            target.created_at = time
        if hasattr(target, 'updated_at'):
            target.updated_at = time

    event.listen(model, 'before_insert', fake_time_handler)

    yield time

    event.remove(model, 'before_insert', fake_time_handler)


@pytest.fixture
def mock_db_time():
    return _mock_db_time


# --------------------------------------------------------------------------- #
# Factory de usuario                                                          #
# --------------------------------------------------------------------------- #


class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'test{n}')
    first_name = factory.LazyAttribute(lambda obj: f'{obj.username}_first')
    last_name = factory.LazyAttribute(lambda obj: f'{obj.username}_last')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    password = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    role = UserRole.STUDENT
    is_tutor = False
    is_active = True
    must_change_password = False


# --------------------------------------------------------------------------- #
# Helper interno de criacao de usuario                                        #
# --------------------------------------------------------------------------- #


async def _make_user(session, **kwargs):
    """Cria e persiste um usuario, expondo clean_password."""
    password = kwargs.pop('clean_password', 'testtest')
    user = UserFactory(password=get_password_hash(password), **kwargs)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = password
    return user


# --------------------------------------------------------------------------- #
# Fixtures genericas                                                          #
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def user(session):
    return await _make_user(session)


@pytest_asyncio.fixture
async def other_user(session):
    return await _make_user(session)


@pytest_asyncio.fixture
async def student_user(session):
    return await _make_user(session, role=UserRole.STUDENT, is_tutor=False)


@pytest_asyncio.fixture
async def guardian_user(session):
    return await _make_user(session, role=UserRole.GUARDIAN, is_tutor=False)


@pytest_asyncio.fixture
async def teacher_user(session):
    return await _make_user(session, role=UserRole.TEACHER, is_tutor=False)


@pytest_asyncio.fixture
async def tutor_user(session):
    """Professor Diretor de Turma."""
    return await _make_user(session, role=UserRole.TEACHER, is_tutor=True)


@pytest_asyncio.fixture
async def coordinator_user(session):
    return await _make_user(session, role=UserRole.COORDINATOR, is_tutor=False)


@pytest_asyncio.fixture
async def admin_user(session):
    return await _make_user(session, role=UserRole.ADMIN, is_tutor=False)


# --------------------------------------------------------------------------- #
# Tokens                                                                      #
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def token(user):
    return create_access_token(data={'sub': user.email})


@pytest_asyncio.fixture
async def refresh_token(user):
    return create_refresh_token(data={'sub': user.email})


def make_token(u):
    """Gera access token para qualquer usuario - helper nos testes."""
    return create_access_token(data={'sub': u.email})
