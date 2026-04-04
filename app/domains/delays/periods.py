"""
Lógica de períodos para o domínio de atrasos.

get_expected_time() deriva os horários de início de aula diretamente
de PERIODS (schedules), que é a fonte de verdade do horário escolar.
Se a duração das aulas ou os intervalos mudarem no schedules, o
expected_time dos novos registros de atraso se atualiza automaticamente.
"""

from datetime import time

from app.domains.schedules.enums import PeriodTypeEnum
from app.domains.schedules.periods import PERIODS

# Janela máxima para desfazer uma decisão de aprovação/rejeição (em minutos)
UNDO_WINDOW_MINUTES = 5


def get_expected_time(arrival_time: time) -> time:
    """
    Retorna o horário de início do período em que o aluno deveria estar.

    Percorre os períodos de aula (ignora intervalos) em ordem e mantém
    o último cujo início é <= arrival_time. Se o aluno chegou antes do
    primeiro período, retorna o início do primeiro período.

    Exemplos (com o horário padrão):
      07:45 → 07:30  (1º período)
      09:50 → 09:30  (3º período, pós-intervalo)
      13:05 → 09:30  (ainda no último bloco da manhã)
      14:00 → 13:20  (1º período da tarde)
      15:30 → 15:20  (3º período da tarde)
    """
    # Filtra apenas os períodos de aula — intervalos não contam
    class_starts = [
        p.start
        for p in PERIODS.periods
        if p.type == PeriodTypeEnum.CLASS_PERIOD
    ]

    expected = class_starts[0]
    for period_start in class_starts:
        if arrival_time >= period_start:
            expected = period_start

    return expected
