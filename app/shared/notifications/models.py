"""
Model SQLAlchemy da tabela `notifications`.

Notificações in-app por usuário — acessíveis em qualquer dispositivo
com o mesmo login. Cada notificação pertence a um usuário (recipient_id)
e carrega um título, mensagem e link de ação opcional.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_as_dataclass, mapped_column

from app.shared.db.registry import mapper_registry


@mapped_as_dataclass(mapper_registry)
class Notification:
    """Notificação in-app para um usuário específico."""

    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Destinatário — apagar o usuário deleta também as suas notificações
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )

    # Conteúdo
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Link opcional para a entidade relacionada (ex: /atrasos/42)
    action_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, default=None
    )

    # Estado de leitura
    is_read: Mapped[bool] = mapped_column(
        Boolean, init=False, default=False, nullable=False
    )

    # Metadados
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
