from enum import Enum, IntEnum


class WeekdayEnum(IntEnum):
    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7


class PeriodTypeEnum(str, Enum):
    CLASS_PERIOD = "class_period"  # Aula
    PLANNING = "planning"  # Intervalo do almoço
    FREE = "free"  # Intervalo do lanche
    SNACK_BREAK = "snack_break"  # Livre
    LUNCH_BREAK = "lunch_break"  # Planejamento

    @property
    def default_title(self) -> str:
        return {
            self.CLASS_PERIOD: 'Aula',
            self.PLANNING: 'Planejamento',
            self.FREE: 'Folga',
            self.SNACK_BREAK: 'Intervalo',
            self.LUNCH_BREAK: 'Almoço',
        }[self]

    @property
    def is_classroom_slot(self) -> bool:
        return self in {
            self.CLASS_PERIOD,
            self.SNACK_BREAK,
            self.LUNCH_BREAK,
        }

    @property
    def requires_teacher(self) -> bool:
        return self == self.CLASS_PERIOD
