"""
Resolução de contexto para os eventos de notificação.

Cada função `resolve_*` carrega do banco tudo o que os canais precisam
(nomes, e-mails, telefones, turmas, etc.) e devolve um dataclass simples.

Separar a resolução de dados do despacho mantém o dispatcher como
orquestrador puro: ele pede o contexto, chama os canais, pronto.
"""

from dataclasses import dataclass, field
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User, active_users, guardian_student
from app.shared.rbac.roles import UserRole

# --------------------------------------------------------------------------- #
# Helpers internos                                                            #
# --------------------------------------------------------------------------- #


def _fmt_name(user: User | None) -> str:
    if not user:
        return 'Usuário desconhecido'
    return f'{user.first_name} {user.last_name}'


def _fmt_time(t: time | None) -> str:
    if not t:
        return '--:--'
    return t.strftime('%H:%M')


def _fmt_date(d: date | None) -> str:
    if not d:
        return '--/--/----'
    return d.strftime('%d/%m/%Y')


async def _get_classroom_name(
    classroom_id: int | None, session: AsyncSession
) -> str:
    if not classroom_id:
        return 'Turma não informada'
    from app.domains.users.models import (
        Classroom,
    )  # importação local para evitar ciclo

    classroom = await session.get(Classroom, classroom_id)
    return classroom.name if classroom else 'Turma não encontrada'


async def _get_guardians(student_id: int, session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(guardian_student.c.guardian_id).where(
            guardian_student.c.student_id == student_id
        )
    )
    ids = [row[0] for row in result.all()]
    if not ids:
        return []
    users = await session.scalars(
        select(User).where(User.id.in_(ids), User.is_active == True)  # noqa: E712
    )
    return list(users.all())


async def _get_coordinators(session: AsyncSession) -> list[User]:
    result = await session.scalars(
        active_users().where(
            User.role.in_([UserRole.COORDINATOR, UserRole.ADMIN])
        )
    )
    return list(result.all())


async def _get_tutor(student_id: int, session: AsyncSession) -> User | None:
    student = await session.get(User, student_id)
    if not student or not student.classroom_id:
        return None
    return await session.scalar(
        active_users().where(
            User.role == UserRole.TEACHER,
            User.is_tutor == True,  # noqa: E712
            User.classroom_id == student.classroom_id,
        )
    )


# --------------------------------------------------------------------------- #
# Contextos                                                                    #
# --------------------------------------------------------------------------- #


@dataclass
class DelayContext:
    delay_id: int
    student: User
    student_name: str
    turma: str
    delay_date_fmt: str
    arrival_time_fmt: str
    expected_time_fmt: str
    delay_minutes: str
    reason: str
    recorded_by_name: str
    approved_by_name: str
    rejection_reason: str
    coordinators: list[User]
    guardians: list[User]


async def resolve_delay(
    delay_id: int, session: AsyncSession
) -> DelayContext | None:
    from app.domains.delays.models import Delay

    delay = await session.get(Delay, delay_id)
    if not delay:
        return None

    student = await session.get(User, delay.student_id)
    recorded_by = (
        await session.get(User, delay.recorded_by_id)
        if delay.recorded_by_id
        else None
    )
    approved_by = (
        await session.get(User, delay.approved_by_id)
        if delay.approved_by_id
        else None
    )
    turma = await _get_classroom_name(
        student.classroom_id if student else None, session
    )
    coordinators = await _get_coordinators(session)
    guardians = await _get_guardians(delay.student_id, session)

    return DelayContext(
        delay_id=delay_id,
        student=student,
        student_name=_fmt_name(student),
        turma=turma,
        delay_date_fmt=_fmt_date(delay.delay_date),
        arrival_time_fmt=_fmt_time(delay.arrival_time),
        expected_time_fmt=_fmt_time(delay.expected_time),
        delay_minutes=str(delay.delay_minutes),
        reason=delay.reason or 'Não informado',
        recorded_by_name=_fmt_name(recorded_by),
        approved_by_name=_fmt_name(approved_by),
        rejection_reason=delay.rejection_reason or 'Não informado',
        coordinators=coordinators,
        guardians=guardians,
    )


@dataclass
class OccurrenceContext:
    occurrence_id: int
    student: User
    student_name: str
    turma: str
    title: str
    description: str
    occurrence_type: str
    occurred_at_fmt: str
    created_by_name: str
    tutor: User | None
    coordinators: list[User]
    guardians: list[User]


async def resolve_occurrence(
    occurrence_id: int, session: AsyncSession
) -> OccurrenceContext | None:
    from datetime import datetime

    from app.domains.occurrences.models import Occurrence

    occurrence = await session.get(Occurrence, occurrence_id)
    if not occurrence:
        return None

    student = await session.get(User, occurrence.student_id)
    created_by = (
        await session.get(User, occurrence.created_by_id)
        if occurrence.created_by_id
        else None
    )
    turma = await _get_classroom_name(
        student.classroom_id if student else None, session
    )
    tutor = await _get_tutor(occurrence.student_id, session)
    coordinators = await _get_coordinators(session)
    guardians = await _get_guardians(occurrence.student_id, session)

    occurred_at = occurrence.occurred_at or occurrence.created_at
    occurred_at_fmt = (
        occurred_at.strftime('%d/%m/%Y %H:%M') if occurred_at else '--'
    )

    return OccurrenceContext(
        occurrence_id=occurrence_id,
        student=student,
        student_name=_fmt_name(student),
        turma=turma,
        title=occurrence.title,
        description=occurrence.description,
        occurrence_type=occurrence.occurrence_type.value,
        occurred_at_fmt=occurred_at_fmt,
        created_by_name=_fmt_name(created_by),
        tutor=tutor,
        coordinators=coordinators,
        guardians=guardians,
    )
