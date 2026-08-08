from datetime import datetime, timedelta
from functools import wraps
from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms.admin import AdminDepositForm, AdminLoginForm, AdminUserEditForm
from ..models.communication import Notification
from ..models.loan import LoanApplication
from ..models.transaction import Transaction
from ..models.user import User
from ..services.fees import fee_breakdown
from ..services.mpesa import generate_reference

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = AdminLoginForm()
    if form.validate_on_submit():
        identifier = form.phone.data.strip()
        user = User.query.filter(
            (User.phone == identifier) | (User.email == identifier.lower())
        ).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid credentials.", "danger")
        elif not user.is_admin:
            flash("This account does not have admin access.", "danger")
        elif user.is_suspended or not user.is_active:
            flash("This admin account is disabled.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out of the admin console.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    """
    Admin dashboard.

    Provides every variable required by admin/dashboard.html.
    All statistics are calculated from the database in real time.
    """

    # ---------------------------------------------------------
    # MEMBER STATISTICS
    # ---------------------------------------------------------

    total_members = (
        User.query
        .filter_by(is_admin=False)
        .count()
    )

    suspended_members = (
        User.query
        .filter_by(
            is_admin=False,
            is_suspended=True,
        )
        .count()
    )

    # ---------------------------------------------------------
    # LOAN STATISTICS
    # ---------------------------------------------------------

    pending_loans = (
        LoanApplication.query
        .filter_by(status="pending")
        .count()
    )

    active_loans = (
        LoanApplication.query
        .filter(
            LoanApplication.status.in_(
                ["disbursed", "repaying"]
            )
        )
        .count()
    )

    # Total amount of loans that have actually been
    # disbursed, are currently being repaid, or are paid.
    total_disbursed = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(LoanApplication.amount),
                0,
            )
        )
        .filter(
            LoanApplication.status.in_(
                ["disbursed", "repaying", "paid"]
            )
        )
        .scalar()
        or 0
    )

    # Total amount of loans that have been fully repaid.
    total_repaid = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(LoanApplication.amount),
                0,
            )
        )
        .filter(
            LoanApplication.status == "paid"
        )
        .scalar()
        or 0
    )

    # ---------------------------------------------------------
    # TRANSACTION STATISTICS
    # ---------------------------------------------------------

    total_fees = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(Transaction.service_fee),
                0,
            )
        )
        .filter(
            Transaction.status == "completed"
        )
        .scalar()
        or 0
    )

    txn_count = (
        Transaction.query
        .filter_by(status="completed")
        .count()
    )

    # ---------------------------------------------------------
    # RECENT TRANSACTIONS
    # ---------------------------------------------------------

    recent_transactions = (
        Transaction.query
        .order_by(Transaction.created_at.desc())
        .limit(6)
        .all()
    )

    # ---------------------------------------------------------
    # RECENT MEMBERS
    # ---------------------------------------------------------

    recent_members = (
        User.query
        .filter_by(is_admin=False)
        .order_by(User.created_at.desc())
        .limit(6)
        .all()
    )

    # ---------------------------------------------------------
    # WEEKLY ACTIVITY CHART
    # ---------------------------------------------------------

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=6)

    weekly_transactions = (
        Transaction.query
        .filter(
            Transaction.created_at >= datetime.combine(
                start_date,
                datetime.min.time(),
            )
        )
        .all()
    )

    # Create exactly seven days for the chart.
    chart_labels = []
    chart_values = []

    for i in range(7):
        day = start_date + timedelta(days=i)

        chart_labels.append(
            day.strftime("%a")
        )

        count = 0

        for transaction in weekly_transactions:
            if transaction.created_at:
                transaction_day = transaction.created_at.date()

                if transaction_day == day:
                    count += 1

        chart_values.append(count)

    # ---------------------------------------------------------
    # STATS OBJECT EXPECTED BY dashboard.html
    # ---------------------------------------------------------

    stats = {
        "total_members": total_members,
        "suspended_members": suspended_members,
        "pending_loans": pending_loans,
        "active_loans": active_loans,
        "total_disbursed": total_disbursed,
        "total_repaid": total_repaid,
        "total_fees": total_fees,
        "txn_count": txn_count,
    }

    # ---------------------------------------------------------
    # CHART OBJECT EXPECTED BY dashboard.html
    # ---------------------------------------------------------

    chart = SimpleNamespace(
        labels=chart_labels,
        values=chart_values,
    )

    # ---------------------------------------------------------
    # RENDER DASHBOARD
    # ---------------------------------------------------------

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        chart=chart,
        recent_transactions=recent_transactions,
        recent_members=recent_members,
    )


@admin_bp.route("/members")
@admin_required
def members():
    """
    Super-admin member management.

    Displays all normal members and supports:
    - Search by name
    - Search by phone
    - Search by email
    - Search by national ID
    - Active members
    - Suspended members
    - Pending/unverified members
    """

    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip().lower()

    # =========================================================
    # ONLY NORMAL MEMBERS
    # =========================================================

    query = User.query.filter(
        User.is_admin.is_(False)
    )

    # =========================================================
    # SEARCH
    # =========================================================

    if q:
        like = f"%{q}%"

        query = query.filter(
            (User.phone.ilike(like))
            | (User.email.ilike(like))
            | (User.first_name.ilike(like))
            | (User.last_name.ilike(like))
            | (User.national_id.ilike(like))
        )

    # =========================================================
    # STATUS FILTER
    # =========================================================

    if status == "active":

        query = query.filter(
            User.is_active.is_(True),
            User.is_suspended.is_(False),
            User.is_verified.is_(True),
        )

    elif status == "suspended":

        query = query.filter(
            User.is_suspended.is_(True)
        )

    elif status == "pending":

        query = query.filter(
            User.is_verified.is_(False)
        )

    # =========================================================
    # GET MEMBERS
    # =========================================================

    items = (
        query
        .order_by(User.created_at.desc())
        .all()
    )

    # =========================================================
    # RENDER
    # =========================================================

    return render_template(
        "admin/members.html",
        items=items,
        q=q,
        current_status=status,
    )
    
@admin_bp.route("/members/<int:user_id>")
@admin_required
def member_detail(user_id):
    """Review a member's complete account information."""

    user = db.session.get(User, user_id)

    if user is None or user.is_admin:
        abort(404)

    recent_transactions = (
        Transaction.query
        .filter_by(user_id=user.id)
        .order_by(Transaction.created_at.desc())
        .limit(10)
        .all()
    )

    recent_loans = (
        LoanApplication.query
        .filter_by(user_id=user.id)
        .order_by(LoanApplication.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/member_detail.html",
        user=user,
        recent_transactions=recent_transactions,
        recent_loans=recent_loans,
    )


@admin_bp.route("/members/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def member_edit(user_id):
    """Edit member: verify / suspend / activate / raise credit limit / reset password."""
    user = db.session.get(User, user_id)
    if user is None or user.is_admin:
        abort(404)

    form = AdminUserEditForm(obj=user)
    if form.validate_on_submit():
        user.first_name = form.first_name.data.strip()
        user.last_name = form.last_name.data.strip()
        user.phone = form.phone.data.strip()
        user.email = form.email.data.strip().lower()
        user.credit_limit = form.credit_limit.data
        user.is_verified = form.is_verified.data
        user.is_active = form.is_active.data
        user.is_suspended = form.is_suspended.data
        user.is_admin = form.is_admin.data
        if form.new_password.data:
            user.set_password(form.new_password.data)
        db.session.commit()
        flash(f"Member {user.full_name()} updated.", "success")
        return redirect(url_for("admin.members"))

    return render_template("admin/member_edit.html", form=form, user=user)


@admin_bp.route("/members/<int:user_id>/deposit", methods=["GET", "POST"])
@admin_required
def member_deposit(user_id):
    """Credit a member's wallet with tiered fee logic applied."""
    user = db.session.get(User, user_id)
    if user is None or user.is_admin:
        abort(404)

    form = AdminDepositForm()
    form.user_id.data = user.id

    breakdown = None
    if form.validate_on_submit():
        amount = form.receive_amount.data
        try:
            breakdown = fee_breakdown(amount)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "admin/member_deposit.html", form=form, user=user, breakdown=None
            )

        txn = Transaction(
            user_id=user.id,
            kind="admin_deposit",
            description=(
                f"Deposit credited by admin — receive KES {breakdown['receive_amount']:,}"
            ),
            receive_amount=breakdown["receive_amount"],
            service_fee=breakdown["service_fee"],
            total_amount=breakdown["total_amount_to_pay"],
            status="completed",
            reference=generate_reference("AD"),
            phone=user.phone,
            stk_status="success",
        )
        db.session.add(txn)
        db.session.add(
            Notification(
                user_id=user.id,
                title="Deposit Credited",
                message=f"KES {breakdown['receive_amount']:,} was credited to your wallet by admin.",
                category="success",
            )
        )
        db.session.commit()
        flash(
            f"Deposited KES {breakdown['receive_amount']:,} for {user.full_name()} "
            f"(fee KES {breakdown['service_fee']:,} / total KES {breakdown['total_amount_to_pay']:,}).",
            "success",
        )
        return redirect(url_for("admin.members"))

    return render_template("admin/member_deposit.html", form=form, user=user, breakdown=breakdown)


@admin_bp.route("/loans")
@admin_required
def loans():
    """
    Super-admin loan management.

    Displays all loan applications and allows filtering
    by their current lifecycle status.
    """

    status = (request.args.get("status") or "").strip().lower()

    query = LoanApplication.query

    # ---------------------------------------------------------
    # STATUS FILTER
    # ---------------------------------------------------------

    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
        "disbursed",
        "repaying",
        "paid",
    }

    if status in allowed_statuses:
        query = query.filter(
            LoanApplication.status == status
        )
    else:
        status = ""

    # ---------------------------------------------------------
    # FETCH LOANS
    # ---------------------------------------------------------

    loans = (
        query
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    # ---------------------------------------------------------
    # RENDER
    # ---------------------------------------------------------

    return render_template(
        "admin/loans.html",
        loans=loans,
        current_status=status,
    )

@admin_bp.route("/loans/<int:loan_id>/status", methods=["POST"])
@admin_required
def loan_status(loan_id):
    loan = db.session.get(LoanApplication, loan_id)
    if loan is None:
        abort(404)
    new_status = request.form.get("status")
    if new_status not in ("approved", "rejected", "disbursed", "repaying", "paid"):
        abort(400)
    loan.status = new_status
    loan.reason = request.form.get("reason") or loan.reason
    db.session.add(
        Notification(
            user_id=loan.user_id,
            title=f"Loan {new_status.title()}",
            message=f"Your {loan.product_name} application was marked as {new_status}.",
            category="success" if new_status in ("approved", "disbursed", "paid") else "warning",
        )
    )
    db.session.commit()
    flash(f"Loan #{loan.id} marked as {new_status}.", "success")
    return redirect(request.referrer or url_for("admin.loans"))


@admin_bp.route("/transactions")
@admin_required
def transactions():
    """
    Complete platform transaction ledger.

    Shows every transaction performed by every non-admin user,
    including deposits, admin deposits, loan repayments, bonuses,
    failed transactions and pending transactions.
    """

    query = (
        Transaction.query
        .join(User, Transaction.user_id == User.id)
        .filter(User.is_admin.is_(False))
    )

    # ---------------------------------------------------------
    # FILTERS
    # ---------------------------------------------------------

    transaction_type = (
        request.args.get("type") or ""
    ).strip().lower()

    status = (
        request.args.get("status") or ""
    ).strip().lower()

    search = (
        request.args.get("q") or ""
    ).strip()

    # Transaction type
    if transaction_type:
        query = query.filter(
            Transaction.kind == transaction_type
        )

    # Transaction status
    if status:
        query = query.filter(
            Transaction.status == status
        )

    # Search member / phone / reference
    if search:
        like = f"%{search}%"

        query = query.filter(
            (User.first_name.ilike(like))
            | (User.last_name.ilike(like))
            | (User.phone.ilike(like))
            | (User.email.ilike(like))
            | (User.national_id.ilike(like))
            | (Transaction.reference.ilike(like))
        )

    # ---------------------------------------------------------
    # FETCH COMPLETE LEDGER
    # ---------------------------------------------------------

    items = (
        query
        .order_by(Transaction.created_at.desc())
        .all()
    )

    return render_template(
        "admin/transactions.html",
        transactions=items,
        items=items,
        current_type=transaction_type,
        current_status=status,
        search_query=search,
    )