"""
Dispatcher de notificações — orquestrador puro.

Responsabilidade única: para cada evento, resolver o contexto de dados
e chamar os canais corretos com os destinatários corretos.

Não contém queries SQL, formatação de strings, nem lógica de envio —
tudo isso vive em `context.py` e `channels/`.

Fluxo por evento
─────────────────────────────────────────────────────────────────
  delay_registered   → in-app (coords) + e-mail (coords) + WhatsApp (coords)
  delay_approved     → in-app (aluno + responsáveis) + e-mail + WhatsApp
  delay_rejected     → in-app (aluno + responsáveis) + e-mail + WhatsApp
  occurrence_created → in-app (DT)
  occurrence_forwarded → in-app (coords) + e-mail (coords)
"""

import asyncio

from app.shared.db.database import SessionLocal
from app.shared.notifications.context import resolve_delay, resolve_occurrence
from app.shared.notifications.channels import inapp, email, whatsapp


# --------------------------------------------------------------------------- #
# Delays                                                                       #
# --------------------------------------------------------------------------- #


async def notify_delay_registered(delay_id: int) -> None:
    """Porteiro registrou atraso → coordenação precisa revisar."""
    async with SessionLocal() as session:
        ctx = await resolve_delay(delay_id, session)
        if not ctx:
            return

        # In-app: todos os coordenadores/admins
        await inapp.send_many(
            session,
            recipient_ids=[c.id for c in ctx.coordinators],
            title='Novo atraso pendente',
            message=f'{ctx.student_name} chegou às {ctx.arrival_time_fmt} ({ctx.delay_minutes} min de atraso) e aguarda aprovação.',
            action_url=f'/atrasos/{delay_id}',
        )
        await session.commit()

    # E-mail e WhatsApp: fora da sessão do banco (I/O bloqueante separado)
    for coord in ctx.coordinators:
        if coord.email:
            email.send_delay_registered(
                to=coord.email,
                saudacao=f'Olá, {coord.first_name}',
                aluno_nome=ctx.student_name,
                turma=ctx.turma,
                horario_chegada=ctx.arrival_time_fmt,
                horario_esperado=ctx.expected_time_fmt,
                minutos_atraso=ctx.delay_minutes,
                motivo=ctx.reason,
                registrado_por=ctx.recorded_by_name,
            )
        if coord.phone:
            whatsapp.send_delay_registered(
                to_phone=coord.phone,
                aluno_nome=ctx.student_name,
                horario_chegada=ctx.arrival_time_fmt,
                minutos_atraso=ctx.delay_minutes,
            )


async def notify_delay_approved(delay_id: int) -> None:
    """Coordenador aprovou a entrada → aluno e responsáveis são notificados."""
    async with SessionLocal() as session:
        ctx = await resolve_delay(delay_id, session)
        if not ctx:
            return

        recipient_ids = [ctx.student.id] + [g.id for g in ctx.guardians]
        await inapp.send_many(
            session,
            recipient_ids=recipient_ids,
            title='Entrada aprovada',
            message=f'A entrada de {ctx.student_name} no dia {ctx.delay_date_fmt} foi aprovada.',
            action_url=f'/atrasos/{delay_id}',
        )
        await session.commit()

    for guardian in ctx.guardians:
        if guardian.email:
            email.send_delay_approved(
                to=guardian.email,
                saudacao=f'Olá, {guardian.first_name}',
                aluno_nome=ctx.student_name,
                turma=ctx.turma,
                data=ctx.delay_date_fmt,
                aprovado_por=ctx.approved_by_name,
            )
        if guardian.phone:
            whatsapp.send_delay_approved(
                to_phone=guardian.phone,
                aluno_nome=ctx.student_name,
                data=ctx.delay_date_fmt,
            )


