import importlib
from http import HTTPStatus
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main_module

# ---------------------------------------------------------------------------
# GET / — health check
# ---------------------------------------------------------------------------


def test_root_retorna_ola_mundo(client):
    response = client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'Olá Mundo!'


def test_root_retorna_environment(client):
    response = client.get('/')

    data = response.json()
    assert 'environment' in data
    assert isinstance(data['environment'], str)


def test_root_retorna_database_status_online_quando_banco_disponivel(client):
    """Banco SQLite em memória do conftest deve estar acessível."""
    response = client.get('/')

    assert response.json()['database_status'] == 'online'


def test_root_retorna_database_status_offline_quando_banco_falha(client):
    """Simula falha de conectividade — database_status deve ser 'offline'."""

    async def _session_que_falha():
        raise Exception('conexão recusada')
        yield  # torna função geradora

    with patch('app.main.get_session', return_value=_session_que_falha()):
        response = client.get('/')

    assert response.json()['database_status'] == 'offline'


def test_root_retorna_database_url(client):
    response = client.get('/')

    data = response.json()
    assert 'database_url' in data
    assert isinstance(data['database_url'], str)
    assert len(data['database_url']) > 0


# ---------------------------------------------------------------------------
# Documentação — desabilitada em produção
# ---------------------------------------------------------------------------


def test_docs_acessivel_em_development(client):
    """/docs deve responder 200 no ambiente de teste (development)."""
    response = client.get('/docs')
    assert response.status_code == HTTPStatus.OK


def test_redoc_acessivel_em_development(client):
    """/redoc deve responder 200 no ambiente de teste (development)."""
    response = client.get('/redoc')
    assert response.status_code == HTTPStatus.OK


def test_docs_desabilitado_em_production():
    """/docs deve retornar 404 quando ENVIRONMENT=production."""

    with patch('app.core.settings.settings.ENVIRONMENT', 'production'):
        # Reimporta o app com o novo valor de ENVIRONMENT

        importlib.reload(main_module)
        prod_client = TestClient(main_module.app)

    response = prod_client.get('/docs')
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_redoc_desabilitado_em_production():
    """/redoc deve retornar 404 quando ENVIRONMENT=production."""

    with patch('app.core.settings.settings.ENVIRONMENT', 'production'):
        importlib.reload(main_module)
        prod_client = TestClient(main_module.app)

    response = prod_client.get('/redoc')
    assert response.status_code == HTTPStatus.NOT_FOUND
