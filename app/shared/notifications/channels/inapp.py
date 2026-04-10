"""
Canal de notificações in-app.

Cria registros na tabela `notifications` que o frontend consome
via polling em GET /notifications/me.

Todas as funções recebem uma sessão aberta e NÃO fazem commit —
o dispatcher é responsável pelo commit após orquestrar todos os canais.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.notifications.models import Notification


async def send(
    session: AsyncSession,
    *,
    recipient_id: int,
    title: str,
    message: str,
    action_url: Optional[str] = None,
) -> None:
    """Persiste uma notificação in-app para o destinatário."""
    notification = Notification(
        recipient_id=recipient_id,
        title=title,
        message=message,
        action_url=action_url,
    )
    session.add(notification)


async def send_many(
    session: AsyncSession,
    *,
    recipient_ids: list[int],
    title: str,
    message: str,
    action_url: Optional[str] = None,
) -> None:
    """Persiste a mesma notificação para múltiplos destinatários."""
    for recipient_id in recipient_ids:
        await send(
            session,
            recipient_id=recipient_id,
            title=title,
            message=message,
            action_url=action_url,
        )
