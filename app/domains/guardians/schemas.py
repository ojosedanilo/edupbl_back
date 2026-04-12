"""
Schemas Pydantic do domínio de guardiões (pais/responsáveis).

Todos os endpoints são read-only — guardiões não criam nem alteram dados.
Os schemas de Delay e Occurrence são reaproveitados dos domínios originais.
"""

from pydantic import BaseModel, ConfigDict


class ChildBasic(BaseModel):
    """Dados mínimos de um filho para listagem na UI do responsável."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    classroom_id: int | None = None
    avatar_url: str | None = None


class ChildrenListResponse(BaseModel):
    children: list[ChildBasic]
