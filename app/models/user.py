from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .transaction import Transaction


class User(UserMixin, db.Model):
    __tablename__ = "users"

    # =========================================================
    # BASIC USER INFORMATION
    # =========================================================

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(
        db.String(80),
        nullable=False,
    )

    last_name = db.Column(
        db.String(80),
        nullable=False,
    )

    phone = db.Column(
        db.String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    national_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    # =========================================================
    # ACCOUNT STATUS
    # =========================================================

    is_verified = db.Column(
        db.Boolean,
        default=False,
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
    )

    is_admin = db.Column(
        db.Boolean,
        default=False,
    )

    is_suspended = db.Column(
        db.Boolean,
        default=False,
    )

    # =========================================================
    # CREDIT
    # =========================================================

    credit_limit = db.Column(
        db.Integer,
        default=100000,
    )

    # =========================================================
    # NOTIFICATION PREFERENCES
    # =========================================================

    notify_sms = db.Column(
        db.Boolean,
        default=True,
    )

    notify_email = db.Column(
        db.Boolean,
        default=True,
    )

    # =========================================================
    # VERIFICATION
    # =========================================================

    verification_code = db.Column(
        db.String(10),
    )

    verification_expires = db.Column(
        db.DateTime,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    loans = db.relationship(
        "LoanApplication",
        backref="user",
        lazy="dynamic",
    )

    transactions = db.relationship(
        "Transaction",
        backref="user",
        lazy="dynamic",
    )

    # =========================================================
    # PASSWORD MANAGEMENT
    # =========================================================

    def set_password(self, password):
        """Hash and store a user's password."""

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check a plain-text password against the stored hash."""

        return check_password_hash(
            self.password_hash,
            password,
        )

    # =========================================================
    # DISPLAY HELPERS
    # =========================================================

    def full_name(self):
        """Return the user's complete name."""

        return f"{self.first_name} {self.last_name}"

    def initials(self):
        """Return the user's initials."""

        return (
            f"{self.first_name[:1]}"
            f"{self.last_name[:1]}"
        ).upper()

    # =========================================================
    # ACCOUNT ACCESS
    # =========================================================

    @property
    def can_access(self):
        """
        Whether this account is currently allowed to access
        the application.
        """

        return (
            self.is_active
            and not self.is_suspended
        )

    # =========================================================
    # AVAILABLE WALLET BALANCE
    # =========================================================

    @property
    def available_balance(self):
        """
        Calculate the user's available wallet balance.

        Completed credits:
            - deposit
            - admin_deposit
            - admin_bonus

        Completed debits:
            - loan_repayment

        Pending or failed transactions are ignored.
        """

        completed_credits = (
            self.transactions
            .filter(
                Transaction.status == "completed",
                Transaction.kind.in_(
                    (
                        "deposit",
                        "admin_deposit",
                        "admin_bonus",
                    )
                ),
            )
            .all()
        )

        completed_debits = (
            self.transactions
            .filter(
                Transaction.status == "completed",
                Transaction.kind == "loan_repayment",
            )
            .all()
        )

        total_credits = sum(
            transaction.receive_amount or 0
            for transaction in completed_credits
        )

        total_debits = sum(
            transaction.total_amount or 0
            for transaction in completed_debits
        )

        return max(
            0,
            total_credits - total_debits,
        )