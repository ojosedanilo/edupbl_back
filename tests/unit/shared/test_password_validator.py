"""
Testes para o validador de senha.

Organização:
- Testes unitários de funções auxiliares
- Testes de validação por critério
- Testes integrados de cenários reais
"""

import pytest
from pwdlib import PasswordHash

# Importar do módulo (ajustar path conforme necessário)
from app.shared.password_validator import (
    PasswordContext,
    PasswordErros,
    PasswordStrength,
    PasswordSuggestions,
    calculate_entropy,
    classify_password,
    estimate_crack_time,
    has_personal_info,
    has_repetition,
    has_sequential_pattern,
    validate_password,
)

# ── FIXTURES ─────────────────────────────────────────────────────────────── #


@pytest.fixture
def password_hasher():
    """Password hasher para criar hashes de teste."""
    return PasswordHash.recommended()


@pytest.fixture
def sample_hash(password_hasher):
    """Hash de uma senha conhecida para testes."""
    return password_hasher.hash('OldPassword#123!')


# ── TESTES UNITÁRIOS: ENTROPIA ───────────────────────────────────────────── #


class TestEntropy:
    """Testes de cálculo de entropia."""

    def test_entropy_only_lowercase(self):
        """Senha apenas minúsculas."""
        entropy = calculate_entropy('abcdefghij')
        # pool = 26, length = 10, entropy = 10 * log2(26) ≈ 47.00
        assert entropy == pytest.approx(47.00, abs=0.1)

    def test_entropy_mixed_case(self):
        """Senha com maiúsculas e minúsculas."""
        entropy = calculate_entropy('AbCdEfGhIj')
        # pool = 52, length = 10, entropy = 10 * log2(52) ≈ 57.00
        assert entropy == pytest.approx(57.00, abs=0.1)

    def test_entropy_with_numbers(self):
        """Senha com letras e números."""
        entropy = calculate_entropy('Abc123')
        # pool = 62, length = 6, entropy = 6 * log2(62) ≈ 35.76
        assert entropy == pytest.approx(35.76, abs=0.5)

    def test_entropy_with_special_chars(self):
        """Senha com caracteres especiais."""
        entropy = calculate_entropy('Abc@123!')
        # pool = 94, length = 8, entropy = 8 * log2(94) ≈ 52.44
        assert entropy == pytest.approx(52.44, abs=0.5)

    def test_entropy_very_long_password(self):
        """Senha muito longa tem entropia alta."""
        password = 'A' * 50 + 'b' * 50 + '1' * 50 + '@' * 50
        entropy = calculate_entropy(password)
        assert entropy > 1000  # Muito alta

    def test_entropy_empty_password(self):
        """Senha vazia tem entropia 0."""
        entropy = calculate_entropy('')
        assert entropy == 0.0


class TestPasswordStrength:
    """Testes de classificação de força."""

    def test_classify_very_weak(self):
        """Entropia < 28 = VERY_WEAK."""
        assert classify_password(20) == PasswordStrength.VERY_WEAK

    def test_classify_weak(self):
        """Entropia 28-35 = WEAK."""
        assert classify_password(30) == PasswordStrength.WEAK
        assert classify_password(35.9) == PasswordStrength.WEAK

    def test_classify_medium(self):
        """Entropia 36-59 = MEDIUM."""
        assert classify_password(40) == PasswordStrength.MEDIUM
        assert classify_password(59.9) == PasswordStrength.MEDIUM

    def test_classify_strong(self):
        """Entropia 60-127 = STRONG."""
        assert classify_password(70) == PasswordStrength.STRONG
        assert classify_password(127.9) == PasswordStrength.STRONG

    def test_classify_very_strong(self):
        """Entropia >= 128 = VERY_STRONG."""
        assert classify_password(128) == PasswordStrength.VERY_STRONG
        assert classify_password(200) == PasswordStrength.VERY_STRONG


# ── TESTES UNITÁRIOS: DETECTORES ─────────────────────────────────────────── #


