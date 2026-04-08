from enum import Enum


class OccurrenceTypeEnum(str, Enum):
    INDISCIPLINA = 'indisciplina'
    CELULAR = 'celular'
    DESRESPEITO = 'desrespeito'
    RENDIMENTO = 'rendimento'
    ATRASOS = 'atrasos'
    FALTAS = 'faltas'
    OUTROS = 'outros'
