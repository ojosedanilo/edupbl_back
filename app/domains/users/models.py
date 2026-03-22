from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import (
    Mapped,
    mapped_as_dataclass,
    mapped_column,
    relationship,
)

from app.shared.db.registry import mapper_registry
from app.shared.rbac.roles import UserRole

# Tabela de associação responsável ↔ aluno (many-to-many)
guardian_student = Table(
    'guardian_student',
    mapper_registry.metadata,
    Column(
        'guardian_id',
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'student_id',
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)


@mapped_as_dataclass(mapper_registry)
class Classroom:
    """Representa uma turma/sala da escola."""

    __tablename__ = 'classrooms'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Ex: "1º ano A", "2º ano B", "3º ano C"
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


@mapped_as_dataclass(mapper_registry)
class User:
    __tablename__ = 'users'
    __table_args__ = (
        # Constraint portável: validada na camada Python (schema Pydantic).
        # A CheckConstraint com regex usa sintaxe diferente em SQLite (~) e
        # PostgreSQL (REGEXP / GLOB), por isso é omitida aqui para evitar
        # erros nos testes (SQLite) e na produção (PostgreSQL).
        # A validação real é feita pelo field_validator em UserSchema.
        CheckConstraint(
            'length(username) > 0',
            name='ck_users_username_nonempty',
        ),
    )

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
    # Força troca de senha no primeiro login
    # (True para usuários importados via CSV)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Sala (obrigatório para alunos e professores DT, NULL para os demais)
    classroom_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('classrooms.id', ondelete='SET NULL'),
        default=None,
        nullable=True,
    )

    # Metadados
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now(), onupdate=func.now()
    )

    # ------------------------------------------------------------------ #
    # Relacionamentos (não participam do __init__ gerado pelo dataclass)  #
    # ------------------------------------------------------------------ #

    # Responsável → lista de alunos sob sua responsabilidade
    # Carregamento: selectin (2 queries — evita produto cartesiano em joins
    # auto-referentes e funciona igualmente bem no SQLite e PostgreSQL)
    students: Mapped[list['User']] = relationship(
        'User',
        secondary='guardian_student',
        primaryjoin='User.id == foreign(guardian_student.c.guardian_id)',
        secondaryjoin='User.id == foreign(guardian_student.c.student_id)',
        lazy='noload',
        init=False,
        default_factory=list,
        viewonly=False,
    )

    # Aluno → lista de responsáveis
    # Carregamento: selectin load (2 queries, evita produto cartesiano em M×N)
    guardians: Mapped[list['User']] = relationship(
        'User',
        secondary='guardian_student',
        primaryjoin='User.id == foreign(guardian_student.c.student_id)',
        secondaryjoin='User.id == foreign(guardian_student.c.guardian_id)',
        lazy='noload',
        init=False,
        default_factory=list,
        viewonly=False,
        overlaps='students',
    )

    # Sala (objeto, não só FK)
    classroom: Mapped['Classroom | None'] = relationship(
        'Classroom',
        lazy='noload',
        init=False,
        default=None,
        foreign_keys='User.classroom_id',
    )
