from app.core.settings import Settings

# ===========================================================================
# app/core/settings.py — branch DATABASE_URL explícita
# ===========================================================================


def test_settings_resolved_database_url_uses_explicit_database_url():
    """
    Quando DATABASE_URL está definida, RESOLVED_DATABASE_URL deve retorná-la
    diretamente (branch `if self.DATABASE_URL`).

    Cobre o statement faltante: `return self.DATABASE_URL`.
    """

    s = Settings(
        DATABASE_URL='postgresql+asyncpg://custom:url@host/mydb',
        SECRET_KEY='test-key',
    )
    assert (
        s.RESOLVED_DATABASE_URL == 'postgresql+asyncpg://custom:url@host/mydb'
    )


def test_settings_resolved_database_url_builds_from_parts():
    """
    Quando DATABASE_URL é None, RESOLVED_DATABASE_URL monta a URL
    a partir dos componentes individuais (branch else).
    """

    s = Settings(
        DATABASE_URL=None,
        DB_USER='myuser',
        DB_PASSWORD='mypass',
        DB_HOST='myhost',
        DB_PORT=5433,
        DB_NAME='mydb',
        SECRET_KEY='test-key',
    )
    assert s.RESOLVED_DATABASE_URL == (
        'postgresql+asyncpg://myuser:mypass@myhost:5433/mydb'
    )
