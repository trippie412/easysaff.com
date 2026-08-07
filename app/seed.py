from datetime import datetime, timedelta

from .extensions import db
from .models.communication import Message, Notification
from .models.loan import LoanApplication
from .models.transaction import Transaction
from .models.user import User


def seed_database():
    """Seed default admin + demo member with sample data (idempotent)."""
    if not User.query.filter_by(phone="0700000000").first():
        admin = User(
            first_name="System", last_name="Admin",
            phone="0700000000", email="admin@loanportal.local",
            national_id="10000000",
            is_verified=True, is_active=True, is_admin=True,
            credit_limit=500000,
        )
        admin.set_password("Admin@123")
        db.session.add(admin)

    if not User.query.filter_by(phone="0712345678").first():
        demo = User(
            first_name="Demo", last_name="Member",
            phone="0712345678", email="demo@loanportal.local",
            national_id="29876543",
            is_verified=True, is_active=True,
            credit_limit=50000,
        )
        demo.set_password("Demo@123")
        db.session.add(demo)
    db.session.commit()

    # ---- Sample data for the demo member --------------------------------
    demo = User.query.filter_by(phone="0712345678").first()
    if demo and not Transaction.query.filter_by(user_id=demo.id).first():
        now = datetime.utcnow()

        loan1 = LoanApplication(
            user_id=demo.id, product_slug="m-shwari", product_name="M-Shwari",
            phone=demo.phone, email=demo.email, national_id=demo.national_id,
            amount=5000, service_fee=300, total_to_pay=5300,
            status="paid", eligibility_status="eligible",
            approved_limit=50000, reason="Qualified.",
            created_at=now - timedelta(days=75),
        )
        loan2 = LoanApplication(
            user_id=demo.id, product_slug="fuliza", product_name="Fuliza M-PESA",
            phone=demo.phone, email=demo.email, national_id=demo.national_id,
            amount=10000, service_fee=400, total_to_pay=10400,
            status="pending", eligibility_status="eligible",
            approved_limit=50000, reason="Awaiting payment confirmation.",
            created_at=now - timedelta(hours=2),
        )
        loan3 = LoanApplication(
            user_id=demo.id, product_slug="hustler-fund", product_name="Hustler Fund",
            phone=demo.phone, email=demo.email, national_id=demo.national_id,
            amount=15000, service_fee=450, total_to_pay=15450,
            status="repaying", eligibility_status="eligible",
            approved_limit=50000, reason="Repayment in progress.",
            created_at=now - timedelta(days=20),
        )
        db.session.add_all([loan1, loan2, loan3])
        db.session.flush()

        txns = [
            Transaction(user_id=demo.id, kind="loan_repayment",
                        description="M-Shwari loan repayment",
                        receive_amount=5000, service_fee=300, total_amount=5300,
                        status="completed", reference="GLSEED0001",
                        phone=demo.phone, loan_id=loan1.id,
                        stk_status="success",
                        created_at=now - timedelta(days=75)),
            Transaction(user_id=demo.id, kind="deposit",
                        description="Wallet top-up",
                        receive_amount=2000, service_fee=200, total_amount=2200,
                        status="completed", reference="GLSEED0002",
                        phone=demo.phone, stk_status="success",
                        created_at=now - timedelta(days=10)),
            Transaction(user_id=demo.id, kind="loan_repayment",
                        description="Hustler Fund repayment",
                        receive_amount=15000, service_fee=450, total_amount=15450,
                        status="pending", reference="GLSEED0003",
                        phone=demo.phone, loan_id=loan3.id,
                        stk_status="pending",
                        created_at=now - timedelta(days=20)),
        ]
        db.session.add_all(txns)

        db.session.add_all([
            Notification(user_id=demo.id, title="Welcome to GreenLend",
                         message="Your account is ready. Explore our loan products.",
                         category="success"),
            Notification(user_id=demo.id, title="Loan Approved",
                         message="Your M-Shwari loan of KES 5,000 was fully repaid.",
                         category="success"),
            Notification(user_id=demo.id, title="Payment Reminder",
                         message="You have a pending Hustler Fund repayment of KES 15,450.",
                         category="warning"),
            Message(user_id=demo.id, direction="in", subject="Welcome to GreenLend",
                    body="Hello! We're glad to have you. Reply anytime for support.",
                    is_read=False, created_at=now - timedelta(days=3)),
            Message(user_id=demo.id, direction="out", subject="Credit limit",
                    body="Hello, how can I increase my credit limit?",
                    is_read=True, created_at=now - timedelta(days=2)),
        ])
        db.session.commit()