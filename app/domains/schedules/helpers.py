from datetime import date, time
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedules.models import (
    ScheduleOverride,
    ScheduleSlot,
    override_classrooms,
)
from app.domains.schedules.periods import PERIODS  # , overlaps
from app.domains.schedules.schemas import Period, PeriodsList, Weekday
from app.domains.users.models import User


def get_current_period(at_time: time, periods: PeriodsList) -> Period | None:
    for period in periods.periods:
        if period.contains(at_time):
            return period
    return None


def is_time_at_class_period(at_time: time, periods: PeriodsList) -> bool:
    current_period = get_current_period(at_time, periods)
    if current_period is None:
        return False
    elif current_period.type == 'class_period':
        return True
    return False


async def get_current_teacher(
    classroom_id: int, at_time: time, session: AsyncSession
) -> Optional[User]:
    """
    Recebe o ID da sala, o horário a procurar e as sessão do banco de dados
    Se estiver em aula e o professor existir, retorna seu ID.
    Se não, retorna None.
    """
    current_period = get_current_period(at_time, PERIODS)
    # Faz com que Domingo seja 1, ... Sábado seja 7, e converte para Weekday enum
    weekday = Weekday((date.today().weekday() + 1) % 7 + 1)

    # 1. Verifica se há um `ScheduleOverride` ativo para
    # a data e horário em questão que afeta a turma
    schedule_override = await session.scalar(
        select(ScheduleOverride)
        .join(
            override_classrooms,
            (override_classrooms.c.override_id == ScheduleOverride.id),
            isouter=True,
        )
        .where(
            # Filtrar pelo dia de hoje
            ScheduleOverride.override_date == date.today(),
            # at_time está no intervalo do agendamento
            ScheduleOverride.starts_at <= at_time,
            ScheduleOverride.ends_at > at_time,
            or_(
                # Afeta todas as turmas
                ScheduleOverride.affects_all,
                # Essa condição precisa do JOIN para funcionar
                override_classrooms.c.classroom_id == classroom_id,
            ),
        )
    )
    # Se tiver algum agendamento que afete todas ou, pelo menos, aquela turma
    if schedule_override is not None:
        # Retorna None, indicando aula suspensa por evento
        return None

    # 2. Descobre em qual período cai o horário `at_time`,
    # consultando a constante `PERIODS`
    # Obs.: garante que current_period é do tipo Period
    if not is_time_at_class_period(at_time, PERIODS):
        # Se cair em um intervalo ou fora do horário escolar, retorna `None`
        return None

    schedule_slot = await session.scalar(
        select(ScheduleSlot)
        # Mesma sala, dia da semana, número do período de aula
        .where(ScheduleSlot.classroom_id == classroom_id)
        .where(ScheduleSlot.weekday == weekday)
        .where(ScheduleSlot.period_number == current_period.period_number)  # type: ignore
        # Tem que ter algum professor
        .where(ScheduleSlot.teacher_id.is_not(None))
    )
    if schedule_slot is None:
        # Retorna None, indicando aula suspensa por evento
        return None

    return await session.get(User, schedule_slot.teacher_id)
