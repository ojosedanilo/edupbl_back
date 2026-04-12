"""
Testes unitários para o validador de horários.

Cobre validate_time_is_interval() com horários dentro e fora dos
intervalos permitidos para porteiros.

Intervalos:
  07:30 – 09:30
  12:00 – 13:20
  15:00 – 17:00
"""

from datetime import time

from app.shared.date_validator import validate_time_is_interval


# --------------------------------------------------------------------------- #
# Horários DENTRO dos intervalos                                               #
# --------------------------------------------------------------------------- #


def test_first_interval_middle_is_valid():
    valid, err = validate_time_is_interval(time(8, 0))
    assert valid is True
    assert err is None


def test_second_interval_middle_is_valid():
    valid, err = validate_time_is_interval(time(12, 30))
    assert valid is True
    assert err is None


def test_third_interval_middle_is_valid():
    valid, err = validate_time_is_interval(time(16, 0))
    assert valid is True
    assert err is None


# Bordas dos intervalos — devem ser aceitas (inclusivo)

def test_first_interval_start_boundary_is_valid():
    valid, err = validate_time_is_interval(time(7, 30))
    assert valid is True


def test_first_interval_end_boundary_is_valid():
    valid, err = validate_time_is_interval(time(9, 30))
    assert valid is True


def test_second_interval_start_boundary_is_valid():
    valid, err = validate_time_is_interval(time(12, 0))
    assert valid is True


def test_second_interval_end_boundary_is_valid():
    valid, err = validate_time_is_interval(time(13, 20))
    assert valid is True


def test_third_interval_start_boundary_is_valid():
    valid, err = validate_time_is_interval(time(15, 0))
    assert valid is True


def test_third_interval_end_boundary_is_valid():
    valid, err = validate_time_is_interval(time(17, 0))
    assert valid is True


# --------------------------------------------------------------------------- #
# Horários FORA dos intervalos (durante aulas)                                #
# --------------------------------------------------------------------------- #


def test_during_class_morning_is_invalid():
    """10:00 — entre o 1º e o 2º intervalo (aula em andamento)."""
    valid, err = validate_time_is_interval(time(10, 0))
    assert valid is False
    assert err is not None
    assert "intervalo" in err.lower()


def test_during_class_afternoon_is_invalid():
    """14:00 — entre o 2º e o 3º intervalo (aula em andamento)."""
    valid, err = validate_time_is_interval(time(14, 0))
    assert valid is False
    assert err is not None


def test_before_school_is_invalid():
    """07:00 — antes do início do expediente."""
    valid, err = validate_time_is_interval(time(7, 0))
    assert valid is False
    assert err is not None


def test_after_school_is_invalid():
    """18:00 — após o encerramento."""
    valid, err = validate_time_is_interval(time(18, 0))
    assert valid is False
    assert err is not None


def test_just_before_first_interval_is_invalid():
    """07:29 — um minuto antes do 1º intervalo."""
    valid, err = validate_time_is_interval(time(7, 29))
    assert valid is False


def test_just_after_first_interval_is_invalid():
    """09:31 — um minuto após o fim do 1º intervalo."""
    valid, err = validate_time_is_interval(time(9, 31))
    assert valid is False
