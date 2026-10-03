"""Configuration package.

* ``settings``  - application settings (``get_settings()``), read from the environment.
* ``database``  - SQLAlchemy engine, sessions and tenant context (``get_engine()``, ``get_db()``).

Nothing is imported here on purpose. Importing ``config`` must stay free of side effects and must not need
DATABASE_URL, secrets or a database, so that tools, tests and model modules can import ``config.database.Base`` or
``config.settings.DEFAULT_ENGINE_WEIGHTS`` without a full environment. Import from the submodules:

    from config.settings import get_settings
    from config.database import get_db, session_scope

Do not re-export the ``settings`` object here: ``config.settings`` is also the name of the submodule, and binding the
object to that name would hide the module.
"""
