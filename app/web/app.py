import sys
from pathlib import Path

from flask import Flask


def _res(rel: str) -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return str(Path(sys._MEIPASS) / rel)
    return str(Path(__file__).parent / rel)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=_res('templates'),
        static_folder=_res('static'),
    )
    app.secret_key = 'nm-secret-change-in-production'

    from app.web.routes import register_routes
    register_routes(app)

    @app.teardown_appcontext
    def _close_db(e=None):
        from app.db.database import close_db
        close_db()

    return app