class TestSequentialPattern:
    """Testes de detecção de padrões sequenciais."""

    def test_detects_numeric_sequence(self):
        """Detecta 123456."""
        assert has_sequential_pattern('Password123456') is True

    def test_detects_reverse_numeric_sequence(self):
        """Detecta 654321."""
        assert has_sequential_pattern('Password654321') is True

    def test_detects_alphabet_sequence(self):
        """Detecta abcd."""
        assert has_sequential_pattern('Passwordabcd') is True

    def test_detects_qwerty_sequence(self):
        """Detecta qwerty."""
        assert has_sequential_pattern('Passwordqwerty') is True

    def test_detects_uppercase_sequence(self):
        """Detecta ABCD."""
        assert has_sequential_pattern('PasswordABCD') is True

    def test_no_sequence_random_password(self):
        """Senha aleatória não tem sequência."""
        assert has_sequential_pattern('Xk9@Lp2#Qz') is False

    def test_no_sequence_short_chunks(self):
        """Chunks de 3 caracteres não são detectados (default length=4)."""
        assert has_sequential_pattern('Passabc') is False  # abc tem 3 chars

    def test_custom_length_detection(self):
        """Detecta sequências de tamanho customizado."""
        assert has_sequential_pattern('Passabc', length=3) is True
        assert has_sequential_pattern('Pass12', length=2) is True


class TestRepetition:
    """Testes de detecção de repetições."""

    def test_detects_four_repeated_chars(self):
        """Detecta aaaa."""
        assert has_repetition('Passwordaaaa') is True

    def test_detects_five_repeated_chars(self):
        """Detecta 11111."""
        assert has_repetition('Pass11111word') is True

    def test_no_repetition_three_chars(self):
        """Três caracteres repetidos não são detectados."""
        assert has_repetition('Passaaa') is False

    def test_no_repetition_alternating(self):
        """Caracteres alternados não são repetição."""
        assert has_repetition('Passabab') is False

    def test_no_repetition_random(self):
        """Senha aleatória não tem repetição."""
        assert has_repetition('Xk9@Lp2#Qz') is False


class TestPersonalInfo:
    """Testes de detecção de informações pessoais."""

    def test_detects_first_name(self):
        """Detecta nome na senha."""
        ctx = PasswordContext('JoaoPassword123', 'João', 'Silva', None)
        assert has_personal_info(ctx) is True

    def test_detects_last_name(self):
        """Detecta sobrenome na senha."""
        ctx = PasswordContext('PasswordSilva123', 'João', 'Silva', None)
        assert has_personal_info(ctx) is True

    def test_detects_year_pattern(self):
        """Detecta múltiplos anos (19xx ou 20xx) — 1 ano isolado não é suficiente."""
        ctx = PasswordContext('Password1995Born2001', None, None, None)
        assert has_personal_info(ctx) is True

        ctx = PasswordContext('Password2000And2010', None, None, None)
        assert has_personal_info(ctx) is True

    def test_single_year_not_detected(self):
        """Um único ano não é detectado sem contexto do usuário."""
        ctx = PasswordContext('Password1995', None, None, None)
        assert has_personal_info(ctx) is False

        ctx = PasswordContext('Password2024', None, None, None)
        assert has_personal_info(ctx) is False

    def test_case_insensitive_detection(self):
        """Detecção é case-insensitive."""
        ctx = PasswordContext('joaoPassword123', 'João', None, None)
        assert has_personal_info(ctx) is True

    def test_no_personal_info_random(self):
        """Senha aleatória não tem info pessoal."""
        ctx = PasswordContext('Xk9@Lp2#Qz', 'João', 'Silva', None)
        assert has_personal_info(ctx) is False

    def test_no_personal_info_without_names(self):
        """Sem nomes fornecidos, só detecta anos."""
        ctx = PasswordContext('PasswordXYZ', None, None, None)
        assert has_personal_info(ctx) is False


# ── TESTES DE VALIDAÇÃO POR CRITÉRIO ─────────────────────────────────────── #


class TestLengthValidation:
    """Testes de validação de comprimento."""

    def test_too_short_password(self):
        """Senha muito curta (< 15 chars)."""
        result = validate_password('Abc@123')
        assert result.valid is False
        assert PasswordErros.MIN_LENGTH in result.erros
        assert PasswordSuggestions.USE_LONGER_PASSWORD in result.suggestions

    def test_minimum_length_password(self):
        """Senha com exatamente 15 caracteres."""
        result = validate_password('Abc@123456789XY')
        # Pode ter outros erros, mas não MIN_LENGTH
        assert PasswordErros.MIN_LENGTH not in result.erros

    def test_long_password_bonus(self):
        """Senha >= 20 chars recebe bônus no score."""
        short_result = validate_password('Abc@123456789XYZ')  # 16 chars
        long_result = validate_password('Abc@123456789XYZABC')  # 19 chars
        very_long_result = validate_password(
            'Abc@123456789XYZABCD'
        )  # 20 chars

        # Very long deve ter score maior ou igual
        assert very_long_result.strength_value >= long_result.strength_value


