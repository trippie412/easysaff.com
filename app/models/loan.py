from datetime import datetime

from ..extensions import db


class LoanApplication(db.Model):
    __tablename__ = "loan_applications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    product_slug = db.Column(db.String(80), nullable=False)
    product_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    national_id = db.Column(db.String(20), nullable=False)

    # amount = what the user RECEIVES; fee + total are computed via services/fees.py
    amount = db.Column(db.Integer, nullable=False)
    service_fee = db.Column(db.Integer, nullable=False, default=0)
    total_to_pay = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(30), default="pending")  # pending/approved/rejected/disbursed/repaying/paid
    eligibility_status = db.Column(db.String(20))         # eligible / not_eligible
    approved_limit = db.Column(db.Integer)
    reason = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)