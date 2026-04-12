"""
Validações de data e horário para regras de negócio da escola.

Funções exportadas:
  validate_date_within_limit()  → data não pode ser futura nem ultrapassar N dias no passado
  validate_time_is_interval()   → horário precisa estar dentro dos intervalos permitidos
"""

from datetime import date, time

# Intervalos permitidos para porteiros (início, fim) — inclusivo nas bordas
ALLOWED_INTERVALS: list[tuple[time, time]] = [
    (time(7, 30), time(9, 30)),
    (time(12, 0), time(13, 20)),
    (time(15, 0), time(17, 0)),
]


def validate_date_within_limit(
    target_date: date,
    max_days_ago: int = 3,
) -> tuple[bool, str | None]:
    """
    Verifica se a data está dentro da janela permitida.

    - Datas futuras são sempre inválidas.
    - Datas mais antigas que `max_days_ago` dias também são inválidas.

    Retorna (True, None) quando válida ou (False, mensagem_de_erro) quando não.
    """
    today = date.today()

    if target_date > today:
        return False, 'A data não pode ser no futuro.'

    diff = (today - target_date).days
    if diff > max_days_ago:
        if max_days_ago == 0:
            return False, 'Atrasos só podem ser registrados no próprio dia.'
        return (
            False,
            f'A data não pode ter mais de {max_days_ago} dias de atraso. '
            f'Data informada tem {diff} dias de atraso.',
        )

    return True, None


def validate_time_is_interval(current_time: time) -> tuple[bool, str | None]:
    """
    Verifica se o horário está dentro de um dos intervalos escolares permitidos.

    Intervalos (inclusivo nas bordas):
      07:30 – 09:30
      12:00 – 13:20
      15:00 – 17:00

    Retorna (True, None) quando dentro de algum intervalo ou (False, mensagem_de_erro).
    """
    for start, end in ALLOWED_INTERVALS:
        if start <= current_time <= end:
            return True, None

    intervals_str = ', '.join(
        f'{s.strftime("%H:%M")}–{e.strftime("%H:%M")}'
        for s, e in ALLOWED_INTERVALS
    )
    return (
        False,
        f'Porteiros só podem registrar atrasos durante os intervalos escolares: {intervals_str}.',
    )
