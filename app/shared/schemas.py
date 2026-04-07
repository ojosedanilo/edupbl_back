from pydantic import BaseModel, Field


class Message(BaseModel):
    message: str


class FilterPage(BaseModel):
    """Parâmetros de paginação para endpoints de listagem."""

    offset: int = Field(0, ge=0, description='Número de registros a pular')
    limit: int = Field(100, ge=1, description='Máximo de registros retornados')