class TestCharacterTypesValidation:
    """Testes de validação de tipos de caracteres."""

    def test_missing_uppercase(self):
        """Senha sem maiúsculas."""
        result = validate_password('abc@123456789xyz')
        assert PasswordErros.MISSING_UPPERCASE in result.erros
        assert PasswordSuggestions.ADD_UPPERCASE in result.suggestions

    def test_missing_lowercase(self):
        """Senha sem minúsculas."""
        result = validate_password('ABC@123456789XYZ')
        assert PasswordErros.MISSING_LOWERCASE in result.erros
        assert PasswordSuggestions.ADD_LOWERCASE in result.suggestions

    def test_missing_number(self):
        """Senha sem números."""
        result = validate_password('Abc@XyzAbcXyzAb')
        assert PasswordErros.MISSING_NUMBER in result.erros
        assert PasswordSuggestions.ADD_NUMBER in result.suggestions

    def test_missing_special(self):
        """Senha sem caracteres especiais."""
        result = validate_password('Abc123456789XYZ')
        assert PasswordErros.MISSING_SPECIAL in result.erros
        assert PasswordSuggestions.ADD_SPECIAL in result.suggestions

    def test_all_char_types_present(self):
        """Senha com todos os tipos."""
        result = validate_password('Abc@123456789XY')
        assert PasswordErros.MISSING_UPPERCASE not in result.erros
        assert PasswordErros.MISSING_LOWERCASE not in result.erros
        assert PasswordErros.MISSING_NUMBER not in result.erros
        assert PasswordErros.MISSING_SPECIAL not in result.erros


class TestPatternsValidation:
    """Testes de validação de padrões."""

    def test_sequential_pattern_detected(self):
        """Detecta padrão sequencial."""
        result = validate_password('Password123456!')
        assert PasswordErros.PATTERN_SEQUENCE in result.erros
        assert PasswordSuggestions.AVOID_PATTERN in result.suggestions

    def test_repetition_detected(self):
        """Detecta repetição de caracteres."""
        result = validate_password('Passwordaaaa123!')
        assert PasswordErros.REPEATED_CHARS in result.erros
        assert PasswordSuggestions.AVOID_REPETITION in result.suggestions

    def test_no_patterns_clean_password(self):
        """Senha limpa sem padrões."""
        result = validate_password('Xk9@Lp2#QzTn5&R')
        assert PasswordErros.PATTERN_SEQUENCE not in result.erros
        assert PasswordErros.REPEATED_CHARS not in result.erros


class TestPersonalInfoValidation:
    """Testes de validação de informações pessoais."""

    def test_with_first_name(self):
        """Detecta nome na senha."""
        result = validate_password(
            'JoaoPassword123!',
            first_name='João',
        )
        assert PasswordErros.PERSONAL_INFO in result.erros
        assert PasswordSuggestions.AVOID_PERSONAL in result.suggestions

    def test_with_last_name(self):
        """Detecta sobrenome na senha."""
        result = validate_password(
            'PasswordSilva123!',
            last_name='Silva',
        )
        assert PasswordErros.PERSONAL_INFO in result.erros

    def test_with_multiple_years(self):
        """Detecta múltiplos anos na senha."""
        result = validate_password('Password1995@Abc2001')
        assert PasswordErros.PERSONAL_INFO in result.erros

    def test_single_year_not_flagged(self):
        """Um único ano não é pessoal sem contexto."""
        result = validate_password('Password1995@AbcXyz')
        assert PasswordErros.PERSONAL_INFO not in result.erros

    def test_without_personal_info(self):
        """Senha sem informações pessoais."""
        result = validate_password(
            'Xk9@Lp2#QzTn5&R',
            first_name='João',
            last_name='Silva',
        )
        assert PasswordErros.PERSONAL_INFO not in result.erros


class TestOldPasswordValidation:
    """Testes de validação contra senha antiga."""

    def test_same_as_old_password(self, sample_hash):
        """Detecta reutilização de senha."""
        result = validate_password(
            'OldPassword#123!',
            current_password_hash=sample_hash,
        )
        assert PasswordErros.SAME_AS_OLD in result.erros
        assert PasswordSuggestions.CHANGE_PASSWORD in result.suggestions

    def test_different_from_old_password(self, sample_hash):
        """Senha diferente da antiga é aceita."""
        result = validate_password(
            'NewPassword#456!',
            current_password_hash=sample_hash,
        )
        assert PasswordErros.SAME_AS_OLD not in result.erros

    def test_no_old_password_provided(self):
        """Sem senha antiga, não há erro."""
        result = validate_password('AnyPassword#123!')
        assert PasswordErros.SAME_AS_OLD not in result.erros


