from datetime import time

from app.domains.schedules.periods import PERIODS
from app.domains.schedules.schemas import Period

LIST_PERIODS_TO_VERIFY = [
    ('class_period', 1, time(7, 30), time(8, 20)),
    ('class_period', 2, time(8, 20), time(9, 10)),
    # Intervalo da manhã
    ('snack_break', None, time(9, 10), time(9, 30)),
    ('class_period', 3, time(9, 30), time(10, 20)),
    ('class_period', 4, time(10, 20), time(11, 10)),
    ('class_period', 5, time(11, 10), time(12, 00)),
    # Almoço
    ('lunch_break', None, time(12, 0), time(13, 20)),
    ('class_period', 6, time(13, 20), time(14, 10)),
    ('class_period', 7, time(14, 10), time(15, 0)),
    # Intervalo da tarde
    ('snack_break', None, time(15, 0), time(15, 20)),
    ('class_period', 8, time(15, 20), time(16, 10)),
    ('class_period', 9, time(16, 10), time(17, 00)),
]
PERIODS_TO_VERIFY = []

for period_item in LIST_PERIODS_TO_VERIFY:
    PERIODS_TO_VERIFY.append(
        Period(
            type=period_item[0],
            period_number=period_item[1],
            start=period_item[2],
            end=period_item[3],
        ),
    )


def test_periods_are_correct():
    assert set(PERIODS_TO_VERIFY).issubset(set(PERIODS.periods))
