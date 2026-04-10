"""
Helpers de verificação de janela horária para o domínio de atrasos.

is_within_interval_window():
  Retorna True se o horário atual estiver dentro de um intervalo
  (SNACK_BREAK ou LUNCH_BREAK) definido em PERIODS.
  Usado para restringir o porteiro a registrar/aprovar atrasos
  apenas durante os intervalos.

PORTER_DELAY_WINDOW_MINUTES:
  Tolerância em minutos além do fim do intervalo — por padrão 5 min.
  Ex.: intervalo termina às 09:30 → porteiro pode até 09:35.
"""

from datetime import datetime, time

from app.domains.schedules.enums import PeriodTypeEnum
from app.domains.schedules.periods import PERIODS

# Tolerância pós-intervalo (porteiro pode registrar até X min após o fim)
PORTER_DELAY_WINDOW_MINUTES = 5

# Tipos de período que abrem a janela do porteiro
_BREAK_TYPES = {PeriodTypeEnum.SNACK_BREAK, PeriodTypeEnum.LUNCH_BREAK}


def is_within_porter_window(now: time | None = None) -> bool:
    """
    Verifica se o horário `now` está dentro de um intervalo + tolerância.

    Se `now` for None, usa o horário atual do sistema.
    """
    from datetime import timedelta

    if now is None:
        now = datetime.now().time()

    for period in PERIODS.periods:
        if period.type not in _BREAK_TYPES:
            continue

        # Estende o fim pelo buffer de tolerância
        from app.domains.schedules.periods import add_time

        extended_end = add_time(period.end, timedelta(minutes=PORTER_DELAY_WINDOW_MINUTES))

        if period.start <= now <= extended_end:
            return True

    return False
