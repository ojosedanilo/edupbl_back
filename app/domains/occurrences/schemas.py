"""
Schemas Pydantic do domínio de ocorrências.

Hierarquia:
  OccurrenceCreate → criação (campos obrigatórios)
  OccurrenceUpdate → atualização parcial (campos opcionais)
  OccurrencePublic → resposta da API
  OccurrenceList   → wrapper de listagem
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.domains.occurrences.enums import OccurrenceTypeEnum

# Limite de dias no passado para registrar uma ocorrência (configurável separadamente dos atrasos)
OCCURRENCE_MAX_DAYS_BACK = 7


class OccurrenceCreate(BaseModel):
    """Campos necessários para registrar uma nova ocorrência."""

    student_id: int
    title: str
    description: str
    occurrence_type: OccurrenceTypeEnum = OccurrenceTypeEnum.OUTROS
    occurred_at: Optional[datetime] = None  # Se omitido, usa o momento atual

    @field_validator('occurred_at')
    @classmethod
    def validate_occurred_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc)
        # Normaliza para UTC se naive
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        min_allowed = now - timedelta(days=OCCURRENCE_MAX_DAYS_BACK)
        if v < min_allowed:
            raise ValueError(
                f'occurred_at não pode ser mais de {OCCURRENCE_MAX_DAYS_BACK} dias no passado'
            )
        if v > now:
            raise ValueError('occurred_at não pode ser no futuro')
        return v


class OccurrenceUpdate(BaseModel):
    """
    Atualização parcial — todos os campos são opcionais.
    Apenas os campos enviados na requisição serão modificados.
    """

    student_id: int | None = None
    title: str | None = None
    description: str | None = None
    occurred_at: datetime | None = None
    occurrence_type: OccurrenceTypeEnum | None = None


class OccurrencePublic(BaseModel):
    """Representação pública de uma ocorrência retornada pela API."""

    id: int
    created_by_id: int | None  # None quando o criador foi deletado (SET NULL)
    student_id: int
    title: str
    description: str
    occurrence_type: OccurrenceTypeEnum
    occurred_at: datetime | None
    forwarded_to_coordinator: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OccurrenceList(BaseModel):
    """Wrapper de listagem de ocorrências."""

    occurrences: list[OccurrencePublic]
