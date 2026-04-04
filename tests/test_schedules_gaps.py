"""
Testes complementares de schedules/ para fechar os gaps de cobertura.

Linhas faltantes identificadas:
  schedules/routers.py  91-108   guardian access (_check_classroom_access CHILD branch)
  schedules/routers.py  249-261  get_current_teacher_by_classroom endpoint
  schedules/routers.py  402-407  list_overrides → branch affects_all=False (classroom_ids)
  schedules/routers.py  498-503  delete_override → branch affects_all=False (classroom_ids)
  rbac/dependencies.py  66       AnyPermissionChecker → 403

Estratégia: cria overrides com affects_all=False e classroom_ids populados para
garantir que os branches de consulta à tabela de associação sejam atingidos.
"""

from http import HTTPStatus
from unittest.mock import patch

import pytest_asyncio

from app.domains.schedules.models import ScheduleSlot
from app.domains.schedules.schemas import Weekday
from app.domains.users.models import Classroom, guardian_student
from app.shared.rbac.roles import UserRole
from app.shared.security import create_access_token
from tests.conftest import _make_user, make_token


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def classroom(session):
    c = Classroom(name='GapRoom_A')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def classroom_b(session):
    c = Classroom(name='GapRoom_B')
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def student(session, classroom):
    return await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )


@pytest_asyncio.fixture
async def guardian(session, student):
    """Responsável com filho vinculado à classroom via guardian_student."""
    g = await _make_user(session, role=UserRole.GUARDIAN)
    await session.execute(
        guardian_student.insert().values(
            guardian_id=g.id, student_id=student.id
        )
    )
    await session.commit()
    await session.refresh(g)
    return g


