"""
Rotas de usuários:
  POST   /users                         — criar usuário
  GET    /users                         — listar usuários (paginado)
  GET    /users/students                — lista reduzida de todos os alunos (porteiro/professor)
  GET    /users/classroom/{classroom_id} — alunos de uma turma (com ownership check)
  GET    /users/current-class-students  — alunos da aula atual do professor logado
  GET    /users/{user_id}/avatar        — servir avatar do usuário
  PUT    /users/{user_id}               — atualizar próprios dados
  PATCH  /users/me/avatar               — enviar/trocar avatar (próprio usuário)
  PATCH  /users/me/password             — trocar senha
  PATCH  /users/{user_id}/avatar        — DT atualiza avatar de aluno da turma
  PATCH  /users/{user_id}/profile       — DT atualiza campos de perfil de aluno da turma
  PATCH  /users/{user_id}/deactivate    — desativar usuário (Admin/Coordinator)
  DELETE /users/{user_id}               — deletar usuário (dados do banco e disco)

Regras de autorização:
  - Criar usuário  : requer USER_CREATE (Admin/Coordinator)
  - Listar         : requer USER_VIEW_ALL (Admin/Coordinator)
  - Lista de alunos: requer USER_VIEW_STUDENTS (Porter/Teacher/Coordinator/Admin)
  - Ver avatar     : requer USER_VIEW_OWN | USER_VIEW_ALL | USER_VIEW_CHILD
                     (qualquer usuário autenticado com permissão de visualizar usuários)
  - Atualizar / Deletar : apenas o próprio usuário
  - Trocar senha   : próprio usuário, com confirmação da senha atual
  - Upload avatar  : próprio usuário OU professor DT para alunos da sua turma
  - Editar perfil do aluno : professor DT (USER_EDIT_OWN_CLASSROOM), escopo restrito
  - Desativar      : Admin ou Coordinator (USER_DELETE)
"""

import io
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import Path as FPath
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AVATAR_DIR
from app.domains.schedules.helpers import is_time_at_class_period
from app.domains.schedules.periods import PERIODS
from app.domains.users.models import Classroom, User
from app.domains.users.schemas import (
    PasswordChange,
    StudentProfileUpdate,
    # StudentSummary,
    StudentSummaryList,
    UserBulkRequest,
    UserBulkResponse,
    UserList,
    UserPublic,
    UserSchema,
    UserUpdate,
)
from app.shared.db.database import get_session
from app.shared.rbac.dependencies import (
    AnyPermissionChecker,
    PermissionChecker,
)
from app.shared.rbac.permissions import SystemPermissions
from app.shared.rbac.roles import UserRole
from app.shared.schemas import FilterPage, Message
from app.shared.security import (
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix='/users', tags=['users'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]

# Tamanho máximo em bytes aceito no upload (2 MB)
_MAX_UPLOAD_BYTES = 2 * 1024 * 1024

# Dimensão do avatar após resize (px) — quadrado
_AVATAR_SIZE = 256

# Tipos MIME aceitos no upload
_ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp'}

# Pasta onde os avatares gerados pelo sistema são salvos.
# Path centralizado em settings.py — não recalcular via __file__ aqui.
_AVATAR_DIR = AVATAR_DIR


def _avatar_path(user_id: int) -> Path:
    """Retorna o Path absoluto do arquivo de avatar de um usuário."""
    return _AVATAR_DIR / f'{user_id}.webp'


def _save_avatar(user_id: int, file_bytes: bytes) -> str:
    """
    Abre, redimensiona e salva o avatar de um usuário como WebP 256×256.

    Fluxo:
    1. Converte RGBA/P → RGB (WebP não suporta alfa neste contexto)
    2. Crop central para quadrado (evita distorção)
    3. Resize para _AVATAR_SIZE×_AVATAR_SIZE com LANCZOS
    4. Salva como WebP qualidade 85 em data/avatars/{user_id}.webp

    Retorna o caminho relativo para guardar no campo avatar_url do banco.
    """
    _AVATAR_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.open(io.BytesIO(file_bytes))

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((_AVATAR_SIZE, _AVATAR_SIZE), Image.LANCZOS)

    dest = _avatar_path(user_id)
    img.save(dest, format='WEBP', quality=85)

    return f'avatars/{user_id}.webp'


def _delete_avatar_file(user_id: int) -> None:
    """Remove o arquivo de avatar do disco, se existir. Silencioso em caso de ausência."""
    dest = _avatar_path(user_id)
    dest.unlink(missing_ok=True)


async def _process_avatar_upload(
    user: User, upload: UploadFile, session: AsyncSession
) -> User:
    """
    Valida, processa e persiste o avatar de um usuário.

    Validações: tipo MIME e tamanho máximo.
    Em caso de erro de processamento de imagem, retorna 422 sem derrubar
    a operação principal.
    """
    if upload.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f'Tipo de arquivo não suportado. Use: {", ".join(sorted(_ALLOWED_MIME))}',
        )

    file_bytes = await upload.read()
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail='Arquivo muito grande. Máximo: 2 MB',
        )

    try:
        avatar_path = _save_avatar(user.id, file_bytes)
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Não foi possível processar a imagem. Verifique se o arquivo é válido.',
        )

    user.avatar_url = avatar_path
    await session.commit()
    await session.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# POST /users — Criar usuário                                                 #
