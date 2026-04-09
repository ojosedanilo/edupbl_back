"""
Testes de delays/routers.py.

Endpoints:
  POST   /delays/              — registrar atraso
  GET    /delays/              — listar todos (com filtros)
  GET    /delays/pending       — listar pendentes
  GET    /delays/me            — atrasos do aluno logado
  GET    /delays/{id}          — detalhe de um atraso
  PATCH  /delays/{id}/approve  — aprovar entrada
  PATCH  /delays/{id}/reject   — rejeitar entrada
  PATCH  /delays/{id}/undo     — desfazer decisão (dentro da janela)
"""

from datetime import datetime, time, timedelta
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.domains.delays.enums import DelayStatusEnum
from app.domains.delays.models import Delay
from app.domains.delays.periods import UNDO_WINDOW_MINUTES
from app.domains.delays.routers import get_delay
from app.domains.schedules.enums import PeriodTypeEnum
from app.domains.schedules.periods import PERIODS
from app.domains.users.models import Classroom, guardian_student
from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token


def _block_starts() -> list[time]:
    """
    Retorna os horários de início de cada bloco de aulas do dia, derivados
    diretamente de PERIODS (a fonte de verdade do horário escolar).

    Um "início de bloco" é a primeira aula após um intervalo (ou a primeira
    aula do dia). Esses são os únicos valores que get_expected_time() pode
    retornar — alunos que chegam atrasados são referenciados ao início do
    bloco em que deveriam estar, não à aula individual.

    Usar esta função nos testes garante que, se os horários forem alterados
    em schedules/periods.py, os testes se adaptam automaticamente sem
    precisar atualizar strings hardcoded.

    Com a configuração padrão os blocos são:
      07:30  (início do dia)
      09:30  (após intervalo do lanche)
      13:20  (após almoço)
      15:20  (após intervalo da tarde)
    """
    periods = PERIODS.periods
    starts = []
    for i, p in enumerate(periods):
        if p.type != PeriodTypeEnum.CLASS_PERIOD:
            continue
        if i == 0 or periods[i - 1].type != PeriodTypeEnum.CLASS_PERIOD:
            starts.append(p.start)
    return starts


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


# =========================================================================== #
# Fixtures                                                                     #
# =========================================================================== #


@pytest_asyncio.fixture
async def porter(session):
    return await _make_user(session, role=UserRole.PORTER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def student(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def other_student(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER, is_tutor=False)


@pytest_asyncio.fixture
async def classroom(session):
    cls = Classroom(name='3A')
    session.add(cls)
    await session.commit()
    await session.refresh(cls)
    return cls


@pytest_asyncio.fixture
async def tutor(session, classroom):
    """Professor DT vinculado à turma 3A."""
    return await _make_user(
        session,
        role=UserRole.TEACHER,
        is_tutor=True,
        classroom_id=classroom.id,
    )


@pytest_asyncio.fixture
async def student_in_class(session, classroom):
    """Aluno da turma 3A."""
    return await _make_user(
        session, role=UserRole.STUDENT, classroom_id=classroom.id
    )


@pytest_asyncio.fixture
async def student_other_class(session):
    """Aluno de outra turma (sem turma vinculada aqui)."""
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def guardian(session, student):
    """Responsável com student como filho."""
    g = await _make_user(session, role=UserRole.GUARDIAN)
    await session.execute(
        guardian_student.insert().values(
            guardian_id=g.id, student_id=student.id
        )
    )
    await session.commit()
    return g


@pytest_asyncio.fixture
async def delay_pending(client, porter, student):
    """Cria via HTTP para garantir que session e client compartilhem o banco."""
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '07:45:00'},
    )
    assert resp.status_code == HTTPStatus.CREATED
    return SimpleNamespace(**resp.json())


