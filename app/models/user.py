from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_suspended = db.Column(db.Boolean, default=False)

    credit_limit = db.Column(db.Integer, default=100000)

    notify_sms = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.Boolean, default=True)

    verification_code = db.Column(db.String(10))
    verification_expires = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    loans = db.relationship("LoanApplication", backref="user", lazy="dynamic")
    transactions = db.relationship("Transaction", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    @property
    def can_access(self):
        return self.is_active and not self.is_suspended