@pytest_asyncio.fixture
async def slot(session, classroom, teacher):
    s = ScheduleSlot(
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        type='class_period',
        title='Matemática Gap',
        weekday=Weekday.MONDAY,
        period_number=1,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@pytest_asyncio.fixture
async def override_specific(session, classroom, coordinator, client):
    """Override com affects_all=False vinculado a classroom via association table."""
    resp = client.post(
        '/schedules/overrides',
        json={
            'title': 'Override Específico',
            'override_date': '2099-01-15',
            'starts_at': '07:00:00',
            'ends_at': '12:00:00',
            'affects_all': False,
            'classroom_ids': [classroom.id],
        },
        headers=_auth(coordinator),
    )
    assert resp.status_code == HTTPStatus.CREATED
    return resp.json()


# ===========================================================================
# routers.py lines 91-108 — _check_classroom_access CHILD branch
# ===========================================================================


async def test_guardian_with_child_in_class_gets_schedule(
    client, guardian, classroom
):
    """
    lines 91-108: Responsável cujo filho está na turma → 200.
    Garante que o JOIN em guardian_student é executado e retorna resultado.
    """
    resp = client.get(
        f'/schedules/classroom/{classroom.id}',
        headers=_auth(guardian),
    )
    assert resp.status_code == HTTPStatus.OK


async def test_guardian_without_child_in_class_forbidden(
    client, session, classroom
):
    """
    lines 91-108: Responsável sem filhos na turma → 403.
    Garante que o branch `if student_in_class is None: raise 403` é atingido.
    """
    guardian_no_kids = await _make_user(session, role=UserRole.GUARDIAN)
    resp = client.get(
        f'/schedules/classroom/{classroom.id}',
        headers=_auth(guardian_no_kids),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Insufficient permissions'


async def test_guardian_child_in_other_class_forbidden(
    client, session, classroom, classroom_b
):
    """
    lines 91-108: Filho está em classroom_b mas guardian tenta acessar
    classroom → 403 (student_in_class is None para classroom_id errado).
    """
    student_b = await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom_b.id
    )
    guardian_b = await _make_user(session, role=UserRole.GUARDIAN)
    await session.execute(
        guardian_student.insert().values(
            guardian_id=guardian_b.id, student_id=student_b.id
        )
    )
    await session.commit()

    # Tenta acessar classroom A, mas filho está em classroom_b
    resp = client.get(
        f'/schedules/classroom/{classroom.id}',
        headers=_auth(guardian_b),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# routers.py lines 249-261 — get_current_teacher_by_classroom endpoint
# ===========================================================================


async def test_get_current_teacher_endpoint_found(
    client, coordinator, classroom, teacher
):
    """
    lines 249-261: Professor encontrado para a turma → 200 com dados do professor.
    """
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = teacher
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(coordinator),
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['id'] == teacher.id


async def test_get_current_teacher_endpoint_not_found(
    client, coordinator, classroom
):
    """
    lines 249-261: Nenhum professor na turma no momento → 404.
    """
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = None
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(coordinator),
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail'] == 'No teacher in class at this time'


async def test_get_current_teacher_guardian_own_class(
    client, guardian, classroom, teacher
):
    """
    lines 249-261: Guardian com filho na turma pode consultar professor atual → 200.
    """
    with patch('app.domains.schedules.routers.get_current_teacher') as mock_fn:
        mock_fn.return_value = teacher
        resp = client.get(
            f'/schedules/current-teacher/{classroom.id}',
            headers=_auth(guardian),
        )
    assert resp.status_code == HTTPStatus.OK


async def test_get_current_teacher_guardian_other_class_forbidden(
    client, guardian, classroom_b
):
    """
    lines 249-261: Guardian sem filho em classroom_b → 403 antes de consultar teacher.
    """
    resp = client.get(
        f'/schedules/current-teacher/{classroom_b.id}',
        headers=_auth(guardian),
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# routers.py lines 402-407 — list_overrides: branch affects_all=False
# ===========================================================================


async def test_list_overrides_specific_classroom_populates_ids(
    client, coordinator, classroom, override_specific
):
    """
    lines 402-407: GET /overrides com override affects_all=False →
    branch que faz SELECT classroom_id FROM override_classrooms é atingido,
    e classroom_ids é preenchido corretamente na resposta.
    """
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK

    specific_overrides = [
        o for o in resp.json()['overrides'] if not o['affects_all']
    ]
    assert len(specific_overrides) >= 1
    # classroom_ids deve estar populado (não None)
    cids = specific_overrides[0]['classroom_ids']
    assert cids is not None
    assert classroom.id in cids


async def test_list_overrides_affects_all_returns_null_classroom_ids(
    client, coordinator
):
    """
    lines 402-407 (else branch): Override affects_all=True → classroom_ids=None.
    """
    client.post(
        '/schedules/overrides',
        json={
            'title': 'Feriado Nacional',
            'override_date': '2099-09-07',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    resp = client.get('/schedules/overrides', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK

    all_overrides = [o for o in resp.json()['overrides'] if o['affects_all']]
    assert len(all_overrides) >= 1
    assert all_overrides[0]['classroom_ids'] is None


# ===========================================================================
# routers.py lines 498-503 — delete_override: branch affects_all=False
# ===========================================================================


async def test_delete_override_specific_classroom_returns_ids(
    client, coordinator, classroom, override_specific
):
    """
    lines 498-503: DELETE /overrides/{id} com override affects_all=False →
    branch que faz SELECT classroom_id FROM override_classrooms é atingido,
    e classroom_ids é retornado na resposta de deleção.
    """
    oid = override_specific['id']
    resp = client.delete(
        f'/schedules/overrides/{oid}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body['id'] == oid
    assert body['affects_all'] is False
    # classroom_ids deve estar preenchido (não None)
    assert body['classroom_ids'] is not None
    assert classroom.id in body['classroom_ids']


async def test_delete_override_affects_all_returns_null_ids(
    client, coordinator
):
    """
    lines 498-503 (else branch): DELETE override affects_all=True → classroom_ids=None.
    """
    r = client.post(
        '/schedules/overrides',
        json={
            'title': 'Para deletar all',
            'override_date': '2099-10-01',
            'starts_at': '00:00:00',
            'ends_at': '23:59:59',
            'affects_all': True,
        },
        headers=_auth(coordinator),
    )
    oid = r.json()['id']
    resp = client.delete(
        f'/schedules/overrides/{oid}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['classroom_ids'] is None


# ===========================================================================
# rbac/dependencies.py line 66 — AnyPermissionChecker → 403
# ===========================================================================


async def test_any_permission_checker_raises_403(client, session):
    """
    rbac/dependencies.py line 66: AnyPermissionChecker dispara HTTPException(403)
    quando o usuário não possui NENHUMA das permissões do conjunto.

    GET /schedules/teacher/{id} exige AnyPermissionChecker({
        SCHEDULES_VIEW_ALL, SCHEDULES_VIEW_OWN
    }).
    Guardiões têm SCHEDULES_VIEW_CHILD mas NÃO têm VIEW_ALL nem VIEW_OWN
    → __call__ chega ao raise HTTPException(403, 'Insufficient permissions').
    """
    guardian = await _make_user(session, role=UserRole.GUARDIAN)
    tok = create_access_token(data={'sub': guardian.email})
    resp = client.get(
        '/schedules/teacher/1',
        headers={'Authorization': f'Bearer {tok}'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()['detail'] == 'Insufficient permissions'


# ===========================================================================
# routers.py line 108 — _check_classroom_access: raise final (sem nenhuma permissão)
# ===========================================================================
#
# O AnyPermissionChecker na rota HTTP bloqueia com 403 ANTES de chamar
# _check_classroom_access, então o raise final (linha 108) só é atingido
# chamando a função diretamente com um usuário que não tenha VIEW_ALL,
# VIEW_OWN nem VIEW_CHILD — como um objeto mock com role sem essas permissões.


import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.domains.schedules.routers import _check_classroom_access
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.helpers import get_user_permissions


@pytest.mark.asyncio
async def test_check_classroom_access_no_permission_raises_403(session):
    """
    routers.py line 108: usuário sem VIEW_ALL, VIEW_OWN nem VIEW_CHILD →
    _check_classroom_access cai no raise final → HTTPException(403).

    Não é possível atingir via HTTP porque AnyPermissionChecker intercepta antes.
    Testamos a função diretamente com um User mock sem nenhuma das permissões.
    """
    # Cria usuário real no banco mas sem permissões de schedule
    # (role STUDENT tem VIEW_OWN — não serve; precisamos de role sem nenhuma das 3)
    # Usamos MagicMock para simular um User com role vazia de permissões
    user = MagicMock()
    user.role = 'fake_role_sem_permissoes'
    user.is_tutor = False
    user.classroom_id = None

    # get_user_permissions retorna conjunto vazio para role desconhecida
    # mas _check_classroom_access usa require_permission que chama helpers diretamente.
    # Precisamos que user_has_permission retorne False para todas as 3.
    # Isso acontece naturalmente: role 'fake_role_sem_permissoes' não está em
    # ROLE_PERMISSIONS, então get_user_permissions retorna só _BASE_PERMISSIONS
    # que não inclui nenhuma das três permissões de schedule.

    with pytest.raises(HTTPException) as exc_info:
        await _check_classroom_access(user, classroom_id=1, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == 'Insufficient permissions'