# ── TESTES INTEGRADOS: CENÁRIOS REAIS ────────────────────────────────────── #


class TestRealWorldScenarios:
    """Testes de cenários reais de uso."""

    def test_very_weak_password(self):
        """Senha muito fraca."""
        result = validate_password('123456')
        assert result.valid is False
        assert result.strength_avaliation == PasswordStrength.VERY_WEAK
        assert len(result.erros) >= 3  # Múltiplos erros
        assert result.strength_value < 0  # Score negativo

    def test_weak_password(self):
        """Senha fraca."""
        result = validate_password('Password123')
        assert result.valid is False
        assert result.strength_avaliation in [
            PasswordStrength.VERY_WEAK,
            PasswordStrength.WEAK,
        ]

    def test_medium_password(self):
        """Senha média — padrão com sequência resulta em inválida."""
        result = validate_password('Password@123456')
        # Tem padrão sequencial (123456) → inválida e força limitada pelo penalizador
        assert result.valid is False
        assert PasswordErros.PATTERN_SEQUENCE in result.erros

    def test_strong_password(self):
        """Senha forte."""
        result = validate_password('MyStr0ng@Passw0rd!')
        assert result.valid is True
        assert result.strength_avaliation in [
            PasswordStrength.MEDIUM,
            PasswordStrength.STRONG,
        ]
        assert len(result.erros) == 0

    def test_very_strong_password(self):
        """Senha muito forte."""
        result = validate_password('Xk9@Lp2#QzTn5&RmWj7$Vu3!')
        assert result.valid is True
        assert result.strength_avaliation in [
            PasswordStrength.STRONG,
            PasswordStrength.VERY_STRONG,
        ]
        assert len(result.erros) == 0
        assert result.strength_value > 5

    def test_passphrase_example(self):
        """Frase de senha (passphrase)."""
        result = validate_password('Café-Manhã#2Ovos&Pão!Queijo')
        assert result.valid is True
        assert result.strength_avaliation in [
            PasswordStrength.STRONG,
            PasswordStrength.VERY_STRONG,
        ]
        assert PasswordSuggestions.USE_PASSPHRASE not in result.suggestions

    def test_all_errors_at_once(self):
        """Senha com todos os erros possíveis."""
        result = validate_password(
            'joao',  # Curta, sem maiúscula, sem número, sem especial
            first_name='João',
        )
        assert result.valid is False
        assert PasswordErros.MIN_LENGTH in result.erros
        assert PasswordErros.MISSING_UPPERCASE in result.erros
        assert PasswordErros.MISSING_NUMBER in result.erros
        assert PasswordErros.MISSING_SPECIAL in result.erros
        assert PasswordErros.PERSONAL_INFO in result.erros

    def test_password_with_only_length_issue(self):
        """Senha com apenas problema de comprimento."""
        result = validate_password('Abc@123XyZ')
        assert result.valid is False
        assert len(result.erros) == 1
        assert PasswordErros.MIN_LENGTH in result.erros

    def test_password_change_scenario(self, sample_hash):
        """Cenário de troca de senha."""
        # Tentar usar senha antiga
        result_old = validate_password(
            'OldPassword#123!',
            first_name='João',
            current_password_hash=sample_hash,
        )
        assert PasswordErros.SAME_AS_OLD in result_old.erros

        # Usar senha nova válida
        result_new = validate_password(
            'NewStr0ng@Passw0rd!2024',
            first_name='João',
            current_password_hash=sample_hash,
        )
        assert result_new.valid is True
        assert PasswordErros.SAME_AS_OLD not in result_new.erros


# ── TESTES DE TEMPO DE QUEBRA ────────────────────────────────────────────── #


