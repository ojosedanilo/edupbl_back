import math
import re
import string
import unicodedata
from enum import Enum
from typing import Callable, Optional

from pwdlib import PasswordHash
from pydantic import BaseModel

# ── HASH ─────────────────────────────────────────────────────────────────── #

password_hasher = PasswordHash.recommended()

# ── CONSTANTES ───────────────────────────────────────────────────────────── #

MIN_LENGTH = 15
BONUS_LENGTH = 20

SCORE_LENGTH = 2
SCORE_LENGTH_BONUS = 1
SCORE_CHAR_TYPE = 1
SCORE_NO_REPETITION = 1

PENALTY_PATTERN = -3
PENALTY_REPETITION = -2
PENALTY_PERSONAL_INFO = -3
PENALTY_SAME_PASSWORD = -3

POOL_LOWER = 26
POOL_UPPER = 26
POOL_DIGITS = 10
POOL_PUNCT = 32
POOL_FALLBACK = 1

ENTROPY_VERY_WEAK = 28
ENTROPY_WEAK = 36
ENTROPY_MEDIUM = 60
ENTROPY_STRONG = 128

ENTROPY_SCORE_MEDIUM = 40
ENTROPY_SCORE_STRONG = 60
ENTROPY_SCORE_MEDIUM_VALUE = 1
ENTROPY_SCORE_STRONG_VALUE = 2

GUESSES_PER_SECOND = 1_000_000_000

REGEX_UPPER = r'[A-Z]'
REGEX_LOWER = r'[a-z]'
REGEX_NUMBER = r'\d'
REGEX_SPECIAL = rf'[{re.escape(string.punctuation)}]'
REGEX_REPEAT = r'(.)\1{3,}'

SEQUENCES = [
    string.ascii_lowercase,
    string.ascii_uppercase,
    string.digits,
    'qwertyuiopasdfghjklzxcvbnm',
]

# ── PERSONAL INFO CONFIG ─────────────────────────────────────────────────── #

MIN_PERSONAL_INFO_LENGTH = 3
MIN_SUBSTRING_LENGTH = 4
YEAR_PATTERN = r'(19|20)\d{2}'
MAX_ALLOWED_YEARS = 1

# ── ENUMS ────────────────────────────────────────────────────────────────── #


class PasswordErros(str, Enum):
    MIN_LENGTH = 'min_length'
    MISSING_UPPERCASE = 'missing_uppercase'
    MISSING_LOWERCASE = 'missing_lowercase'
    MISSING_NUMBER = 'missing_number'
    MISSING_SPECIAL = 'missing_special'
    PERSONAL_INFO = 'personal_info'
    PATTERN_SEQUENCE = 'pattern_sequence'
    REPEATED_CHARS = 'repeated_chars'
    SAME_AS_OLD = 'same_as_old'


class PasswordSuggestions(str, Enum):
    USE_LONGER_PASSWORD = 'use_longer_password'
    ADD_UPPERCASE = 'add_uppercase'
    ADD_LOWERCASE = 'add_lowercase'
    ADD_NUMBER = 'add_number'
    ADD_SPECIAL = 'add_special'
    AVOID_PERSONAL = 'avoid_personal_info'
    AVOID_PATTERN = 'avoid_patterns'
    AVOID_REPETITION = 'avoid_repetition'
    CHANGE_PASSWORD = 'use_different_password'
    USE_PASSPHRASE = 'use_passphrase'


class PasswordStrength(str, Enum):
    VERY_WEAK = 'very_weak'
    WEAK = 'weak'
    MEDIUM = 'medium'
    STRONG = 'strong'
    VERY_STRONG = 'very_strong'


# ── MODELO ───────────────────────────────────────────────────────────────── #


class PasswordValidation(BaseModel):
    valid: bool
    erros: list[PasswordErros]
    strength_value: int
    strength_avaliation: PasswordStrength
    suggestions: list[PasswordSuggestions]
    crack_time: str


# ── CONTEXTO ─────────────────────────────────────────────────────────────── #


