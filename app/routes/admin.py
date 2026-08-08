from functools import wraps

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
    # Member statistics
    total_members = User.query.filter_by(is_admin=False).count()
    suspended_members = User.query.filter_by(
        is_admin=False,
        is_suspended=True,
    ).count()

    # Loan statistics
    pending_loans = LoanApplication.query.filter_by(
        status="pending"
    ).count()

    active_loans = LoanApplication.query.filter(
        LoanApplication.status.in_(["disbursed", "repaying"])
    ).count()

    # Financial statistics
    fee_revenue = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(Transaction.service_fee),
                0,
            )
        )
        .filter(Transaction.status == "completed")
        .scalar()
        or 0
    )

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

    # Recent members
    recent_members = (
        User.query
        .filter_by(is_admin=False)
        .order_by(User.created_at.desc())
        .limit(6)
        .all()
    )

    # Recent loans
    recent_loans = (
        LoanApplication.query
        .order_by(LoanApplication.created_at.desc())
        .limit(6)
        .all()
    )

    # Dashboard statistics expected by admin/dashboard.html
    stats = {
        "total_members": total_members,
        "suspended_members": suspended_members,
        "pending_loans": pending_loans,
        "active_loans": active_loans,
        "fee_revenue": fee_revenue,
        "total_disbursed": total_disbursed,
    }

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_members=recent_members,
        recent_loans=recent_loans,
    )


@admin_bp.route("/members")
@admin_required
def members():
    q = (request.args.get("q") or "").strip()
    query = User.query.filter_by(is_admin=False)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (User.phone.like(like))
            | (User.email.like(like))
            | (User.first_name.like(like))
            | (User.last_name.like(like))
            | (User.national_id.like(like))
        )
    items = query.order_by(User.created_at.desc()).all()
    return render_template("admin/members.html", items=items, q=q)


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
    status = (request.args.get("status") or "").strip()
    query = LoanApplication.query
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(LoanApplication.created_at.desc()).all()
    return render_template("admin/loans.html", items=items, status=status)


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
    items = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template("admin/transactions.html", items=items)