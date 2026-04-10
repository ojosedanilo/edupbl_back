"""
Rotas de notificações in-app.

  GET    /notifications/me          → lista as notificações do usuário logado
  PATCH  /notifications/{id}/read   → marca uma notificação como lida
  PATCH  /notifications/read-all    → marca todas as notificações como lidas
  DELETE /notifications/{id}        → apaga uma notificação
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.database import get_session
from app.shared.notifications.models import Notification
from app.shared.notifications.schemas import NotificationList, NotificationPublic
from app.shared.security import get_current_user
from app.domains.users.models import User

router = APIRouter(prefix='/notifications', tags=['notifications'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# --------------------------------------------------------------------------- #
# GET /notifications/me                                                        #
# --------------------------------------------------------------------------- #


@router.get('/me', response_model=NotificationList)
async def list_my_notifications(session: Session, current_user: CurrentUser):
    """
    Retorna as notificações do usuário logado, ordenadas da mais recente.
    Inclui contagem de não lidas para o badge do sino.
    """
    result = await session.scalars(
        select(Notification)
        .where(Notification.recipient_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = result.all()

    unread_count = await session.scalar(
        select(func.count()).where(
            Notification.recipient_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )

    return {'notifications': notifications, 'unread_count': unread_count or 0}


# --------------------------------------------------------------------------- #
# PATCH /notifications/read-all                                                #
# --------------------------------------------------------------------------- #


@router.patch('/read-all', status_code=HTTPStatus.NO_CONTENT)
async def mark_all_read(session: Session, current_user: CurrentUser):
    """Marca todas as notificações do usuário como lidas."""
    await session.execute(
        update(Notification)
        .where(
            Notification.recipient_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await session.commit()


# --------------------------------------------------------------------------- #
# PATCH /notifications/{id}/read                                               #
# --------------------------------------------------------------------------- #


@router.patch('/{notification_id}/read', response_model=NotificationPublic)
async def mark_notification_read(
    session: Session,
    current_user: CurrentUser,
    notification_id: int = Path(alias='notification_id'),
):
    """Marca uma notificação específica como lida."""
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
        )
    )
    if not notification:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Notification not found',
        )

    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return notification


# --------------------------------------------------------------------------- #
# DELETE /notifications/{id}                                                   #
# --------------------------------------------------------------------------- #


@router.delete('/{notification_id}', status_code=HTTPStatus.NO_CONTENT)
async def delete_notification(
    session: Session,
    current_user: CurrentUser,
    notification_id: int = Path(alias='notification_id'),
):
    """Apaga uma notificação do usuário."""
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
        )
    )
    if not notification:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Notification not found',
        )

    await session.delete(notification)
    await session.commit()
