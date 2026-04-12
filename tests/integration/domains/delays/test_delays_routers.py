"""
Testes de integração: restrições de data e horário em POST /delays/.

Cobre as regras da tabela de negócio:
  - Porteiro → apenas hoje + apenas nos intervalos
  - Coordenador → apenas hoje, sem restrição de horário
  - Qualquer role → data de 5 dias atrás → 400
"""

from datetime import date, timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token


# ── helpers ──────────────────────────────────────────────────────────────── #


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# ── fixtures ─────────────────────────────────────────────────────────────── #


@pytest_asyncio.fixture
async def porter(session):
    return await _make_user(session, role=UserRole.PORTER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def student(session):
    return await _make_user(session, role=UserRole.STUDENT)


# ── POST /delays/ — restrições de data ───────────────────────────────────── #


def test_porter_can_register_today(client, porter, student):
    """Porteiro no horário do intervalo registrando atraso de hoje → 201."""
    with patch(
        'app.domains.delays.routers.validate_time_is_interval',
        return_value=(True, None),
    ):
        resp = client.post(
            '/delays/',
            headers=_auth(porter),
            json={
                'student_id': student.id,
                'arrival_time': '08:00:00',
                'delay_date': _today(),
            },
        )
    assert resp.status_code == HTTPStatus.CREATED


def test_porter_outside_interval_gets_403(client, porter, student):
    """Porteiro fora do intervalo → 403, independentemente da data."""
    with patch(
        'app.domains.delays.routers.validate_time_is_interval',
        return_value=(False, 'Fora do intervalo.'),
    ):
        resp = client.post(
            '/delays/',
            headers=_auth(porter),
            json={
                'student_id': student.id,
                'arrival_time': '10:00:00',
                'delay_date': _today(),
            },
        )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_porter_cannot_register_yesterday(client, porter, student):
    """Porteiro só pode registrar no próprio dia → ontem retorna 400."""
    with patch(
        'app.domains.delays.routers.validate_time_is_interval',
        return_value=(True, None),
    ):
        resp = client.post(
            '/delays/',
            headers=_auth(porter),
            json={
                'student_id': student.id,
                'arrival_time': '08:00:00',
                'delay_date': _days_ago(1),
            },
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_coordinator_can_register_today_any_time(client, coordinator, student):
    """Coordenador pode registrar atraso de hoje sem restrição de horário."""
    resp = client.post(
        '/delays/',
        headers=_auth(coordinator),
        json={
            'student_id': student.id,
            'arrival_time': '10:00:00',  # fora do intervalo — não importa para coord
            'delay_date': _today(),
        },
    )
    assert resp.status_code == HTTPStatus.CREATED


def test_coordinator_cannot_register_yesterday(client, coordinator, student):
    """Coordenador → atrasos só hoje → ontem retorna 400."""
    resp = client.post(
        '/delays/',
        headers=_auth(coordinator),
        json={
            'student_id': student.id,
            'arrival_time': '08:00:00',
            'delay_date': _days_ago(1),
        },
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_any_role_5_days_ago_gets_400(client, coordinator, student):
    """Data de 5 dias atrás → 400 para qualquer role."""
    resp = client.post(
        '/delays/',
        headers=_auth(coordinator),
        json={
            'student_id': student.id,
            'arrival_time': '08:00:00',
            'delay_date': _days_ago(5),
        },
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert 'mesmo dia' in resp.json()['detail'].lower() or 'próprio dia' in resp.json()['detail'].lower()
