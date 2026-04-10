"""
Canal de notificações por e-mail.

Cada função `send_*` monta o corpo do e-mail a partir do template
correspondente em notifications/templates/ e o envia via SMTP.

Se SMTP_ENABLED=false, todas as funções são no-ops silenciosos —
o dispatcher não precisa checar o flag individualmente.

As funções recebem os dados já resolvidos (strings prontas) para
manter este módulo livre de queries ao banco.
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.settings import settings

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / 'templates'


def _load_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding='utf-8')


def _send(to: str, subject: str, body: str) -> None:
    """Envia um e-mail de texto simples via SMTP configurado."""
    if not settings.SMTP_ENABLED:
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.SMTP_FROM
    msg['To'] = to
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to, msg.as_string())
    except Exception as exc:  # pragma: no cover
        # Falha no envio não deve derrubar a requisição
        print(f'[email] Falha ao enviar para {to}: {exc}')


# --------------------------------------------------------------------------- #
# Delays                                                                       #
# --------------------------------------------------------------------------- #


def send_delay_registered(
    *,
    to: str,
    saudacao: str,
    aluno_nome: str,
    turma: str,
    horario_chegada: str,
    horario_esperado: str,
    minutos_atraso: str,
    motivo: str,
    registrado_por: str,
) -> None:
    """Notifica a coordenação que um novo atraso foi registrado."""
    template = _load_template('delay_registered.txt')
    body = template.format(
        saudacao=saudacao,
        aluno_nome=aluno_nome,
        turma=turma,
        horario_chegada=horario_chegada,
        horario_esperado=horario_esperado,
        minutos_atraso=minutos_atraso,
        motivo=motivo,
        registrado_por=registrado_por,
    )
    subject = body.splitlines()[0]
    _send(to, subject, body)


def send_delay_approved(
    *,
    to: str,
    saudacao: str,
    aluno_nome: str,
    turma: str,
    data: str,
    aprovado_por: str,
) -> None:
    """Notifica o aluno/responsável que o atraso foi aprovado."""
    template = _load_template('delay_approved.txt')
    body = template.format(
        saudacao=saudacao,
        aluno_nome=aluno_nome,
        turma=turma,
        data=data,
        aprovado_por=aprovado_por,
    )
    subject = body.splitlines()[0]
    _send(to, subject, body)


def send_delay_rejected(
    *,
    to: str,
    saudacao: str,
    aluno_nome: str,
    turma: str,
    data: str,
    motivo_rejeicao: str,
) -> None:
    """Notifica o aluno/responsável que o atraso foi rejeitado."""
    template = _load_template('delay_rejected.txt')
    body = template.format(
        saudacao=saudacao,
        aluno_nome=aluno_nome,
        turma=turma,
        data=data,
        motivo_rejeicao=motivo_rejeicao,
    )
    subject = body.splitlines()[0]
    _send(to, subject, body)


# --------------------------------------------------------------------------- #
# Occurrences                                                                  #
# --------------------------------------------------------------------------- #


def send_occurrence_created(
    *,
    to: str,
    saudacao: str,
    aluno_nome: str,
    titulo: str,
    tipo: str,
    descricao: str,
    data: str,
    registrado_por: str,
) -> None:
    """Notifica o responsável que uma ocorrência foi registrada."""
    template = _load_template('occurrence_created.txt')
    body = template.format(
        saudacao=saudacao,
        aluno_nome=aluno_nome,
        titulo=titulo,
        tipo=tipo,
        descricao=descricao,
        data=data,
        registrado_por=registrado_por,
    )
    subject = body.splitlines()[0]
    _send(to, subject, body)
