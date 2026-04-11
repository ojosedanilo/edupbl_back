from typing import Optional

from pydantic import BaseModel, Field

from app.shared.rbac.roles import UserRole


class Message(BaseModel):
    message: str


class HealthResponse(BaseModel):
    """Resposta do endpoint de health check (GET /)."""

    message: str
    environment: str
    database_status: str  # 'online' | 'offline'
    database_url: str


class FilterPage(BaseModel):
    """Parâmetros de paginação para endpoints de listagem."""

    offset: int = Field(0, ge=0, description='Número de registros a pular')
    limit: int = Field(100, ge=1, description='Máximo de registros retornados')
    role: Optional[UserRole] = None
