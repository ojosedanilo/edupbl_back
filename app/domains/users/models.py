"""
Models SQLAlchemy do domínio de usuários.

Modelos:
  Classroom — representa uma turma/sala da escola
  User      — usuário do sistema (aluno, professor, responsável, etc.)

Tabela de associação:
  guardian_student — relação many-to-many entre responsável e aluno
"""

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

# Tabela de associação many-to-many entre responsável (guardian) e aluno (student).
# Ambas as FKs apontam para a mesma tabela `users`, por isso o modelo é auto-referente.
# ondelete='CASCADE' garante que as entradas são removidas junto com o usuário.
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
    """Representa uma turma/sala da escola (ex: '1º ano A', '3º ano B')."""

    __tablename__ = 'classrooms'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


@mapped_as_dataclass(mapper_registry)
class User:
    """
    Usuário do sistema — representa alunos, professores, responsáveis,
    coordenadores, porteiros e administradores.

    Nota sobre CheckConstraint:
      A validação de formato do username é feita pelo field_validator do
      Pydantic (UserSchema) em vez de CheckConstraint no banco, pois SQLite
      (usado nos testes) e PostgreSQL (produção) têm sintaxes de regex
      incompatíveis. O constraint abaixo apenas impede usernames vazios.
    """

    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint(
            'length(username) > 0',
            name='ck_users_username_nonempty',
        ),
    )

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # ── Autenticação ───────────────────────────────────────────────── #
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password: Mapped[str] = mapped_column(nullable=False)

    # ── Dados pessoais ─────────────────────────────────────────────── #
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Role e flags ───────────────────────────────────────────────── #
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name='userrole',
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserRole.STUDENT,
        nullable=False,
    )

    # Professor Diretor de Turma — concede permissões extras ao TEACHER
    is_tutor: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Força o usuário a trocar a senha no primeiro login
    # (definido como True em importações via CSV)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # ── Turma ──────────────────────────────────────────────────────── #
    # Obrigatório para alunos e professores DT; NULL para os demais.
    # SET NULL ao apagar a turma preserva o usuário sem turma vinculada.
    classroom_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('classrooms.id', ondelete='SET NULL'),
        default=None,
        nullable=True,
    )

    # ── Perfil / Contato ───────────────────────────────────────────── #
    # Caminho relativo ao avatar salvo em disco (ex: 'avatars/42.jpg').
    # NULL significa sem foto — o frontend exibe iniciais ou placeholder.
    # O arquivo é redimensionado para 256×256 px no upload antes de salvar.
    avatar_url: Mapped[str | None] = mapped_column(
        String(255),
        default=None,
        nullable=True,
    )

    # Telefone do usuário (ex: '+5585999990000') — usado para notificações WhatsApp/SMS.
    # Preenchido voluntariamente após o primeiro login (LGPD).
    # NULL significa que notificações só vão por e-mail.
    phone: Mapped[str | None] = mapped_column(
        String(20),
        default=None,
        nullable=True,
    )

    # ── Metadados ──────────────────────────────────────────────────── #
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now(), onupdate=func.now()
    )

    # ── Relacionamentos ────────────────────────────────────────────── #
    # Carregamento lazy='noload' (nenhuma query automática).
    # Carregue explicitamente com selectin_load() quando precisar acessar.
    #
    # Usamos selectin (2 queries separadas) em vez de join porque:
    # - Evita produto cartesiano em relacionamentos auto-referentes
    # - Funciona igualmente bem em SQLite e PostgreSQL

    # Responsável → lista de alunos sob sua responsabilidade
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

    # Sala associada ao usuário (objeto completo, não só o ID)
    classroom: Mapped['Classroom | None'] = relationship(
        'Classroom',
        lazy='noload',
        init=False,
        default=None,
        foreign_keys='User.classroom_id',
    )
