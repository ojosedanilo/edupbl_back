from datetime import datetime

from sqlalchemy import Boolean, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_as_dataclass, mapped_column, registry

from app.shared.rbac.roles import UserRole

table_registry = registry()


@mapped_as_dataclass(table_registry)
class User:
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Autenticação
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password: Mapped[str] = mapped_column(nullable=False)

    # Dados pessoais
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Role e permissões
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name='userrole',
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserRole.STUDENT,
        nullable=False,
    )

    # Flags especiais
    # Professor Diretor de Turma
    is_tutor: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Metadados
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now(), onupdate=func.now()
    )
