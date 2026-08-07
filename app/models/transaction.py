from datetime import datetime

from ..extensions import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)  # deposit / loan_repayment / admin_deposit
    description = db.Column(db.String(255))

    receive_amount = db.Column(db.Integer, nullable=False)
    service_fee = db.Column(db.Integer, nullable=False, default=0)
    total_amount = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(20), default="pending")  # pending/completed/failed
    reference = db.Column(db.String(60), unique=True, index=True)
    phone = db.Column(db.String(20))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_applications.id"))

    stk_checkout_id = db.Column(db.String(60))
    stk_started_at = db.Column(db.DateTime)
    stk_status = db.Column(db.String(20), default="pending")  # pending/success/failed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)