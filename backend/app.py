from __future__ import annotations

from flask import Flask, jsonify

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - development fallback before env setup
    CORS = None

from backend.config import Config
from backend.routes.health import health_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    if CORS is not None:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    app.register_blueprint(health_bp, url_prefix="/api")

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
