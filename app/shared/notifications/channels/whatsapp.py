"""
Canal de notificações por WhatsApp.

Envia mensagens via a integração configurada em settings
(WHATSAPP_ENABLED, WHATSAPP_DB_PATH, WHATSAPP_DEVICE_NAME).

Se WHATSAPP_ENABLED=false, todas as funções são no-ops silenciosos.

As funções recebem os dados já resolvidos (strings prontas) para
manter este módulo livre de queries ao banco.

TODO: implementar o envio real conforme INTEGRACAO_WHATSAPP.md.
      Por ora, as funções loggam a mensagem e retornam.
"""

from app.core.settings import settings


def _send(to_phone: str, message: str) -> None:
    """Envia uma mensagem de texto via WhatsApp para o número informado."""
    if not settings.WHATSAPP_ENABLED:
        return

    # TODO: integrar com a biblioteca/API de WhatsApp definida no plano.
    print(f'[whatsapp] → {to_phone}: {message[:80]}…')


# --------------------------------------------------------------------------- #
# Delays                                                                       #
# --------------------------------------------------------------------------- #


def send_delay_registered(
    *,
    to_phone: str,
    aluno_nome: str,
    horario_chegada: str,
    minutos_atraso: str,
) -> None:
    """Avisa a coordenação via WhatsApp que há um novo atraso pendente."""
    msg = (
        f'📋 Novo atraso pendente\n'
        f'Aluno: {aluno_nome}\n'
        f'Chegada: {horario_chegada} ({minutos_atraso} min de atraso)\n'
        f'Acesse o sistema para aprovar ou rejeitar.'
    )
    _send(to_phone, msg)


def send_delay_approved(
    *,
    to_phone: str,
    aluno_nome: str,
    data: str,
) -> None:
    """Avisa o responsável que o atraso foi aprovado."""
    msg = (
        f'✅ Entrada aprovada\n'
        f'O atraso de {aluno_nome} em {data} foi aprovado.'
    )
    _send(to_phone, msg)


def send_delay_rejected(
    *,
    to_phone: str,
    aluno_nome: str,
    data: str,
    motivo_rejeicao: str,
) -> None:
    """Avisa o responsável que o atraso foi rejeitado."""
    msg = (
        f'❌ Entrada não aprovada\n'
        f'O atraso de {aluno_nome} em {data} não foi aprovado.\n'
        f'Motivo: {motivo_rejeicao}'
    )
    _send(to_phone, msg)


# --------------------------------------------------------------------------- #
# Occurrences                                                                  #
# --------------------------------------------------------------------------- #


def send_occurrence_created(
    *,
    to_phone: str,
    aluno_nome: str,
    titulo: str,
    tipo: str,
) -> None:
    """Avisa o responsável via WhatsApp que uma ocorrência foi registrada."""
    msg = (
        f'⚠️ Nova ocorrência\n'
        f'Aluno: {aluno_nome}\n'
        f'Tipo: {tipo}\n'
        f'Título: {titulo}\n'
        f'Acesse o sistema para mais detalhes.'
    )
    _send(to_phone, msg)