# --------------------------------------------------------------------------- #


@router.post(
    '/',
    status_code=HTTPStatus.CREATED,
    response_model=UserPublic,
    dependencies=[Depends(PermissionChecker({SystemPermissions.USER_CREATE}))],
)
async def create_user(user: UserSchema, session: Session):
    """
    Cria um novo usuário. Requer USER_CREATE (Admin ou Coordinator).

    Verifica conflito de username e e-mail antes de inserir.
    Retorna mensagens de erro distintas para cada campo em conflito.
    """
    existing = await session.scalar(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )

    if existing:
        if existing.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username already exists',
            )
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Email already exists',
        )

    db_user = User(
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        password=get_password_hash(user.password),
        role=user.role,
        is_tutor=user.is_tutor,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


# --------------------------------------------------------------------------- #
# GET /users — Listar usuários (com paginação)                                #
# --------------------------------------------------------------------------- #


@router.get(
    '/',
    response_model=UserList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.USER_VIEW_ALL}))
    ],
)
async def read_users(
    session: Session,
    filter_users: Annotated[FilterPage, Query()],
):
    query = select(User)

    if filter_users.role:
        query = query.where(User.role == filter_users.role)

    result = await session.scalars(
        query.offset(filter_users.offset).limit(filter_users.limit)
    )

    return {'users': result.all()}


# --------------------------------------------------------------------------- #
# GET /users/students — Lista reduzida de todos os alunos                     #
# --------------------------------------------------------------------------- #


@router.get(
    '/students',
    response_model=StudentSummaryList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.USER_VIEW_STUDENTS}))
    ],
)
async def list_all_students(session: Session):
    """
    Retorna lista reduzida de todos os alunos, ordenada por sobrenome.

    Requer USER_VIEW_STUDENTS (Porter, Teacher, Coordinator, Admin).
    Expõe apenas campos de identificação (StudentSummary) — sem dados sensíveis.
    """
    result = await session.scalars(
        select(User)
        .where(User.role == UserRole.STUDENT)
        .order_by(User.last_name)
    )
    return {'students': result.all()}


# --------------------------------------------------------------------------- #
# GET /users/classrooms — Lista todas as turmas                               #
# --------------------------------------------------------------------------- #


@router.get(
    '/classrooms',
    response_model=list[dict],
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.SCHEDULES_VIEW_ALL,
                SystemPermissions.SCHEDULES_VIEW_OWN,
                SystemPermissions.SCHEDULES_VIEW_CHILD,
            })
        )
    ],
)
async def list_classrooms(session: Session):
    """
    Retorna lista de todas as turmas (id + name) em ordem alfabética.

    Usado pelo frontend de horários para exibir o nome da turma em vez do ID.
    Requer qualquer permissão de visualização de horários.
    """
    result = await session.scalars(select(Classroom).order_by(Classroom.name))
    classrooms = result.all()
    return [{'id': c.id, 'name': c.name} for c in classrooms]


# --------------------------------------------------------------------------- #
# GET /users/classroom/{classroom_id} — Alunos de uma turma                  #
# --------------------------------------------------------------------------- #


