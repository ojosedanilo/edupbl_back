"""
Utilitários de normalização de texto.

Usado para garantir que usernames contenham apenas caracteres ASCII
seguros (a-z, 0-9, ponto e underscore), sem acentos, cedilha ou
outros caracteres especiais.
"""

import re
import unicodedata


def slugify(text: str) -> str:
    """Converte uma string para formato seguro de username.

    Passos:
    1. Normaliza para NFD (separa letras de seus diacríticos)
    2. Remove os diacríticos (acentos, cedilha vira 'c', etc.)
    3. Converte para ASCII puro
    4. Coloca em minúsculas
    5. Troca espaços por underscore
    6. Remove qualquer caractere que não seja a-z, 0-9, ponto ou underscore
    7. Remove pontos/underscores repetidos ou nas extremidades

    Exemplos:
        "João"      -> "joao"
        "Ção"       -> "cao"
        "José Lima" -> "jose_lima"
        "Ângela"    -> "angela"
        "Renée"     -> "renee"
    """
    # Separa letras de diacríticos (ex: "ã" vira "a" + combining tilde)
    normalized = unicodedata.normalize('NFD', text)

    # Descarta os caracteres de categoria "Mark, Nonspacing" (os diacríticos)
    ascii_text = ''.join(
        c for c in normalized if unicodedata.category(c) != 'Mn'
    )

    # Encode/decode para garantir ASCII puro (elimina qualquer sobra)
    ascii_text = ascii_text.encode('ascii', errors='ignore').decode('ascii')

    # Minúsculas e troca espaços por underscore
    ascii_text = ascii_text.lower().replace(' ', '_')

    # Remove tudo que não seja a-z, 0-9, ponto ou underscore
    ascii_text = re.sub(r'[^a-z0-9._]', '', ascii_text)

    # Colapsa sequências de pontos/underscores (ex: "a..b" -> "a.b")
    ascii_text = re.sub(r'[._]{2,}', '.', ascii_text)

    # Remove ponto ou underscore no início/fim
    ascii_text = ascii_text.strip('._')

    return ascii_text


# Regex de validação — mesmas regras do slugify, para uso em schemas Pydantic
USERNAME_REGEX = re.compile(r'^[a-z0-9][a-z0-9._]{1,48}[a-z0-9]$')


def username_is_valid(username: str) -> bool:
    """Retorna True se o username já está no formato correto."""
    return bool(USERNAME_REGEX.match(username))
