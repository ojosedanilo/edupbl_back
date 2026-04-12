"""
Testes unitários para o validador de datas.

Cobre validate_date_within_limit() com limite padrão (3 dias) e
com limite zero (mesmo dia), que é o caso dos atrasos.
"""

from datetime import date, timedelta

from app.shared.date_validator import validate_date_within_limit

# --------------------------------------------------------------------------- #
# validate_date_within_limit — limite padrão (3 dias, usado em ocorrências)   #
# --------------------------------------------------------------------------- #


def test_today_is_valid():
    valid, err = validate_date_within_limit(date.today())
    assert valid is True
    assert err is None


def test_yesterday_is_valid():
    valid, err = validate_date_within_limit(date.today() - timedelta(days=1))
    assert valid is True
    assert err is None


def test_exactly_3_days_ago_is_valid():
    valid, err = validate_date_within_limit(date.today() - timedelta(days=3))
    assert valid is True
    assert err is None


def test_4_days_ago_is_invalid():
    valid, err = validate_date_within_limit(date.today() - timedelta(days=4))
    assert valid is False
    assert err is not None
    assert '3' in err  # mensagem menciona o limite


def test_future_date_is_invalid():
    valid, err = validate_date_within_limit(date.today() + timedelta(days=1))
    assert valid is False
    assert err is not None
    assert 'futuro' in err.lower()


# --------------------------------------------------------------------------- #
# validate_date_within_limit — limite zero (mesmo dia, usado em atrasos)      #
# --------------------------------------------------------------------------- #


def test_today_is_valid_same_day_restriction():
    valid, err = validate_date_within_limit(date.today(), max_days_ago=0)
    assert valid is True
    assert err is None


def test_yesterday_is_invalid_same_day_restriction():
    valid, err = validate_date_within_limit(
        date.today() - timedelta(days=1), max_days_ago=0
    )
    assert valid is False
    assert err is not None
    assert 'mesmo dia' in err.lower() or 'próprio dia' in err.lower()


def test_3_days_ago_is_invalid_same_day_restriction():
    valid, err = validate_date_within_limit(
        date.today() - timedelta(days=3), max_days_ago=0
    )
    assert valid is False
    assert err is not None


def test_future_is_invalid_same_day_restriction():
    valid, err = validate_date_within_limit(
        date.today() + timedelta(days=1), max_days_ago=0
    )
    assert valid is False
    assert err is not None
