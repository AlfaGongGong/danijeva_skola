from flask import Flask
import os
import logging


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    from .routes.auth import auth_bp
    from .routes.lessons import lessons_bp
    from .routes.test import test_bp
    from .routes.stats import stats_bp
    from .routes.atlas import atlas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(lessons_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(atlas_bp)

    from database import init_db
    from config import IZVJESTAJI_DIR
    os.makedirs(IZVJESTAJI_DIR, exist_ok=True)

    with app.app_context():
        try:
            init_db()
        except Exception as e:
            logging.error(f"Database initialization error: {e}")

    return app
