from __future__ import annotations

from flask import Flask, jsonify

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - development fallback before env setup
    CORS = None

from backend.config import Config
from backend.routes.admin import admin_bp
from backend.routes.auth import auth_bp
from backend.routes.datasets import datasets_bp
from backend.routes.health import health_bp
from backend.routes.indexes import index_bp
from backend.routes.search import search_bp
from backend.routes.visualization import visualization_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    if CORS is not None:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(datasets_bp, url_prefix="/api/datasets")
    app.register_blueprint(index_bp, url_prefix="/api/index")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(visualization_bp, url_prefix="/api/visualization")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "not_found", "message": "API route not found"}), 404

    @app.errorhandler(Exception)
    def unhandled_error(error):
        app.logger.exception("Unhandled API error")
        return (
            jsonify(
                {
                    "error": "internal_server_error",
                    "message": str(error),
                }
            ),
            500,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