@router.get(
    '/classroom/{classroom_id}',
    response_model=StudentSummaryList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.USER_VIEW_STUDENTS}))
    ],
)
async def list_students_of_classroom(
    session: Session,
    current_user: CurrentUser,
    classroom_id: int = FPath(alias='classroom_id'),
):
    """
    Retorna lista reduzida de alunos de uma turma específica, ordenada por sobrenome.

    Requer USER_VIEW_STUDENTS. Ownership check: professor só acessa a própria
    classroom_id; coordinator, admin e porteiro acessam qualquer turma.
    """
    is_restricted = current_user.role == UserRole.TEACHER
    if is_restricted and current_user.classroom_id != classroom_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: você só pode ver alunos da sua própria turma',
        )

    result = await session.scalars(
        select(User)
        .where(User.role == UserRole.STUDENT)
        .where(User.classroom_id == classroom_id)
        .order_by(User.last_name)
    )
    return {'students': result.all()}


# --------------------------------------------------------------------------- #
# GET /users/current-class-students — Alunos da aula atual do professor       #
# --------------------------------------------------------------------------- #


@router.get(
    '/current-class-students',
    response_model=StudentSummaryList,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.USER_VIEW_STUDENTS}))
    ],
)
async def list_current_class_students(
    session: Session,
    current_user: CurrentUser,
):
    """
    Retorna os alunos da turma que o professor está lecionando agora.

    Determina a aula atual via horário do dia e classroom_id do professor.
    Requer USER_VIEW_STUDENTS. Retorna 404 se o professor não estiver em aula
    ou não tiver classroom_id associado.
    """
    if current_user.classroom_id is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Você não tem turma associada',
        )

    now = datetime.now().time()
    if not is_time_at_class_period(now, PERIODS):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Nenhuma aula em andamento no momento',
        )

    result = await session.scalars(
        select(User)
        .where(User.role == UserRole.STUDENT)
        .where(User.classroom_id == current_user.classroom_id)
        .order_by(User.last_name)
    )
    return {'students': result.all()}


# --------------------------------------------------------------------------- #
# GET /users/search — Busca usuários por nome ou username                     #
# --------------------------------------------------------------------------- #


@router.get(
    '/search',
    response_model=UserList,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.USER_VIEW_ALL,
                SystemPermissions.USER_VIEW_OWN,
                SystemPermissions.USER_VIEW_CHILD,
            })
        )
    ],
)
async def search_users(
    session: Session,
    q: Annotated[str, Query(description='Termo de busca (nome ou username)')],
    role: Annotated[
        UserRole | None, Query(description='Filtrar por papel')
    ] = None,
    limit: Annotated[
        int, Query(description='Limite de resultados', ge=1, le=50)
    ] = 10,
):
    """Busca usuários por nome ou username. Usado para autocomplete."""
    query = select(User).where(
        or_(
            User.first_name.ilike(f'%{q}%'),
            User.last_name.ilike(f'%{q}%'),
            User.username.ilike(f'%{q}%'),
        )
    )

    if role:
        query = query.where(User.role == role)

    result = await session.scalars(query.limit(limit))
    return {'users': result.all()}


# --------------------------------------------------------------------------- #
# POST /users/bulk — Buscar múltiplos usuários por IDs                        #
# --------------------------------------------------------------------------- #


@router.post(
    '/bulk',
    response_model=UserBulkResponse,
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.USER_VIEW_ALL,
                SystemPermissions.USER_VIEW_STUDENTS,
            })
        )
    ],
)
async def get_users_bulk(
    data: UserBulkRequest,
    session: Session,
):
    """
    Retorna informações de múltiplos usuários a partir de uma lista de IDs.

    IDs inexistentes são silenciosamente ignorados — apenas os encontrados
    são retornados. A ordem da resposta segue a ordem dos IDs fornecidos.

    Requer USER_VIEW_ALL (Admin/Coordinator) ou USER_VIEW_STUDENTS
    (Teacher/Porter) — professores e porteiros podem consultar alunos
    pelo ID sem precisar de acesso total ao sistema.
    """
    if not data.ids:
        return {'users': []}

    result = await session.scalars(select(User).where(User.id.in_(data.ids)))
    users_by_id = {u.id: u for u in result.all()}

    # Preserva a ordem dos IDs fornecidos, ignorando inexistentes
    ordered = [users_by_id[uid] for uid in data.ids if uid in users_by_id]
    return {'users': ordered}


