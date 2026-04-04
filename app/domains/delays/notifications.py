# Placeholders de notificação — serão implementados na feature de WhatsApp
# (ver plano/3-INTEGRACAO_WHATSAPP.md)


async def notify_delay_registered(delay_id: int) -> None:
    """Notifica a coordenação que um novo atraso foi registrado (status PENDING)."""
    pass


async def notify_delay_approved(delay_id: int) -> None:
    """Notifica o professor DT e o responsável que a entrada foi aprovada."""
    pass


async def notify_delay_rejected(delay_id: int) -> None:
    """Notifica o responsável que a entrada foi rejeitada."""
    pass
