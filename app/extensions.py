from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    from .models.user import User
    return db.session.get(User, int(user_id))