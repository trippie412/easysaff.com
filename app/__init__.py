from flask import Flask

from config import config_map, Config
from .extensions import db, login_manager


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, Config))

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    # Jinja helpers
    @app.template_filter("kes")
    def kes_filter(value):
        return f"KES {int(value or 0):,}"

    from .routes.main import main_bp
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.loans import loans_bp
    from .routes.payments import payments_bp
    from .routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(loans_bp, url_prefix="/loans")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        from .seed import seed_database
        seed_database()

    return app