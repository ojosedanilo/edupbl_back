from sqlalchemy.ext.asyncio import AsyncSession
from app.core.settings import settings


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_ENABLED:
        print()
        return


# ── Delays ───────────────────────────────────────────────────────────────── #


async def send_email_delay_registered(
    delay_id: int,
    session: AsyncSession,
) -> None:
    """Envia o e-mail para a coordenação que um novo atraso foi registrado (status PENDING)."""
    data = {
        'saudacao': '',
        'aluno_nome': '',
        'turma': '',
        'horario_chegada': '',
        'horario_esperado': '',
        'minutos_atraso': '',
        'motivo': '',
        'registrado_por': '',
    }
    message.format(**data)
    pass


async def send_email_delay_approved(
    delay_id: int,
    session: AsyncSession,
) -> None:
    """Envia o e-mail para o professor DT e o responsável que a entrada foi aprovada."""
    data = {
        'saudacao': '',
        'aluno_nome': '',
        'turma': '',
        'data': '',
        'aprovado_por': '',
    }
    message.format(**data)
    pass


async def send_email_delay_rejected(
    delay_id: int,
    session: AsyncSession,
) -> None:
    """Envia o e-mail para o responsável que a entrada foi rejeitada."""
    data = {
        'saudacao': '',
        'aluno_nome': '',
        'turma': '',
        'data': '',
        'motivo_rejeicao': '',
    }
    message.format(**data)
    pass


# ── Occurrences ──────────────────────────────────────────────────────────── #


async def send_email_occurrence_created(
    occurrence_id: int,
    session: AsyncSession,
) -> None:
    """Envia o e-mail para o responsável que o aluno recebeu uma ocorrência."""
    data = {
        'saudacao': '',
        'aluno_nome': '',
        'titulo': '',
        'descricao': '',
        'data': '',
        'registrado_por': '',
    }
    message.format(**data)
    pass