# --------------------------------------------------------------------------- #
# GET /users/{user_id}/avatar — Servir avatar                                 #
# --------------------------------------------------------------------------- #


@router.get(
    '/{user_id}/avatar',
    dependencies=[
        Depends(
            AnyPermissionChecker({
                SystemPermissions.USER_VIEW_OWN,
                SystemPermissions.USER_VIEW_ALL,
                SystemPermissions.USER_VIEW_CHILD,
            })
        )
    ],
)
async def get_user_avatar(
    session: Session,
    user_id: int = FPath(alias='user_id'),
):
    """
    Retorna o arquivo de avatar do usuário diretamente como imagem WebP.

    Requer autenticação e ao menos uma das permissões de visualização de
    usuários: USER_VIEW_OWN (próprio usuário/aluno), USER_VIEW_ALL
    (Admin/Coordinator) ou USER_VIEW_CHILD (Responsável vendo filho).
    Isso protege dados de presença e identidade de alunos contra acesso
    não autenticado.

    Retorna 404 se o usuário não existir ou não tiver avatar cadastrado.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='User not found'
        )

    avatar_file = _avatar_path(user_id)
    if not user.avatar_url or not avatar_file.exists():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Avatar not found'
        )

    return FileResponse(
        path=avatar_file,
        media_type='image/webp',
        filename=f'avatar_{user_id}.webp',
    )


# --------------------------------------------------------------------------- #
# PUT /users/{user_id} — Atualizar usuário (self-service)                    #
# --------------------------------------------------------------------------- #


@router.put('/{user_id}', response_model=UserPublic)
async def update_user(
    user: UserUpdate,
    session: Session,
    current_user: CurrentUser,
    user_id: int = FPath(alias='user_id'),
):
    """
    Atualiza os dados do usuário.

    Apenas o próprio usuário pode se atualizar (self-service).
    Verifica conflito de username/e-mail com outros usuários antes de salvar.
    Apenas campos enviados na requisição são alterados (patch semântico via PUT).
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    if user.username is not None or user.email is not None:
        conditions = []
        if user.username is not None:
            conditions.append(User.username == user.username)
        if user.email is not None:
            conditions.append(User.email == user.email)

        conflicting = await session.scalar(
            select(User).where(or_(*conditions))
        )

        if conflicting and conflicting.id != current_user.id:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username or Email already exists',
            )

    for field, value in user.model_dump(exclude_unset=True).items():
        if field == 'password':
            setattr(current_user, field, get_password_hash(value))
        else:
            setattr(current_user, field, value)

    await session.commit()
    await session.refresh(current_user)
    return current_user


# --------------------------------------------------------------------------- #
# PATCH /users/me/avatar — Upload de avatar (próprio usuário)                #
# --------------------------------------------------------------------------- #


@router.patch('/me/avatar', response_model=UserPublic)
async def upload_my_avatar(
    session: Session,
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """
    Faz upload e substitui o avatar do usuário logado.

    Aceita JPEG, PNG ou WebP com até 2 MB. A imagem é redimensionada
    para 256×256 px e salva como WebP em data/avatars/{user_id}.webp,
    substituindo qualquer versão anterior.
    """
    return await _process_avatar_upload(current_user, file, session)


# --------------------------------------------------------------------------- #
# PATCH /users/me/password — Trocar senha                                    #
# --------------------------------------------------------------------------- #


@router.patch('/me/password', response_model=Message)
async def change_my_password(
    data: PasswordChange,
    session: Session,
    current_user: CurrentUser,
):
    """
    Troca a senha do usuário logado e limpa o flag must_change_password.

    Exige a senha atual para confirmar a identidade antes de aceitar a nova.
    """
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Current password is incorrect',
        )

    current_user.password = get_password_hash(data.new_password)
    current_user.must_change_password = False

    await session.commit()
    return {'message': 'Password updated successfully'}