@pytest_asyncio.fixture
async def delay_db(session, porter, student):
    """Cria diretamente no banco — para testes que não precisam do client."""
    from datetime import time

    delay = Delay(
        student_id=student.id,
        recorded_by_id=porter.id,
        arrival_time=time(7, 45),
        delay_minutes=15,
    )
    session.add(delay)
    await session.commit()
    await session.refresh(delay)
    return delay


# =========================================================================== #
# POST /delays/ — Registrar atraso                                            #
# =========================================================================== #


def test_create_delay_returns_full_object(client, porter, student):
    """POST bem-sucedido → 201 com todos os campos preenchidos."""
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '07:45:00'},
    )
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['id'] is not None
    assert data['student_id'] == student.id
    assert data['recorded_by_id'] == porter.id
    assert data['approved_by_id'] is None
    assert data['status'] == DelayStatusEnum.PENDING
    assert data['arrival_time'] == '07:45:00'
    # expected_time deve ser o início do primeiro bloco do dia
    first_block = _block_starts()[0]
    assert data['expected_time'] == first_block.strftime('%H:%M:%S')


def test_create_delay_calculates_delay_minutes(client, porter, student):
    """delay_minutes deve ser a diferença em relação ao expected_time do bloco."""
    arrival = time(7, 50)
    first_block = _block_starts()[0]
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={
            'student_id': student.id,
            'arrival_time': arrival.strftime('%H:%M:%S'),
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    expected_minutes = int(
        (
            datetime.combine(datetime.today(), arrival)
            - datetime.combine(datetime.today(), first_block)
        ).total_seconds()
        // 60
    )
    assert resp.json()['delay_minutes'] == expected_minutes


def test_create_delay_expected_time_from_period(client, porter, student):
    """expected_time deve refletir o início do bloco correto para o horário de chegada."""
    # Usa o segundo bloco do dia (pós-intervalo da manhã) como referência
    blocks = _block_starts()
    second_block = blocks[1]  # ex: 09:30 na configuração padrão
    # Chega 25 minutos após o início do bloco
    arrival = time(second_block.hour, second_block.minute + 25)
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={
            'student_id': student.id,
            'arrival_time': arrival.strftime('%H:%M:%S'),
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['expected_time'] == second_block.strftime('%H:%M:%S')
    expected_minutes = int(
        (
            datetime.combine(datetime.today(), arrival)
            - datetime.combine(datetime.today(), second_block)
        ).total_seconds()
        // 60
    )
    assert data['delay_minutes'] == expected_minutes


def test_create_delay_with_reason(client, porter, student):
    """Motivo opcional deve ser salvo quando informado."""
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={
            'student_id': student.id,
            'arrival_time': '08:05:00',
            'reason': 'Trânsito na Av. Principal',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()['reason'] == 'Trânsito na Av. Principal'


def test_create_delay_student_not_found(client, porter):
    """Aluno inexistente → 404."""
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': 99999, 'arrival_time': '08:00:00'},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_create_delay_user_not_student(client, porter, coordinator):
    """Registrar atraso para um não-aluno → 422."""
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': coordinator.id, 'arrival_time': '08:00:00'},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_delay_duplicate_same_day(
    client, porter, student, delay_pending
):
    """Segundo atraso no mesmo dia para o mesmo aluno → 409."""
    resp = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '09:00:00'},
    )
    assert resp.status_code == HTTPStatus.CONFLICT


# --------------------------------------------------------------------------- #
# Permissões — POST                                                           #
# --------------------------------------------------------------------------- #


