"""
Testes de proteção de rotas — verifica quais endpoints exigem autenticação
e quais permissões são necessárias para cada um.

Organização por domínio:
  1. auth/       — rotas públicas (token, logout, refresh) e protegidas (me, admin)
  2. users/      — criação, listagem, avatar (GET/PATCH), perfil, desativação, deleção
  3. delays/     — criação, listagem, aprovação, rejeição, undo
  4. occurrences/— criação, listagem, edição, deleção
  5. schedules/  — slots, overrides, horários por turma/professor

Convenção:
  - test_*_unauthenticated → espera 401 (sem token)
  - test_*_forbidden_*     → espera 403 (token válido, permissão insuficiente)
  - test_*_allowed_*       → espera qualquer coisa exceto 401/403 (rota acessível)

Rotas intencionalmente públicas (sem autenticação):
  POST /auth/token
  POST /auth/logout
  POST /auth/refresh_token
"""

from http import HTTPStatus

import pytest_asyncio

from app.shared.rbac.roles import UserRole
from tests.conftest import _make_user, make_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(user) -> dict:
    return {'Authorization': f'Bearer {make_token(user)}'}


def _no_auth() -> dict:
    return {}


def _invalid_auth() -> dict:
    return {'Authorization': 'Bearer tokeninvalido'}


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def student(session):
    return await _make_user(session, role=UserRole.STUDENT)


@pytest_asyncio.fixture
async def guardian(session):
    return await _make_user(session, role=UserRole.GUARDIAN)


@pytest_asyncio.fixture
async def teacher(session):
    return await _make_user(session, role=UserRole.TEACHER)


@pytest_asyncio.fixture
async def tutor(session):
    """Professor Diretor de Turma."""
    return await _make_user(session, role=UserRole.TEACHER, is_tutor=True)


@pytest_asyncio.fixture
async def porter(session):
    return await _make_user(session, role=UserRole.PORTER)


@pytest_asyncio.fixture
async def coordinator(session):
    return await _make_user(session, role=UserRole.COORDINATOR)


@pytest_asyncio.fixture
async def admin(session):
    return await _make_user(session, role=UserRole.ADMIN)


# ===========================================================================
# 1. AUTH — rotas públicas vs protegidas
# ===========================================================================


class TestAuthPublicRoutes:
    """POST /auth/token, /auth/logout e /auth/refresh_token são públicos."""

    def test_token_is_public(self, client):
        """POST /auth/token sem credenciais → não é 401 (é 422 por dados inválidos)."""
        resp = client.post('/auth/token', data={})
        assert resp.status_code != HTTPStatus.UNAUTHORIZED

    def test_logout_is_public(self, client):
        """POST /auth/logout sem token → não é 401."""
        resp = client.post('/auth/logout')
        assert resp.status_code != HTTPStatus.UNAUTHORIZED

    def test_refresh_token_without_cookie_is_401(self, client):
        """POST /auth/refresh_token sem cookie de refresh → 401 (sem cookie, não sem auth)."""
        resp = client.post('/auth/refresh_token')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED


class TestAuthProtectedRoutes:
    """GET /auth/me e GET /auth/me/permissions exigem autenticação."""

    def test_me_unauthenticated(self, client):
        resp = client.get('/auth/me')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_me_invalid_token(self, client):
        resp = client.get('/auth/me', headers=_invalid_auth())
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_me_allowed_for_any_authenticated(self, client, student):
        resp = client.get('/auth/me', headers=_auth(student))
        assert resp.status_code == HTTPStatus.OK

    def test_me_permissions_unauthenticated(self, client):
        resp = client.get('/auth/me/permissions')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_me_permissions_allowed_for_any_authenticated(
        self, client, teacher
    ):
        resp = client.get('/auth/me/permissions', headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.OK

    def test_admin_route_unauthenticated(self, client):
        resp = client.get('/auth/admin')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_admin_route_forbidden_for_student(self, client, student):
        resp = client.get('/auth/admin', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_admin_route_forbidden_for_teacher(self, client, teacher):
        resp = client.get('/auth/admin', headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_admin_route_forbidden_for_porter(self, client, porter):
        resp = client.get('/auth/admin', headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_admin_route_allowed_for_coordinator(self, client, coordinator):
        resp = client.get('/auth/admin', headers=_auth(coordinator))
        assert resp.status_code == HTTPStatus.OK

    def test_admin_route_allowed_for_admin(self, client, admin):
        resp = client.get('/auth/admin', headers=_auth(admin))
        assert resp.status_code == HTTPStatus.OK


# ===========================================================================
# 2. USERS — proteção por endpoint
# ===========================================================================


class TestUsersPostProtection:
    """POST /users/ — requer USER_CREATE (Admin, Coordinator)."""

    def test_create_user_unauthenticated(self, client):
        resp = client.post('/users/', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_create_user_forbidden_for_student(self, client, student):
        resp = client.post('/users/', json={}, headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_user_forbidden_for_teacher(self, client, teacher):
        resp = client.post('/users/', json={}, headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_user_forbidden_for_porter(self, client, porter):
        resp = client.post('/users/', json={}, headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_user_forbidden_for_guardian(self, client, guardian):
        resp = client.post('/users/', json={}, headers=_auth(guardian))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_user_allowed_for_coordinator(self, client, coordinator):
        """Coordinator com permissão passa pela proteção (422 = dados inválidos, não 401/403)."""
        resp = client.post('/users/', json={}, headers=_auth(coordinator))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_create_user_allowed_for_admin(self, client, admin):
        resp = client.post('/users/', json={}, headers=_auth(admin))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )


class TestUsersGetListProtection:
    """GET /users/ — requer USER_VIEW_ALL (Admin, Coordinator)."""

    def test_list_users_unauthenticated(self, client):
        resp = client.get('/users/')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_users_forbidden_for_student(self, client, student):
        resp = client.get('/users/', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_users_forbidden_for_teacher(self, client, teacher):
        resp = client.get('/users/', headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_users_forbidden_for_porter(self, client, porter):
        resp = client.get('/users/', headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_users_forbidden_for_guardian(self, client, guardian):
        resp = client.get('/users/', headers=_auth(guardian))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_users_allowed_for_coordinator(self, client, coordinator):
        resp = client.get('/users/', headers=_auth(coordinator))
        assert resp.status_code == HTTPStatus.OK

    def test_list_users_allowed_for_admin(self, client, admin):
        resp = client.get('/users/', headers=_auth(admin))
        assert resp.status_code == HTTPStatus.OK


class TestUsersGetAvatarProtection:
    """
    GET /users/{user_id}/avatar — requer autenticação (qualquer usuário logado).

    Este endpoint foi protegido porque avatares expõem dados de identidade
    (especialmente de alunos). Qualquer acesso não autenticado retorna 401.

    O checker usa AnyPermissionChecker({USER_VIEW_OWN, USER_VIEW_ALL, USER_VIEW_CHILD}).
    Como USER_VIEW_OWN é uma permissão BASE concedida a TODOS os usuários
    autenticados (_BASE_PERMISSIONS em permissions.py), na prática todos os
    usuários logados passam pela verificação.

    Resultado esperado por role:
      anônimo    → sem token → 401  ✗
      STUDENT    → USER_VIEW_OWN (base) ✓
      TEACHER    → USER_VIEW_OWN (base) ✓
      PORTER     → USER_VIEW_OWN (base) ✓
      GUARDIAN   → USER_VIEW_OWN (base) + USER_VIEW_CHILD ✓
      COORDINATOR→ USER_VIEW_OWN (base) + USER_VIEW_ALL ✓
      ADMIN      → USER_VIEW_OWN (base) + USER_VIEW_ALL ✓
    """

    def test_get_avatar_unauthenticated(self, client):
        """Sem token → 401. Endpoint não é mais público."""
        resp = client.get('/users/9999/avatar')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_get_avatar_invalid_token(self, client):
        """Token malformado → 401."""
        resp = client.get('/users/9999/avatar', headers=_invalid_auth())
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_get_avatar_allowed_for_student(self, client, student):
        """Student tem USER_VIEW_OWN (base) → passa pela proteção (404 = sem avatar)."""
        resp = client.get(
            f'/users/{student.id}/avatar', headers=_auth(student)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_get_avatar_allowed_for_teacher(self, client, teacher):
        """Teacher tem USER_VIEW_OWN (base) → passa pela proteção."""
        resp = client.get(
            f'/users/{teacher.id}/avatar', headers=_auth(teacher)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_get_avatar_allowed_for_porter(self, client, porter):
        """Porter tem USER_VIEW_OWN (base) → passa pela proteção."""
        resp = client.get(f'/users/{porter.id}/avatar', headers=_auth(porter))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_get_avatar_allowed_for_guardian(self, client, guardian):
        """Guardian tem USER_VIEW_OWN (base) + USER_VIEW_CHILD → passa pela proteção."""
        resp = client.get(
            f'/users/{guardian.id}/avatar', headers=_auth(guardian)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_get_avatar_allowed_for_coordinator(self, client, coordinator):
        """Coordinator tem USER_VIEW_OWN (base) + USER_VIEW_ALL → passa pela proteção."""
        resp = client.get(
            f'/users/{coordinator.id}/avatar', headers=_auth(coordinator)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_get_avatar_allowed_for_admin(self, client, admin):
        """Admin tem USER_VIEW_OWN (base) + USER_VIEW_ALL → passa pela proteção."""
        resp = client.get(f'/users/{admin.id}/avatar', headers=_auth(admin))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_get_avatar_nonexistent_user_returns_404_not_401(
        self, client, student
    ):
        """Usuário inexistente com token válido → 404, não 401/403."""
        resp = client.get('/users/999999/avatar', headers=_auth(student))
        assert resp.status_code == HTTPStatus.NOT_FOUND


class TestUsersPatchMeAvatarProtection:
    """PATCH /users/me/avatar — qualquer usuário autenticado (USER_EDIT é base)."""

    def test_upload_my_avatar_unauthenticated(self, client):
        resp = client.patch('/users/me/avatar')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_upload_my_avatar_allowed_for_student(self, client, student):
        """Passa pela proteção — erro esperado é 422 (sem arquivo), não 401/403."""
        resp = client.patch('/users/me/avatar', headers=_auth(student))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )


class TestUsersPatchStudentAvatarProtection:
    """PATCH /users/{id}/avatar — requer USER_EDIT_OWN_CLASSROOM (Professor DT)."""

    def test_upload_student_avatar_unauthenticated(self, client):
        resp = client.patch('/users/9999/avatar')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_upload_student_avatar_forbidden_for_student(
        self, client, student
    ):
        resp = client.patch(
            f'/users/{student.id}/avatar', headers=_auth(student)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_upload_student_avatar_forbidden_for_regular_teacher(
        self, client, teacher
    ):
        """Professor sem is_tutor não tem USER_EDIT_OWN_CLASSROOM → 403."""
        resp = client.patch(
            f'/users/{teacher.id}/avatar', headers=_auth(teacher)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_upload_student_avatar_forbidden_for_porter(self, client, porter):
        resp = client.patch(
            f'/users/{porter.id}/avatar', headers=_auth(porter)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_upload_student_avatar_allowed_for_tutor(self, client, tutor):
        """Professor DT (is_tutor=True) tem USER_EDIT_OWN_CLASSROOM → passa pela proteção."""
        resp = client.patch(f'/users/{tutor.id}/avatar', headers=_auth(tutor))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_upload_student_avatar_allowed_for_coordinator(
        self, client, coordinator
    ):
        resp = client.patch(
            f'/users/{coordinator.id}/avatar', headers=_auth(coordinator)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )


class TestUsersPatchProfileProtection:
    """PATCH /users/{id}/profile — requer USER_EDIT_OWN_CLASSROOM (Professor DT)."""

    def test_update_profile_unauthenticated(self, client):
        resp = client.patch('/users/9999/profile', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_update_profile_forbidden_for_student(self, client, student):
        resp = client.patch(
            f'/users/{student.id}/profile', json={}, headers=_auth(student)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_update_profile_forbidden_for_regular_teacher(
        self, client, teacher
    ):
        resp = client.patch(
            f'/users/{teacher.id}/profile', json={}, headers=_auth(teacher)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_update_profile_allowed_for_tutor(self, client, tutor):
        resp = client.patch(
            f'/users/{tutor.id}/profile', json={}, headers=_auth(tutor)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )


class TestUsersPatchDeactivateProtection:
    """PATCH /users/{id}/deactivate — requer USER_DELETE (Admin, Coordinator)."""

    def test_deactivate_unauthenticated(self, client):
        resp = client.patch('/users/9999/deactivate')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_deactivate_forbidden_for_student(self, client, student):
        resp = client.patch(
            f'/users/{student.id}/deactivate', headers=_auth(student)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_deactivate_forbidden_for_teacher(self, client, teacher):
        resp = client.patch(
            f'/users/{teacher.id}/deactivate', headers=_auth(teacher)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_deactivate_forbidden_for_porter(self, client, porter):
        resp = client.patch(
            f'/users/{porter.id}/deactivate', headers=_auth(porter)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_deactivate_allowed_for_coordinator(
        self, client, coordinator, student
    ):
        resp = client.patch(
            f'/users/{student.id}/deactivate', headers=_auth(coordinator)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_deactivate_allowed_for_admin(self, client, admin, student):
        resp = client.patch(
            f'/users/{student.id}/deactivate', headers=_auth(admin)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )


# ===========================================================================
# 3. DELAYS — proteção por endpoint
# ===========================================================================


class TestDelaysProtection:
    """Rotas de atrasos — todas exigem autenticação."""

    def test_create_delay_unauthenticated(self, client):
        resp = client.post('/delays/', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_create_delay_forbidden_for_student(self, client, student):
        resp = client.post('/delays/', json={}, headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_delay_forbidden_for_teacher(self, client, teacher):
        resp = client.post('/delays/', json={}, headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_delay_allowed_for_porter(self, client, porter):
        """Porter tem DELAYS_CREATE → passa pela proteção."""
        resp = client.post('/delays/', json={}, headers=_auth(porter))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_all_delays_unauthenticated(self, client):
        resp = client.get('/delays/')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_all_delays_forbidden_for_student(self, client, student):
        resp = client.get('/delays/', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_all_delays_forbidden_for_teacher(self, client, teacher):
        resp = client.get('/delays/', headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_all_delays_allowed_for_porter(self, client, porter):
        resp = client.get('/delays/', headers=_auth(porter))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_all_delays_allowed_for_coordinator(
        self, client, coordinator
    ):
        resp = client.get('/delays/', headers=_auth(coordinator))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_pending_delays_unauthenticated(self, client):
        resp = client.get('/delays/pending')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_pending_delays_forbidden_for_porter(self, client, porter):
        """Porter pode criar mas não revisar atrasos."""
        resp = client.get('/delays/pending', headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_pending_delays_allowed_for_coordinator(
        self, client, coordinator
    ):
        resp = client.get('/delays/pending', headers=_auth(coordinator))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_my_delays_unauthenticated(self, client):
        resp = client.get('/delays/me')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_my_delays_allowed_for_student(self, client, student):
        resp = client.get('/delays/me', headers=_auth(student))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_my_delays_forbidden_for_teacher(self, client, teacher):
        """Teacher não possui DELAYS_VIEW_OWN → 403."""
        resp = client.get('/delays/me', headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_approve_delay_unauthenticated(self, client):
        resp = client.patch('/delays/9999/approve')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_approve_delay_forbidden_for_student(self, client, student):
        resp = client.patch('/delays/9999/approve', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_approve_delay_forbidden_for_porter(self, client, porter):
        resp = client.patch('/delays/9999/approve', headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_approve_delay_allowed_for_coordinator(self, client, coordinator):
        resp = client.patch('/delays/9999/approve', headers=_auth(coordinator))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_reject_delay_unauthenticated(self, client):
        resp = client.patch('/delays/9999/reject', json={'reason': 'x'})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_reject_delay_forbidden_for_porter(self, client, porter):
        resp = client.patch(
            '/delays/9999/reject', json={'reason': 'x'}, headers=_auth(porter)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_undo_delay_unauthenticated(self, client):
        resp = client.patch('/delays/9999/undo')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_undo_delay_forbidden_for_student(self, client, student):
        resp = client.patch('/delays/9999/undo', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN


# ===========================================================================
# 4. OCCURRENCES — proteção por endpoint
# ===========================================================================


class TestOccurrencesProtection:
    """Rotas de ocorrências — todas exigem autenticação."""

    def test_create_occurrence_unauthenticated(self, client):
        resp = client.post('/occurrences/', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_create_occurrence_forbidden_for_student(self, client, student):
        resp = client.post('/occurrences/', json={}, headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_occurrence_forbidden_for_porter(self, client, porter):
        resp = client.post('/occurrences/', json={}, headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_occurrence_allowed_for_teacher(self, client, teacher):
        resp = client.post('/occurrences/', json={}, headers=_auth(teacher))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_all_occurrences_unauthenticated(self, client):
        resp = client.get('/occurrences/')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_all_occurrences_forbidden_for_student(self, client, student):
        resp = client.get('/occurrences/', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_all_occurrences_forbidden_for_teacher(self, client, teacher):
        """Teacher tem VIEW_OWN, não VIEW_ALL → 403 neste endpoint."""
        resp = client.get('/occurrences/', headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_all_occurrences_allowed_for_coordinator(
        self, client, coordinator
    ):
        resp = client.get('/occurrences/', headers=_auth(coordinator))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_my_occurrences_unauthenticated(self, client):
        resp = client.get('/occurrences/me')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_my_occurrences_allowed_for_student(self, client, student):
        resp = client.get('/occurrences/me', headers=_auth(student))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_my_occurrences_allowed_for_teacher(self, client, teacher):
        resp = client.get('/occurrences/me', headers=_auth(teacher))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_update_occurrence_unauthenticated(self, client):
        resp = client.put('/occurrences/9999', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_update_occurrence_forbidden_for_student(self, client, student):
        resp = client.put('/occurrences/9999', json={}, headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_delete_occurrence_unauthenticated(self, client):
        resp = client.delete('/occurrences/9999')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_delete_occurrence_forbidden_for_student(self, client, student):
        resp = client.delete('/occurrences/9999', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_delete_occurrence_forbidden_for_porter(self, client, porter):
        resp = client.delete('/occurrences/9999', headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_delete_occurrence_allowed_for_teacher(self, client, teacher):
        """Teacher tem OCCURRENCES_DELETE → passa pela proteção (404 = ocorrência não existe)."""
        resp = client.delete('/occurrences/9999', headers=_auth(teacher))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )


# ===========================================================================
# 5. SCHEDULES — proteção por endpoint
# ===========================================================================


class TestSchedulesProtection:
    """Rotas de horários — todas exigem autenticação."""

    def test_list_periods_unauthenticated(self, client):
        resp = client.get('/schedules/periods')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_periods_allowed_for_student(self, client, student):
        resp = client.get('/schedules/periods', headers=_auth(student))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_list_periods_allowed_for_teacher(self, client, teacher):
        resp = client.get('/schedules/periods', headers=_auth(teacher))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_classroom_schedule_unauthenticated(self, client):
        resp = client.get('/schedules/classroom/1')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_classroom_schedule_forbidden_for_teacher(self, client, teacher):
        """Teacher sem is_tutor não possui SCHEDULES_VIEW_ALL/OWN/CHILD → 403."""
        resp = client.get('/schedules/classroom/1', headers=_auth(teacher))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_classroom_schedule_forbidden_for_porter(self, client, porter):
        """Porter tem SCHEDULES_VIEW_ALL → passa pela proteção."""
        resp = client.get('/schedules/classroom/1', headers=_auth(porter))
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_create_slot_unauthenticated(self, client):
        resp = client.post('/schedules/slots', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_create_slot_forbidden_for_student(self, client, student):
        resp = client.post('/schedules/slots', json={}, headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_slot_forbidden_for_teacher(self, client, teacher):
        resp = client.post('/schedules/slots', json={}, headers=_auth(teacher))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_slot_forbidden_for_porter(self, client, porter):
        resp = client.post('/schedules/slots', json={}, headers=_auth(porter))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_slot_allowed_for_coordinator(self, client, coordinator):
        resp = client.post(
            '/schedules/slots', json={}, headers=_auth(coordinator)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_update_slot_unauthenticated(self, client):
        resp = client.put('/schedules/slots/1', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_update_slot_forbidden_for_student(self, client, student):
        resp = client.put(
            '/schedules/slots/1', json={}, headers=_auth(student)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_delete_slot_unauthenticated(self, client):
        resp = client.delete('/schedules/slots/1')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_delete_slot_forbidden_for_student(self, client, student):
        resp = client.delete('/schedules/slots/1', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_list_overrides_unauthenticated(self, client):
        resp = client.get('/schedules/overrides')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_create_override_unauthenticated(self, client):
        resp = client.post('/schedules/overrides', json={})
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_create_override_forbidden_for_student(self, client, student):
        resp = client.post(
            '/schedules/overrides', json={}, headers=_auth(student)
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_create_override_allowed_for_coordinator(
        self, client, coordinator
    ):
        resp = client.post(
            '/schedules/overrides', json={}, headers=_auth(coordinator)
        )
        assert resp.status_code not in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )

    def test_delete_override_unauthenticated(self, client):
        resp = client.delete('/schedules/overrides/1')
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_delete_override_forbidden_for_student(self, client, student):
        resp = client.delete('/schedules/overrides/1', headers=_auth(student))
        assert resp.status_code == HTTPStatus.FORBIDDEN