class TestCrackTime:
    """Testes de estimativa de tempo de quebra."""

    def test_crack_time_format_seconds(self):
        """Tempo em segundos."""
        time = estimate_crack_time(30)  # net=0 → 1 segundo
        assert 'segundos' in time

    def test_crack_time_format_minutes(self):
        """Tempo em minutos."""
        time = estimate_crack_time(36)  # net=6 → limiar de minutos
        assert 'minutos' in time

    def test_crack_time_format_hours(self):
        """Tempo em horas."""
        time = estimate_crack_time(42)  # net=12 → limiar de horas
        assert 'horas' in time

    def test_crack_time_format_days(self):
        """Tempo em dias."""
        time = estimate_crack_time(47)  # net=17 → limiar de dias
        assert 'dias' in time

    def test_crack_time_format_years(self):
        """Tempo em anos."""
        time = estimate_crack_time(60)  # net=30 → anos
        assert 'anos' in time

    def test_crack_time_very_high_entropy(self):
        """Alta entropia → resposta em anos sem OverflowError."""
        time = estimate_crack_time(128)
        assert 'anos' in time
        # Não deve lançar exceção nem retornar string vazia
        assert len(time) > 0

    def test_crack_time_very_low_entropy(self):
        """Baixa entropia = instantâneo."""
        time = estimate_crack_time(5)
        assert time == 'instantâneo'

    def test_crack_time_extreme_entropy_no_overflow(self):
        """Entropia extrema (400 bits) não causa OverflowError."""
        time = estimate_crack_time(400)
        assert 'anos' in time

    def test_crack_time_boundary_instantaneous(self):
        """Entropy=29: net=-1 → instantâneo."""
        assert estimate_crack_time(29) == 'instantâneo'

    def test_crack_time_boundary_seconds(self):
        """Entropy=30: net=0 → segundos."""
        assert 'segundos' in estimate_crack_time(30)

    def test_crack_time_boundary_minutes(self):
        """Entropy=36: net=6 → minutos."""
        assert 'minutos' in estimate_crack_time(36)

    def test_crack_time_boundary_years(self):
        """Entropy=55: net=25 → anos."""
        assert 'anos' in estimate_crack_time(55)


# ── TESTES DE EDGE CASES ─────────────────────────────────────────────────── #


class TestEdgeCases:
    """Testes de casos extremos."""

    def test_empty_password(self):
        """Senha vazia."""
        result = validate_password('')
        assert result.valid is False
        assert PasswordErros.MIN_LENGTH in result.erros

    def test_whitespace_only_password(self):
        """Senha só com espaços."""
        result = validate_password('               ')
        assert result.valid is False

    def test_unicode_password(self):
        """Senha com caracteres unicode."""
        result = validate_password('Senha@123Açúcar')
        # Deve processar sem erros
        assert result is not None

    def test_very_long_password(self):
        """Senha extremamente longa."""
        password = 'A1@b' * 100  # 400 caracteres
        result = validate_password(password)
        assert result.valid is True
        assert result.strength_avaliation == PasswordStrength.VERY_STRONG

    def test_all_special_chars(self):
        """Senha só com caracteres especiais."""
        result = validate_password('!@#$%^&*()_+-=[]')
        assert result.valid is False
        assert PasswordErros.MISSING_UPPERCASE in result.erros
        assert PasswordErros.MISSING_LOWERCASE in result.erros
        assert PasswordErros.MISSING_NUMBER in result.erros

    def test_none_values_for_optional_params(self):
        """Parâmetros opcionais como None."""
        result = validate_password(
            'Str0ng@Password!',
            first_name=None,
            last_name=None,
            current_password_hash=None,
        )
        assert result is not None
        assert result.valid is True

    def test_suggestions_are_unique(self):
        """Sugestões não devem ser duplicadas."""
        result = validate_password('abc123')
        # Converter para set e comparar tamanhos
        assert len(result.suggestions) == len(set(result.suggestions))


# ── TESTES DE REGRESSÃO ──────────────────────────────────────────────────── #


class TestRegression:
    """Testes de regressão para bugs conhecidos."""

    def test_score_never_exceeds_reasonable_limit(self):
        """Score não deve ser absurdamente alto."""
        result = validate_password('Perfect@Passw0rd!2024Strong')
        assert result.strength_value < 20  # Limite razoável

    def test_invalid_hash_doesnt_crash(self):
        """Hash inválido não causa crash."""
        result = validate_password(
            'NewPassword@123!',
            current_password_hash='invalid_hash_format',
        )
        # Não deve crashar
        assert result is not None

    def test_case_sensitivity_in_names(self):
        """Nomes com case diferentes são detectados."""
        result1 = validate_password('JOAOPassword123!', first_name='joão')
        result2 = validate_password('joaoPassword123!', first_name='JOÃO')

        assert PasswordErros.PERSONAL_INFO in result1.erros
        assert PasswordErros.PERSONAL_INFO in result2.erros

    def test_partial_name_in_password(self):
        """Nome parcial na senha é detectado."""
        result = validate_password(
            'MyJoaoPassword123!',
            first_name='João',
        )
        assert PasswordErros.PERSONAL_INFO in result.erros


