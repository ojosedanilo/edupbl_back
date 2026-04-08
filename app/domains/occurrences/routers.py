"""
Rotas de ocorrências disciplinares.

Regras de autorização por endpoint:
  POST   /occurrences          → requer OCCURRENCES_CREATE (professor/coordenador)
  GET    /occurrences          → requer OCCURRENCES_VIEW_ALL (coordenador/admin)
  GET    /occurrences/me       → requer OCCURRENCES_VIEW_OWN (aluno vê as suas; professor vê as que criou)
  GET    /occurrences/{id}     → requer OCCURRENCES_VIEW_OWN + verificação por aluno
  PUT    /occurrences/{id}     → requer OCCURRENCES_EDIT (professor só edita as próprias)
  DELETE /occurrences/{id}     → requer OCCURRENCES_DELETE (professor só deleta as próprias)
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.occurrences.models import Occurrence
from app.domains.occurrences.schemas import (
    OccurrenceCreate,
    OccurrenceList,
    OccurrencePublic,
    OccurrenceUpdate,
)
from app.domains.users.models import User
from app.shared.db.database import get_session
from app.shared.notifications.dispatcher import notify_occurrence_created
from app.shared.rbac.dependencies import PermissionChecker
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.security import get_current_user

router = APIRouter(prefix='/occurrences', tags=['occurrences'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def _get_occurrence_or_404(
    occurrence_id: int, session: AsyncSession
) -> Occurrence:
    """Busca a ocorrência pelo id ou lança 404 se não existir."""
    occurrence = await session.scalar(
        select(Occurrence).where(Occurrence.id == occurrence_id)
    )
    if not occurrence:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Occurrence not found'
        )
    return occurrence


def _assert_can_modify(occurrence: Occurrence, current_user: User) -> None:
    """
    Professores só podem alterar ocorrências que eles próprios criaram.
    Coordenadores e admins podem alterar qualquer ocorrência.
    Lança 403 se a regra for violada.
    """
    if (
        current_user.role == UserRole.TEACHER
        and occurrence.created_by_id != current_user.id
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )


# --------------------------------------------------------------------------- #
# POST /occurrences — Criar ocorrência                                        #
# --------------------------------------------------------------------------- #


@router.post(
    '/',
    status_code=HTTPStatus.CREATED,
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_CREATE}))
    ],
)
async def create_occurrence(
    data: OccurrenceCreate,
    session: Session,
    current_user: CurrentUser,
):
    """
    Registra uma nova ocorrência sobre um aluno.

    O campo created_by_id é preenchido automaticamente com
    o usuário logado — não é aceito no corpo da requisição.
    """
    student = await session.get(User, data.student_id)
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Student not found'
        )

    occurrence = Occurrence(
        created_by_id=current_user.id,
        student_id=data.student_id,
        title=data.title,
        description=data.description,
        occurrence_type=data.occurrence_type,
    )

    session.add(occurrence)
    await session.commit()
    await session.refresh(occurrence)

    await notify_occurrence_created(occurrence.id)
    return occurrence


# --------------------------------------------------------------------------- #
# GET /occurrences — Listar todas (coordenador/admin)                        #
# --------------------------------------------------------------------------- #


@router.get(
    '/',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_ALL}))
    ],
)
async def list_all_occurrences(session: Session):
    """Retorna todas as ocorrências do sistema. Acesso restrito a coordenadores e admins."""
    result = await session.scalars(select(Occurrence))
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/me — Minhas ocorrências                                   #
# --------------------------------------------------------------------------- #


@router.get(
    '/me',
    response_model=OccurrenceList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_OWN}))
    ],
)
async def list_my_occurrences(session: Session, current_user: CurrentUser):
    """
    Lista ocorrências do usuário logado.

    - Aluno: ocorrências em que ele é o estudante envolvido.
    - Professor/outros: ocorrências que ele criou.
    """
    if current_user.role == UserRole.STUDENT:
        stmt = select(Occurrence).where(
            Occurrence.student_id == current_user.id
        )
    else:
        stmt = select(Occurrence).where(
            Occurrence.created_by_id == current_user.id
        )

    result = await session.scalars(stmt)
    return {'occurrences': result.all()}


# --------------------------------------------------------------------------- #
# GET /occurrences/{id} — Detalhe de uma ocorrência                         #
# --------------------------------------------------------------------------- #


@router.get(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_VIEW_OWN}))
    ],
)
async def get_occurrence(
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    """
    Retorna uma ocorrência específica.

    Alunos só podem visualizar ocorrências em que são o estudante envolvido.
    Professores e coordenadores podem ver qualquer uma (dentro de sua permissão).
    """
    occurrence = await _get_occurrence_or_404(occurrence_id, session)

    if (
        current_user.role == UserRole.STUDENT
        and occurrence.student_id != current_user.id
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Insufficient permissions',
        )

    return occurrence


# --------------------------------------------------------------------------- #
# PUT /occurrences/{id} — Atualizar ocorrência                              #
# --------------------------------------------------------------------------- #


@router.put(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_EDIT}))
    ],
)
async def update_occurrence(
    data: OccurrenceUpdate,
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    """
    Atualiza título e/ou descrição de uma ocorrência.

    Professores só podem editar ocorrências que eles próprios criaram.
    """
    occurrence = await _get_occurrence_or_404(occurrence_id, session)
    _assert_can_modify(occurrence, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(occurrence, field, value)

    await session.commit()
    await session.refresh(occurrence)
    return occurrence


# --------------------------------------------------------------------------- #
# DELETE /occurrences/{id} — Deletar ocorrência                             #
# --------------------------------------------------------------------------- #


@router.delete(
    '/{occurrence_id}',
    response_model=OccurrencePublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.OCCURRENCES_DELETE}))
    ],
)
async def delete_occurrence(
    session: Session,
    current_user: CurrentUser,
    occurrence_id: int = Path(alias='occurrence_id'),
):
    """
    Deleta permanentemente uma ocorrência.

    Professores só podem deletar ocorrências que eles próprios criaram.
    O refresh antes do delete garante que todos os campos estejam
    carregados para a resposta final.
    """
    occurrence = await _get_occurrence_or_404(occurrence_id, session)
    _assert_can_modify(occurrence, current_user)

    # Garante que todos os atributos escalares estejam em memória
    # antes do delete para que o objeto retornado na resposta seja completo
    await session.refresh(occurrence)
    await session.delete(occurrence)
    await session.commit()
    return occurrence
