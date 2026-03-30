"""
Schemas Pydantic do domínio de ocorrências.

Hierarquia:
  OccurrenceCreate → criação (campos obrigatórios)
  OccurrenceUpdate → atualização parcial (campos opcionais)
  OccurrencePublic → resposta da API
  OccurrenceList   → wrapper de listagem
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OccurrenceCreate(BaseModel):
    """Campos necessários para registrar uma nova ocorrência."""

    student_id: int
    title: str
    description: str


class OccurrenceUpdate(BaseModel):
    """
    Atualização parcial — todos os campos são opcionais.
    Apenas os campos enviados na requisição serão modificados.
    """

    student_id: int | None = None
    title: str | None = None
    description: str | None = None


class OccurrencePublic(BaseModel):
    """Representação pública de uma ocorrência retornada pela API."""

    id: int
    created_by_id: int | None  # None quando o criador foi deletado (SET NULL)
    student_id: int
    title: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OccurrenceList(BaseModel):
    """Wrapper de listagem de ocorrências."""

    occurrences: list[OccurrencePublic]