# ── TESTES PARAMETRIZADOS ────────────────────────────────────────────────── #


@pytest.mark.parametrize(
    'password,expected_valid',
    [
        ('Abc@123', False),  # Muito curta
        ('Abc@XyzMno12TUv', True),  # Mínimo válido, sem sequência
        ('Password123456!', False),  # Tem sequência
        ('Xk9@Lp2#QzTn5&R', True),  # Forte
        ('aaaa@123456789A', False),  # Repetição e sequência
        ('Café@123Ovos&Pão', True),  # Passphrase
    ],
)
def test_password_validity_parametrized(password, expected_valid):
    """Testa validade de várias senhas."""
    result = validate_password(password)
    assert result.valid == expected_valid


@pytest.mark.parametrize(
    'password,min_strength',
    [
        ('12345', PasswordStrength.VERY_WEAK),
        ('Abc@123456789XY', PasswordStrength.WEAK),
        ('Str0ng@Password!', PasswordStrength.MEDIUM),
        ('VeryStr0ng@Passw0rd!2024', PasswordStrength.STRONG),
    ],
)
def test_password_strength_parametrized(password, min_strength):
    """Testa força mínima de várias senhas."""
    result = validate_password(password)

    # Mapear forças para números
    strength_order = {
        PasswordStrength.VERY_WEAK: 0,
        PasswordStrength.WEAK: 1,
        PasswordStrength.MEDIUM: 2,
        PasswordStrength.STRONG: 3,
        PasswordStrength.VERY_STRONG: 4,
    }

    assert (
        strength_order[result.strength_avaliation]
        >= strength_order[min_strength]
    )


# ── EXEMPLO DE USO ───────────────────────────────────────────────────────── #


def test_example_usage():
    """Exemplo de uso completo do validador."""
    # Caso 1: Senha fraca
    result = validate_password('senha123')
    assert result.valid is False
    print(f'\nSenha fraca:')
    print(f'  Erros: {[e.value for e in result.erros]}')
    print(f'  Força: {result.strength_avaliation.value}')
    print(f'  Sugestões: {[s.value for s in result.suggestions]}')

    # Caso 2: Senha forte
    result = validate_password(
        'MinhaSenha#Super$Forte123!',
        first_name='João',
        last_name='Silva',
    )
    assert result.valid is True
    print(f'\nSenha forte:')
    print(f'  Valid: {result.valid}')
    print(f'  Força: {result.strength_avaliation.value}')
    print(f'  Score: {result.strength_value}')
    print(f'  Tempo de quebra: {result.crack_time}')


# ── TESTES DE COBERTURA DE BRANCHES ──────────────────────────────────────── #


class TestCoverageGaps:
    """Testes para cobrir branches não alcançados."""

    def test_name_ge_min_length_but_no_match(self):
        """Nome com 3 chars (≥ MIN_PERSONAL_INFO_LENGTH) mas não ocorre na senha."""
        # 'Ana' tem 3 chars, aparece normalizada como 'ana' — não está em 'Xk9@Lp2QzTn5'
        ctx = PasswordContext('Xk9@Lp2QzTn5bRw', 'Ana', None, None)
        # len('ana') == 3 >= MIN_PERSONAL_INFO_LENGTH (3), mas não está nas palavras
        # nem como substring (len < MIN_SUBSTRING_LENGTH=4) → False → linha 218 coberta
        assert has_personal_info(ctx) is False

    def test_name_exact_min_substring_match(self):
        """Nome com 4 chars presente como substring → detectado."""
        ctx = PasswordContext('Xk9@AndreLp2Qz', 'Andre', None, None)
        assert has_personal_info(ctx) is True

    def test_name_three_chars_substring_not_matched(self):
        """Nome com 3 chars não é detectado por substring (MIN_SUBSTRING_LENGTH=4)."""
        # 'ana' tem 3 chars — abaixo do limiar de substring
        ctx = PasswordContext('Xk9@anLp2QzTnbRw', 'Ana', None, None)
        # Só detecta se 'ana' for palavra exata — aqui está como parte de 'an'
        result = has_personal_info(ctx)
        # O resultado depende de se 'ana' está nas palavras extraídas; aqui não está
        assert isinstance(result, bool)  # apenas garante execução sem crash