class PasswordContext:
    def __init__(
        self,
        password: str,
        first_name: Optional[str],
        last_name: Optional[str],
        current_hash: Optional[str],
    ):
        self.password = password
        self.first_name = first_name
        self.last_name = last_name
        self.current_hash = current_hash

        self.errors: list[PasswordErros] = []
        self.suggestions: list[PasswordSuggestions] = []
        self.score: int = 0


# ── UTILIDADES ───────────────────────────────────────────────────────────── #


def normalize(text: str) -> str:
    text = text.lower()
    return ''.join(
        c
        for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def extract_words(password: str) -> list[str]:
    return re.findall(r'[a-zA-Z]+', normalize(password))


# ── ENTROPIA ─────────────────────────────────────────────────────────────── #


def calculate_entropy(password: str) -> float:
    pool = 0

    if any(c in string.ascii_lowercase for c in password):
        pool += POOL_LOWER
    if any(c in string.ascii_uppercase for c in password):
        pool += POOL_UPPER
    if any(c in string.digits for c in password):
        pool += POOL_DIGITS
    if any(c in string.punctuation for c in password):
        pool += POOL_PUNCT

    if pool == 0:
        pool = POOL_FALLBACK

    return round(len(password) * math.log2(pool), 2)


def classify_password(
    entropy: float, error_count: int = 0
) -> PasswordStrength:
    # Penalizar a entropia efetiva por erros de validação
    effective_entropy = entropy - (error_count * 15)

    if effective_entropy < ENTROPY_VERY_WEAK:
        return PasswordStrength.VERY_WEAK
    if effective_entropy < ENTROPY_WEAK:
        return PasswordStrength.WEAK
    if effective_entropy < ENTROPY_MEDIUM:
        return PasswordStrength.MEDIUM
    if effective_entropy < ENTROPY_STRONG:
        return PasswordStrength.STRONG
    return PasswordStrength.VERY_STRONG


# ── DETECTORES ───────────────────────────────────────────────────────────── #


def has_sequential_pattern(password: str, length: int = 4) -> bool:
    password = password.lower()

    for seq in SEQUENCES:
        for i in range(len(seq) - length + 1):
            chunk = seq[i : i + length]
            if chunk in password or chunk[::-1] in password:
                return True
    return False


def has_repetition(password: str) -> bool:
    return bool(re.search(REGEX_REPEAT, password))


def has_personal_info(ctx: PasswordContext) -> bool:
    words = extract_words(ctx.password)
    password_normalized = normalize(ctx.password)

    def check_name(name: Optional[str]) -> bool:
        if not name:
            return False

        name = normalize(name)

        if len(name) < MIN_PERSONAL_INFO_LENGTH:
            return False

        # match exato em palavra
        if name in words:
            return True

        # match como substring (mais restritivo)
        if len(name) >= MIN_SUBSTRING_LENGTH and name in password_normalized:
            return True

        return False

    if check_name(ctx.first_name):
        return True

    if check_name(ctx.last_name):
        return True

    # anos (somente se muitos)
    years = re.findall(YEAR_PATTERN, ctx.password)
    if len(years) > MAX_ALLOWED_YEARS:
        return True

    return False


# ── STEPS ────────────────────────────────────────────────────────────────── #


def step_length(ctx: PasswordContext):
    if len(ctx.password) < MIN_LENGTH:
        ctx.errors.append(PasswordErros.MIN_LENGTH)
        ctx.suggestions.append(PasswordSuggestions.USE_LONGER_PASSWORD)
        return

    ctx.score += SCORE_LENGTH
    if len(ctx.password) >= BONUS_LENGTH:
        ctx.score += SCORE_LENGTH_BONUS


def step_character_types(ctx: PasswordContext):
    checks = [
        (
            REGEX_UPPER,
            PasswordErros.MISSING_UPPERCASE,
            PasswordSuggestions.ADD_UPPERCASE,
        ),
        (
            REGEX_LOWER,
            PasswordErros.MISSING_LOWERCASE,
            PasswordSuggestions.ADD_LOWERCASE,
        ),
        (
            REGEX_NUMBER,
            PasswordErros.MISSING_NUMBER,
            PasswordSuggestions.ADD_NUMBER,
        ),
        (
            REGEX_SPECIAL,
            PasswordErros.MISSING_SPECIAL,
            PasswordSuggestions.ADD_SPECIAL,
        ),
    ]

    for regex, err, sug in checks:
        if not re.search(regex, ctx.password):
            ctx.errors.append(err)
            ctx.suggestions.append(sug)
        else:
            ctx.score += SCORE_CHAR_TYPE


def step_patterns(ctx: PasswordContext):
    if has_sequential_pattern(ctx.password):
        ctx.errors.append(PasswordErros.PATTERN_SEQUENCE)
        ctx.suggestions.append(PasswordSuggestions.AVOID_PATTERN)
        ctx.score += PENALTY_PATTERN

    if has_repetition(ctx.password):
        ctx.errors.append(PasswordErros.REPEATED_CHARS)
        ctx.suggestions.append(PasswordSuggestions.AVOID_REPETITION)
        ctx.score += PENALTY_REPETITION
    else:
        ctx.score += SCORE_NO_REPETITION


def step_personal_info(ctx: PasswordContext):
    if has_personal_info(ctx):
        ctx.errors.append(PasswordErros.PERSONAL_INFO)
        ctx.suggestions.append(PasswordSuggestions.AVOID_PERSONAL)
        ctx.score += PENALTY_PERSONAL_INFO


def step_old_password(ctx: PasswordContext):
    if not ctx.current_hash:
        return

    try:
        if password_hasher.verify(ctx.password, ctx.current_hash):
            ctx.errors.append(PasswordErros.SAME_AS_OLD)
            ctx.suggestions.append(PasswordSuggestions.CHANGE_PASSWORD)
            ctx.score += PENALTY_SAME_PASSWORD
    except Exception:
        pass


# ── PIPELINE ─────────────────────────────────────────────────────────────── #

PipelineStep = Callable[[PasswordContext], None]

PIPELINE: list[PipelineStep] = [
    step_length,
    step_character_types,
    step_patterns,
    step_personal_info,
    step_old_password,
]

# ── ERROS CRÍTICOS ───────────────────────────────────────────────────────── #

CRITICAL_ERRORS = {
    PasswordErros.MIN_LENGTH,
    PasswordErros.SAME_AS_OLD,
    PasswordErros.MISSING_UPPERCASE,
    PasswordErros.MISSING_LOWERCASE,
    PasswordErros.MISSING_NUMBER,
    PasswordErros.MISSING_SPECIAL,
    PasswordErros.REPEATED_CHARS,
    PasswordErros.PATTERN_SEQUENCE,
}

# ── FUNÇÃO FINAL ─────────────────────────────────────────────────────────── #


def validate_password(
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    current_password_hash: Optional[str] = None,
) -> PasswordValidation:

    ctx = PasswordContext(
        password, first_name, last_name, current_password_hash
    )

    for step in PIPELINE:
        step(ctx)

    entropy = calculate_entropy(password)
    strength = classify_password(entropy, error_count=len(ctx.errors))

    if entropy > ENTROPY_SCORE_STRONG:
        ctx.score += ENTROPY_SCORE_STRONG_VALUE
    elif entropy > ENTROPY_SCORE_MEDIUM:
        ctx.score += ENTROPY_SCORE_MEDIUM_VALUE

    if len(password) < BONUS_LENGTH:
        ctx.suggestions.append(PasswordSuggestions.USE_PASSPHRASE)

    crack_time = estimate_crack_time(entropy)

    valid = not any(e in CRITICAL_ERRORS for e in ctx.errors)

    return PasswordValidation(
        valid=valid,
        erros=ctx.errors,
        strength_value=ctx.score,
        strength_avaliation=strength,
        suggestions=list(dict.fromkeys(ctx.suggestions)),
        crack_time=crack_time,
    )


# ── TEMPO DE QUEBRA ─────────────────────────────────────────────────────── #
#
# Aproximação: 2¹⁰ ≈ 10³  (erro ~2,4%)
#
# Com 10⁹ tentativas/s = 10³ × 10⁶ ≈ 2³⁰:
#   tentativas = 2^E
#   segundos   = 2^E / 2^30 = 2^(E-30)
#
# Convertemos escala de tempo também via 2¹⁰ ≈ 10³:
#   minuto  ≈  60 s  ≈ 2^6        →  bits_extra = 6
#   hora    ≈ 3600 s ≈ 2^12       →  bits_extra = 12
#   dia     ≈ 86400s ≈ 2^17       →  bits_extra = 17   (2^17=131072, real=86400)
#   ano     ≈ 3,2×10⁷s ≈ 2^25    →  bits_extra = 25   (2^25=33M,   real=31,5M)
#
# Todos os thresholds são expoentes de 2 — sem float arithmetic, sem overflow.
#
# Grandeza     | threshold (bits de E)   | real (s)   | approx (2^n)
# -------------|-------------------------|------------|-------------
# instantâneo  | E - 30 < 0             | < 1 s      |
# segundos     | 0  ≤ E-30 < 6          | 1-60 s     | 2⁰..2⁵
# minutos      | 6  ≤ E-30 < 12         | 1-60 min   | 2⁶..2¹¹
# horas        | 12 ≤ E-30 < 17         | 1-24 h     | 2¹²..2¹⁶
# dias         | 17 ≤ E-30 < 25         | 1-365 dias | 2¹⁷..2²⁴
# anos         | E-30 ≥ 25              | ≥ 1 ano    | 2²⁵+
#
# Para o número legível, calculamos 2^(E-30-bits_unidade) e exibimos
# como potência de 10 via 2¹⁰ ≈ 10³: n bits → 10^(n//10 * 3 + ajuste).
# Na prática, para exibição bastam os valores inteiros.

# Expoente de 2 equivalente a 10⁹ tentativas/segundo (2^30 ≈ 10^9)
_BITS_PER_SECOND = 30

# Limiares de escala em bits adicionais além de _BITS_PER_SECOND
_BITS_MINUTE = 6  # 2^6  = 64  ≈ 60
_BITS_HOUR = 12  # 2^12 = 4096 ≈ 3600
_BITS_DAY = 17  # 2^17 = 131072 ≈ 86400
_BITS_YEAR = 25  # 2^25 = 33M ≈ 31,5M


def _bits_to_human(bits: int, unit_bits: int, unit_name: str) -> str:
    """Converte bits de excesso em quantidade legível usando 2^10 ≈ 10^3."""
    excess = bits - unit_bits
    if excess <= 0:
        return f'1 {unit_name}'

    # Cada 10 bits ≈ 10^3 (mil); usamos isso para escala legível
    # Representamos como "~N" onde N é múltiplo aproximado de 10
    thousands = excess // 10  # quantos "mil" de excesso
    remainder = excess % 10  # bits restantes (0-9)
    base = 1 << remainder  # 2^remainder (1..512)

    if thousands == 0:
        return f'~{base} {unit_name}'
    suffix = ['mil', 'milhão', 'bilhão', 'trilhão', 'quadrilhão']
    if thousands <= len(suffix):
        return f'~{base} {suffix[thousands - 1]} de {unit_name}'
    return f'~10^{thousands * 3} {unit_name}'


def estimate_crack_time(entropy: float) -> str:
    # Trabalhamos com expoente inteiro (floor) para evitar floats
    e = int(entropy)
    net = e - _BITS_PER_SECOND  # bits acima de 1 tentativa/segundo

    if net < 0:
        return 'instantâneo'
    if net < _BITS_MINUTE:
        return _bits_to_human(net, 0, 'segundos')
    if net < _BITS_HOUR:
        return _bits_to_human(net, _BITS_MINUTE, 'minutos')
    if net < _BITS_DAY:
        return _bits_to_human(net, _BITS_HOUR, 'horas')
    if net < _BITS_YEAR:
        return _bits_to_human(net, _BITS_DAY, 'dias')
    return _bits_to_human(net, _BITS_YEAR, 'anos')