def test_create_delay_student_cannot_register(client, student, other_student):
    """Aluno não tem permissão de registrar atraso → 403."""
    resp = client.post(
        '/delays/',
        headers=_auth(student),
        json={'student_id': other_student.id, 'arrival_time': '08:00:00'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_create_delay_teacher_cannot_register(client, teacher, student):
    """Professor não tem DELAYS_CREATE → 403."""
    resp = client.post(
        '/delays/',
        headers=_auth(teacher),
        json={'student_id': student.id, 'arrival_time': '08:00:00'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# =========================================================================== #
# GET /delays/ — Listar todos                                                 #
# =========================================================================== #


def test_list_all_delays_coordinator(client, coordinator, delay_pending):
    """Coordenador pode listar todos os atrasos."""
    resp = client.get('/delays/', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['delays']) == 1


def test_list_all_delays_porter(client, porter, delay_pending):
    """Porteiro pode listar todos os atrasos."""
    resp = client.get('/delays/', headers=_auth(porter))
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()['delays']) == 1


def test_list_all_delays_student_forbidden(client, student):
    """Aluno não tem DELAYS_VIEW_ALL → 403."""
    resp = client.get('/delays/', headers=_auth(student))
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_list_all_delays_filter_by_status(
    client, coordinator, porter, student, other_student
):
    """Filtro ?status retorna apenas os atrasos com aquele status."""
    # Cria um atraso pendente
    client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '08:00:00'},
    )
    # Cria outro atraso e aprova
    r = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': other_student.id, 'arrival_time': '08:05:00'},
    )
    delay_id = r.json()['id']
    client.patch(f'/delays/{delay_id}/approve', headers=_auth(coordinator))

    resp = client.get('/delays/?status=PENDING', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    delays = resp.json()['delays']
    assert all(d['status'] == 'PENDING' for d in delays)
    assert len(delays) == 1


# =========================================================================== #
# GET /delays/pending                                                         #
# =========================================================================== #


def test_list_pending_delays_returns_only_pending(
    client, coordinator, porter, student, other_student
):
    """GET /delays/pending retorna apenas os PENDING."""
    # Cria dois atrasos
    r1 = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '08:00:00'},
    )
    r2 = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': other_student.id, 'arrival_time': '08:05:00'},
    )

    # Aprova o primeiro
    client.patch(
        f'/delays/{r1.json()["id"]}/approve', headers=_auth(coordinator)
    )

    resp = client.get('/delays/pending', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    delays = resp.json()['delays']
    assert len(delays) == 1
    assert delays[0]['id'] == r2.json()['id']
    assert delays[0]['status'] == 'PENDING'


def test_list_pending_delays_porter_forbidden(client, porter):
    """Porteiro não tem DELAYS_REVIEW → 403 no /pending."""
    resp = client.get('/delays/pending', headers=_auth(porter))
    assert resp.status_code == HTTPStatus.FORBIDDEN


# =========================================================================== #
# GET /delays/me                                                              #
# =========================================================================== #


def test_list_my_delays_student_sees_own(
    client, porter, student, other_student
):
    """Aluno só vê os próprios atrasos em /delays/me."""
    client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '08:00:00'},
    )
    client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': other_student.id, 'arrival_time': '08:05:00'},
    )

    resp = client.get('/delays/me', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    delays = resp.json()['delays']
    assert len(delays) == 1
    assert delays[0]['student_id'] == student.id


def test_list_my_delays_coordinator_forbidden(client, coordinator):
    """Coordenador não tem DELAYS_VIEW_OWN → 403."""
    # Na prática o coordenador TEM a permissão (recebe {*SystemPermissions}).
    # Testamos com guardian que não tem DELAYS_VIEW_OWN.
    pass  # removido — ver test_list_my_delays_guardian_forbidden abaixo


def test_list_my_delays_guardian_forbidden(client, guardian):
    """Responsável não tem DELAYS_VIEW_OWN → 403."""
    resp = client.get('/delays/me', headers=_auth(guardian))
    assert resp.status_code == HTTPStatus.FORBIDDEN


# =========================================================================== #
# GET /delays/{id} — Detalhe com regras de ownership                         #
# =========================================================================== #


def test_get_delay_coordinator_sees_any(client, coordinator, delay_pending):
    """Coordenador pode ver qualquer atraso."""
    resp = client.get(
        f'/delays/{delay_pending.id}', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK


def test_get_delay_porter_sees_any(client, porter, delay_pending):
    """Porteiro pode ver qualquer atraso."""
    resp = client.get(f'/delays/{delay_pending.id}', headers=_auth(porter))
    assert resp.status_code == HTTPStatus.OK


def test_get_delay_student_sees_own(client, student, delay_pending):
    """Aluno pode ver o próprio atraso."""
    resp = client.get(f'/delays/{delay_pending.id}', headers=_auth(student))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['student_id'] == student.id


def test_get_delay_student_cannot_see_other(
    client, other_student, delay_pending
):
    """Aluno não pode ver atraso de outro aluno → 403."""
    resp = client.get(
        f'/delays/{delay_pending.id}', headers=_auth(other_student)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_get_delay_guardian_sees_child(client, guardian, delay_pending):
    """Responsável pode ver atraso do próprio filho."""
    resp = client.get(f'/delays/{delay_pending.id}', headers=_auth(guardian))
    assert resp.status_code == HTTPStatus.OK


def test_get_delay_guardian_cannot_see_other_student(
    client, session, porter, other_student
):
    """Responsável não pode ver atraso de aluno que não é filho → 403."""
    # Cria um responsável SEM vínculo com other_student
    import asyncio

    unrelated_guardian = asyncio.get_event_loop().run_until_complete(
        _make_user(session, role=UserRole.GUARDIAN)
    )
    # Cria o atraso para other_student
    r = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': other_student.id, 'arrival_time': '08:00:00'},
    )
    resp = client.get(
        f'/delays/{r.json()["id"]}', headers=_auth(unrelated_guardian)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_get_delay_tutor_sees_own_classroom(
    client, tutor, porter, student_in_class
):
    """Professor DT pode ver atraso de aluno da própria turma."""
    r = client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student_in_class.id, 'arrival_time': '08:00:00'},
    )
    resp = client.get(f'/delays/{r.json()["id"]}', headers=_auth(tutor))
    assert resp.status_code == HTTPStatus.OK


def test_get_delay_tutor_cannot_see_other_classroom(
    client, tutor, porter, student_other_class
):
    """Professor DT não pode ver atraso de aluno de outra turma → 403."""
    r = client.post(
        '/delays/',
        headers=_auth(porter),
        json={
            'student_id': student_other_class.id,
            'arrival_time': '08:00:00',
        },
    )
    resp = client.get(f'/delays/{r.json()["id"]}', headers=_auth(tutor))
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_get_delay_teacher_not_tutor_forbidden(client, teacher, delay_pending):
    """Professor que não é DT não tem nenhuma permissão de visualização → 403."""
    resp = client.get(f'/delays/{delay_pending.id}', headers=_auth(teacher))
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_get_delay_not_found(client, coordinator):
    """ID inexistente → 404."""
    resp = client.get('/delays/99999', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.NOT_FOUND


# =========================================================================== #
# PATCH /delays/{id}/approve                                                  #
# =========================================================================== #


def test_approve_delay_sets_approved(client, coordinator, delay_pending):
    """Aprovação muda status para APPROVED e preenche approved_by_id."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['status'] == 'APPROVED'
    assert data['approved_by_id'] == coordinator.id


def test_approve_delay_already_decided(client, coordinator, delay_pending):
    """Aprovar um atraso já decidido → 409."""
    client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )
    resp = client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.CONFLICT


def test_approve_delay_teacher_forbidden(client, teacher, delay_pending):
    """Professor não tem DELAYS_REVIEW → 403."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(teacher)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_approve_delay_porter_forbidden(client, porter, delay_pending):
    """Porteiro não tem DELAYS_REVIEW → 403."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(porter)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# =========================================================================== #
# PATCH /delays/{id}/reject                                                   #
# =========================================================================== #


def test_reject_delay_sets_rejected(client, coordinator, delay_pending):
    """Rejeição muda status para REJECTED e preenche rejection_reason."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={'rejection_reason': 'Responsável não atendeu'},
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['status'] == 'REJECTED'
    assert data['approved_by_id'] == coordinator.id
    assert data['rejection_reason'] == 'Responsável não atendeu'


def test_reject_delay_requires_reason(client, coordinator, delay_pending):
    """Rejeitar sem rejection_reason → 422 (campo obrigatório)."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_reject_delay_already_decided(client, coordinator, delay_pending):
    """Rejeitar um atraso já decidido → 409."""
    client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={'rejection_reason': 'Primeiro motivo'},
    )
    resp = client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={'rejection_reason': 'Tentativa repetida'},
    )
    assert resp.status_code == HTTPStatus.CONFLICT


def test_reject_approved_delay(client, coordinator, delay_pending):
    """Tentar rejeitar um atraso já aprovado → 409."""
    client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )
    resp = client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={'rejection_reason': 'Tentativa de mudar decisão'},
    )
    assert resp.status_code == HTTPStatus.CONFLICT


def test_reject_delay_porter_forbidden(client, porter, delay_pending):
    """Porteiro não tem DELAYS_REVIEW → 403."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(porter),
        json={'rejection_reason': 'Motivo'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


# =========================================================================== #
# PATCH /delays/{id}/undo — Janela de desfazer                               #
# =========================================================================== #


def test_undo_approved_delay_within_window(client, coordinator, delay_pending):
    """Desfazer aprovação dentro da janela → volta para PENDING."""
    client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )

    resp = client.patch(
        f'/delays/{delay_pending.id}/undo', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['status'] == 'PENDING'
    assert data['approved_by_id'] is None
    assert data['rejection_reason'] is None


def test_undo_rejected_delay_within_window(client, coordinator, delay_pending):
    """Desfazer rejeição dentro da janela → volta para PENDING."""
    client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={'rejection_reason': 'Motivo temporário'},
    )

    resp = client.patch(
        f'/delays/{delay_pending.id}/undo', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['status'] == 'PENDING'
    assert data['rejection_reason'] is None


def test_undo_pending_delay_conflict(client, coordinator, delay_pending):
    """Tentar desfazer um atraso que ainda é PENDING → 409."""
    resp = client.patch(
        f'/delays/{delay_pending.id}/undo', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.CONFLICT


async def test_undo_expired_window(
    client, session, coordinator, delay_pending
):
    """Undo após a janela expirada → 409."""
    # Aprova o atraso
    client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )

    # Simula que a decisão foi tomada além da janela configurada
    from sqlalchemy import select, update

    await session.execute(
        update(Delay)
        .where(Delay.id == delay_pending.id)
        .values(
            updated_at=datetime.utcnow()
            - timedelta(minutes=UNDO_WINDOW_MINUTES + 1)
        )
    )
    await session.commit()

    resp = client.patch(
        f'/delays/{delay_pending.id}/undo', headers=_auth(coordinator)
    )
    assert resp.status_code == HTTPStatus.CONFLICT


def test_undo_porter_forbidden(client, porter, coordinator, delay_pending):
    """Porteiro não tem DELAYS_REVIEW → 403 no undo."""
    client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )
    resp = client.patch(
        f'/delays/{delay_pending.id}/undo', headers=_auth(porter)
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_undo_after_undo_allows_new_decision(
    client, coordinator, delay_pending
):
    """Após desfazer, é possível tomar uma nova decisão."""
    client.patch(
        f'/delays/{delay_pending.id}/approve', headers=_auth(coordinator)
    )
    client.patch(
        f'/delays/{delay_pending.id}/undo', headers=_auth(coordinator)
    )

    # Agora rejeita
    resp = client.patch(
        f'/delays/{delay_pending.id}/reject',
        headers=_auth(coordinator),
        json={'rejection_reason': 'Decisão revisada'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == 'REJECTED'


# =========================================================================== #
# GET /delays/ — Filtro por data                                              #
# =========================================================================== #


def test_list_all_delays_filter_by_date(
    client, coordinator, porter, student, other_student
):
    """Filtro ?date retorna apenas os atrasos daquela data."""
    from datetime import date, time
    from sqlalchemy.ext.asyncio import AsyncSession
    import asyncio
    from app.shared.db.database import get_session

    # Cria um atraso hoje via HTTP (delay_date será date.today())
    client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '08:00:00'},
    )

    today_str = date.today().isoformat()
    resp = client.get(f'/delays/?date={today_str}', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    delays = resp.json()['delays']
    assert len(delays) == 1
    assert delays[0]['student_id'] == student.id


def test_list_all_delays_filter_by_date_no_match(
    client, coordinator, porter, student
):
    """Filtro ?date com data sem atrasos retorna lista vazia."""
    # Cria um atraso hoje
    client.post(
        '/delays/',
        headers=_auth(porter),
        json={'student_id': student.id, 'arrival_time': '08:00:00'},
    )

    # Filtra por data que não tem nenhum atraso
    resp = client.get('/delays/?date=2000-01-01', headers=_auth(coordinator))
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['delays'] == []


# =========================================================================== #
# GET /delays/{id} — Branch "qualquer outro caso não coberto"                #
# =========================================================================== #


@pytest.mark.anyio
async def test_get_delay_uncovered_role_raises_forbidden():
    """
    Branch final de get_delay() — raise HTTPException(FORBIDDEN).

    Esse branch é atingido quando o usuário tem pelo menos uma das permissões
    DELAYS_VIEW_* (passou pelo AnyPermissionChecker), mas não é nenhum dos
    roles tratados explicitamente (COORDINATOR, ADMIN, PORTER, STUDENT,
    GUARDIAN, TEACHER). Testado diretamente na função para forçar o caminho
    sem precisar de um role real no banco.
    """
    # Cria um delay fake com student_id arbitrário
    fake_delay = MagicMock()
    fake_delay.student_id = 42

    # Usuário com role que não cai em nenhum dos ifs (ex: valor arbitrário)
    fake_user = MagicMock()
    fake_user.role = 'nonexistent_role'
    fake_user.id = 99

    # Session que devolve o delay sem precisar de banco real
    fake_session = AsyncMock()
    fake_session.scalar = AsyncMock(return_value=fake_delay)

    with pytest.raises(Exception) as exc_info:
        await get_delay(
            session=fake_session,
            current_user=fake_user,
            delay_id=1,
        )

    from fastapi import HTTPException

    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == HTTPStatus.FORBIDDEN


# =========================================================================== #
# schedules/enums.py — PeriodTypeEnum.default_title e is_classroom_slot      #
# =========================================================================== #


def test_period_type_default_title_all_values():
    """default_title retorna o título correto para cada tipo de período."""
    assert PeriodTypeEnum.CLASS_PERIOD.default_title == 'Aula'
    assert PeriodTypeEnum.PLANNING.default_title == 'Planejamento'
    assert PeriodTypeEnum.FREE.default_title == 'Folga'
    assert PeriodTypeEnum.SNACK_BREAK.default_title == 'Intervalo'
    assert PeriodTypeEnum.LUNCH_BREAK.default_title == 'Almoço'


def test_period_type_is_classroom_slot_true_cases():
    """is_classroom_slot retorna True para CLASS_PERIOD, SNACK_BREAK e LUNCH_BREAK."""
    assert PeriodTypeEnum.CLASS_PERIOD.is_classroom_slot is True
    assert PeriodTypeEnum.SNACK_BREAK.is_classroom_slot is True
    assert PeriodTypeEnum.LUNCH_BREAK.is_classroom_slot is True


def test_period_type_is_classroom_slot_false_cases():
    """is_classroom_slot retorna False para PLANNING e FREE."""
    assert PeriodTypeEnum.PLANNING.is_classroom_slot is False
    assert PeriodTypeEnum.FREE.is_classroom_slot is False