async def notify_delay_rejected(delay_id: int) -> None:
    """Coordenador rejeitou a entrada → aluno e responsáveis são notificados."""
    async with SessionLocal() as session:
        ctx = await resolve_delay(delay_id, session)
        if not ctx:
            return

        recipient_ids = [ctx.student.id] + [g.id for g in ctx.guardians]
        await inapp.send_many(
            session,
            recipient_ids=recipient_ids,
            title='Entrada não aprovada',
            message=f'A entrada de {ctx.student_name} no dia {ctx.delay_date_fmt} não foi aprovada. Motivo: {ctx.rejection_reason}.',
            action_url=f'/atrasos/{delay_id}',
        )
        await session.commit()

    for guardian in ctx.guardians:
        if guardian.email:
            email.send_delay_rejected(
                to=guardian.email,
                saudacao=f'Olá, {guardian.first_name}',
                aluno_nome=ctx.student_name,
                turma=ctx.turma,
                data=ctx.delay_date_fmt,
                motivo_rejeicao=ctx.rejection_reason,
            )
        if guardian.phone:
            whatsapp.send_delay_rejected(
                to_phone=guardian.phone,
                aluno_nome=ctx.student_name,
                data=ctx.delay_date_fmt,
                motivo_rejeicao=ctx.rejection_reason,
            )


# --------------------------------------------------------------------------- #
# Occurrences                                                                  #
# --------------------------------------------------------------------------- #


async def notify_occurrence_created(occurrence_id: int) -> None:
    """
    Ocorrência criada:
      - DT da turma recebe in-app para decidir se encaminha.
      - Responsáveis recebem in-app imediatamente (transparência).
    """
    async with SessionLocal() as session:
        ctx = await resolve_occurrence(occurrence_id, session)
        if not ctx:
            return

        # In-app: DT da turma
        if ctx.tutor:
            await inapp.send(
                session,
                recipient_id=ctx.tutor.id,
                title='Nova ocorrência registrada',
                message=f'Uma ocorrência foi registrada para {ctx.student_name}. Verifique se deve ser encaminhada à coordenação.',
                action_url=f'/ocorrencias/{occurrence_id}',
            )

        # In-app: responsáveis do aluno
        if ctx.guardians:
            await inapp.send_many(
                session,
                recipient_ids=[g.id for g in ctx.guardians],
                title='Ocorrência registrada',
                message=f'Uma ocorrência foi registrada para {ctx.student_name}: {ctx.title}.',
                action_url=f'/ocorrencias/{occurrence_id}',
            )

        await session.commit()


async def notify_occurrence_forwarded(occurrence_id: int) -> None:
    """
    DT encaminhou ocorrência → coordenação é notificada in-app + e-mail.
    Responsáveis recebem in-app, e-mail e WhatsApp informando que houve ocorrência.
    """
    async with SessionLocal() as session:
        ctx = await resolve_occurrence(occurrence_id, session)
        if not ctx:
            return

        # In-app: coordenadores
        await inapp.send_many(
            session,
            recipient_ids=[c.id for c in ctx.coordinators],
            title='Ocorrência encaminhada pelo DT',
            message=f'O DT encaminhou uma ocorrência de {ctx.student_name} ({ctx.title}) para a coordenação.',
            action_url=f'/ocorrencias/{occurrence_id}',
        )

        # In-app: responsáveis
        await inapp.send_many(
            session,
            recipient_ids=[g.id for g in ctx.guardians],
            title='Ocorrência registrada',
            message=f'Uma ocorrência foi registrada para {ctx.student_name}: {ctx.title}.',
            action_url=f'/ocorrencias/{occurrence_id}',
        )

        await session.commit()

    # E-mail: coordenadores + responsáveis
    for coord in ctx.coordinators:
        if coord.email:
            email.send_occurrence_created(
                to=coord.email,
                saudacao=f'Olá, {coord.first_name}',
                aluno_nome=ctx.student_name,
                titulo=ctx.title,
                tipo=ctx.occurrence_type,
                descricao=ctx.description,
                data=ctx.occurred_at_fmt,
                registrado_por=ctx.created_by_name,
            )

    for guardian in ctx.guardians:
        if guardian.email:
            email.send_occurrence_created(
                to=guardian.email,
                saudacao=f'Olá, {guardian.first_name}',
                aluno_nome=ctx.student_name,
                titulo=ctx.title,
                tipo=ctx.occurrence_type,
                descricao=ctx.description,
                data=ctx.occurred_at_fmt,
                registrado_por=ctx.created_by_name,
            )
        if guardian.phone:
            whatsapp.send_occurrence_created(
                to_phone=guardian.phone,
                aluno_nome=ctx.student_name,
                titulo=ctx.title,
                tipo=ctx.occurrence_type,
            )