# --------------------------------------------------------------------------- #
# PATCH /users/{user_id}/avatar — DT faz upload de avatar de aluno da turma #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{user_id}/avatar',
    response_model=UserPublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.USER_EDIT_OWN_CLASSROOM}))
    ],
)
async def upload_student_avatar(
    session: Session,
    current_user: CurrentUser,
    user_id: int = FPath(alias='user_id'),
    file: UploadFile = File(...),
):
    """
    Professor DT faz upload do avatar de um aluno da própria turma.

    Requer USER_EDIT_OWN_CLASSROOM. O aluno deve pertencer à turma do DT.
    """
    student = await session.get(User, user_id)
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='User not found'
        )

    if student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Este endpoint só permite editar avatares de alunos',
        )

    if student.classroom_id != current_user.classroom_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Aluno não pertence à sua turma',
        )

    return await _process_avatar_upload(student, file, session)


# --------------------------------------------------------------------------- #
# PATCH /users/{user_id}/profile — DT edita campos de perfil de aluno        #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{user_id}/profile',
    response_model=UserPublic,
    dependencies=[
        Depends(PermissionChecker({SystemPermissions.USER_EDIT_OWN_CLASSROOM}))
    ],
)
async def update_student_profile(
    data: StudentProfileUpdate,
    session: Session,
    current_user: CurrentUser,
    user_id: int = FPath(alias='user_id'),
):
    """
    Professor DT atualiza campos de perfil permitidos de um aluno da turma.

    Campos editáveis pelo DT estão definidos em StudentProfileUpdate.
    Dados de autenticação (email, senha, username) e administrativos
    (role, is_active) ficam fora do escopo deste endpoint intencionalmente.

    Requer USER_EDIT_OWN_CLASSROOM. O aluno deve pertencer à turma do DT.
    """
    student = await session.get(User, user_id)
    if not student:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='User not found'
        )

    if student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Este endpoint só permite editar perfil de alunos',
        )

    if student.classroom_id != current_user.classroom_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Aluno não pertence à sua turma',
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)

    await session.commit()
    await session.refresh(student)
    return student


# --------------------------------------------------------------------------- #
# PATCH /users/{user_id}/deactivate — Desativar usuário                      #
# --------------------------------------------------------------------------- #


@router.patch(
    '/{user_id}/deactivate',
    response_model=Message,
    dependencies=[Depends(PermissionChecker({SystemPermissions.USER_DELETE}))],
)
async def deactivate_user(
    session: Session,
    current_user: CurrentUser,
    user_id: int = FPath(alias='user_id'),
):
    """
    Desativa um usuário (is_active = False) sem removê-lo do sistema.

    Todos os dados do usuário — banco e disco (avatar) — são preservados
    integralmente. O usuário desativado não consegue mais autenticar, mas
    seu histórico (ocorrências, atrasos, etc.) permanece intacto para fins
    de auditoria e relatórios.

    Requer USER_DELETE (Admin ou Coordinator).
    Não é possível desativar a si mesmo por esta rota (use DELETE para
    exclusão própria).
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Não é possível desativar a si mesmo',
        )

    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='User not found'
        )

    if not target.is_active:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Usuário já está desativado',
        )

    target.is_active = False
    await session.commit()
    return {'message': 'User deactivated successfully'}


# --------------------------------------------------------------------------- #
# DELETE /users/{user_id} — Deletar usuário                                  #
# --------------------------------------------------------------------------- #


@router.delete('/{user_id}', response_model=Message)
async def delete_user(
    session: Session,
    current_user: CurrentUser,
    user_id: int = FPath(alias='user_id'),
):
    """
    Deleta o usuário permanentemente. Apenas o próprio usuário pode se deletar.

    Remove todos os dados do usuário:
    - Banco: o registro é deletado (CASCADE para ocorrências sobre o aluno,
      SET NULL para ocorrências criadas pelo usuário).
    - Disco: o arquivo de avatar (data/avatars/{user_id}.webp) é removido,
      se existir.

    Dados de auditoria ligados a ocorrências criadas pelo usuário têm
    created_by_id → NULL (SET NULL), preservando o registro histórico.
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    # Remove o avatar do disco antes de deletar do banco
    _delete_avatar_file(user_id)

    await session.delete(current_user)
    await session.commit()
    return {'message': 'User deleted'}
