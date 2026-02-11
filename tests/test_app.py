from http import HTTPStatus

from fastapi.testclient import TestClient

from app.app import app


def test_home_deve_retornar_ok_e_ola_mundo():
    client = TestClient(app)  # Arrange

    response = client.get('/')  # Act

    assert response.status_code == HTTPStatus.OK  # Assert
    assert response.json() == {'message': 'Olá, Mundo!'}  # Assert


def test_html_deve_retornar_ok_e_html():
    client = TestClient(app)

    response = client.get('/html')

    assert response.status_code == HTTPStatus.OK
    assert '<h1>Olá, Mundo!</h1>' in response.text
