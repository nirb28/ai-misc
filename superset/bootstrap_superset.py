import os

from superset import db
from superset.app import create_app


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_admin_user(flask_app) -> None:
    username = os.environ.get("SUPERSET_ADMIN_USERNAME", "admin")
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin")
    firstname = os.environ.get("SUPERSET_ADMIN_FIRSTNAME", "Superset")
    lastname = os.environ.get("SUPERSET_ADMIN_LASTNAME", "Admin")
    email = os.environ.get("SUPERSET_ADMIN_EMAIL", "admin@superset.local")

    security_manager = flask_app.appbuilder.sm
    existing_user = security_manager.find_user(username=username)
    if existing_user is not None:
        return

    security_manager.add_user(
        username,
        firstname,
        lastname,
        email,
        security_manager.find_role("Admin"),
        password,
    )


def ensure_starburst_database() -> None:
    from superset.models.core import Database

    sqlalchemy_uri = os.environ.get("STARBURST_SQLALCHEMY_URI")
    if not sqlalchemy_uri:
        return

    database_name = os.environ.get("STARBURST_DATABASE_NAME", "starburst")
    expose_in_sqllab = _to_bool(os.environ.get("STARBURST_EXPOSE_IN_SQLLAB"), True)
    allow_run_async = _to_bool(os.environ.get("STARBURST_ALLOW_RUN_ASYNC"), True)

    database = db.session.query(Database).filter_by(database_name=database_name).one_or_none()
    if database is None:
        database = Database(database_name=database_name)
        db.session.add(database)

    database.set_sqlalchemy_uri(sqlalchemy_uri)
    database.expose_in_sqllab = expose_in_sqllab
    database.allow_run_async = allow_run_async
    db.session.commit()


if __name__ == "__main__":
    flask_app = create_app()
    with flask_app.app_context():
        ensure_admin_user(flask_app)
        ensure_starburst_database()
