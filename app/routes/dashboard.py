from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models.communication import Message, Notification
from ..models.loan import LoanApplication
from ..models.transaction import Transaction

dashboard_bp = Blueprint("dashboard", __name__)

ACTIVE_STATUSES = ("approved", "disbursed", "repaying")


@dashboard_bp.route("/")
@login_required
def index():
    loans = (
        current_user.loans
        .order_by(LoanApplication.created_at.desc())
        .all()
    )
    recent_transactions = (
        current_user.transactions
        .order_by(Transaction.created_at.desc())
        .limit(6)
        .all()
    )
    recent_notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(4)
        .all()
    )
    unread_notifications = (
        Notification.query
        .filter_by(user_id=current_user.id, is_read=False)
        .count()
    )

    total_borrowed = sum(l.amount for l in loans if l.status in ACTIVE_STATUSES + ("paid",))
    outstanding = sum(l.total_to_pay for l in loans if l.status in ACTIVE_STATUSES)
    active_loans = sum(1 for l in loans if l.status in ACTIVE_STATUSES)
    completed_loans = sum(1 for l in loans if l.status == "paid")

    # Monthly spending chart (last 6 months)
    chart_labels, chart_values = [], []
    today = datetime.utcnow()
    for i in range(5, -1, -1):
        first_of_month = datetime(today.year, today.month, 1) - timedelta(days=30 * i)
        month_total = sum(
            t.total_amount
            for t in current_user.transactions
            if t.status == "completed"
            and t.created_at.year == first_of_month.year
            and t.created_at.month == first_of_month.month
        )
        chart_labels.append(first_of_month.strftime("%b"))
        chart_values.append(month_total)

    return render_template(
        "dashboard/index.html",
        loans=loans,
        recent_transactions=recent_transactions,
        recent_notifications=recent_notifications,
        unread_notifications=unread_notifications,
        total_borrowed=total_borrowed,
        outstanding=outstanding,
        active_loans=active_loans,
        completed_loans=completed_loans,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user
    if request.method == "POST":
        user.first_name = (request.form.get("first_name") or user.first_name).strip()
        user.last_name = (request.form.get("last_name") or user.last_name).strip()
        user.email = (request.form.get("email") or user.email).strip().lower()
        user.notify_sms = "notify_sms" in request.form
        user.notify_email = "notify_email" in request.form
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("dashboard.profile"))
    return render_template("dashboard/profile.html", user=user)


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_pass = request.form.get("current_password") or ""
        new_pass = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not current_user.check_password(current_pass):
            flash("Current password is incorrect.", "danger")
        elif len(new_pass) < 8:
            flash("New password must be at least 8 characters.", "danger")
        elif new_pass != confirm:
            flash("New passwords do not match.", "danger")
        else:
            current_user.set_password(new_pass)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("dashboard.settings"))
    return render_template("dashboard/settings.html")


@dashboard_bp.route("/notifications")
@login_required
def notifications():
    items = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("dashboard/notifications.html", items=items)


@dashboard_bp.route("/notifications/read-all")
@login_required
def notifications_read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("dashboard.notifications"))


@dashboard_bp.route("/messages")
@login_required
def messages():
    items = (
        Message.query
        .filter_by(user_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("dashboard/messages.html", items=items)


@dashboard_bp.route("/messages/<int:message_id>", methods=["GET", "POST"])
@login_required
def message_detail(message_id):
    msg = Message.query.filter_by(id=message_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        if body:
            db.session.add(
                Message(
                    user_id=current_user.id,
                    direction="out",
                    subject=f"Re: {msg.subject}",
                    body=body,
                )
            )
            db.session.commit()
            flash("Reply sent. Our team will get back to you.", "success")
        return redirect(url_for("dashboard.message_detail", message_id=msg.id))

    if not msg.is_read:
        msg.is_read = True
        db.session.commit()
    return render_template("dashboard/message_detail.html", msg=msg)


@dashboard_bp.route("/support", methods=["GET", "POST"])
@login_required
def support():
    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        body = (request.form.get("body") or "").strip()
        if subject and body:
            db.session.add(
                Message(user_id=current_user.id, direction="out", subject=subject, body=body)
            )
            db.session.commit()
            flash("Your message has been sent to support.", "success")
            return redirect(url_for("dashboard.support"))
        flash("Please provide both a subject and a message.", "danger")
    return render_template("dashboard/support.html")


@dashboard_bp.route("/loans")
@login_required
def loans():
    items = (
        current_user.loans
        .order_by(LoanApplication.created_at.desc())
        .all()
    )
    return render_template("dashboard/loans.html", items=items)

@dashboard_bp.app_context_processor
def inject_counts():
    """Provide unread notification/message counts to all dashboard templates."""
    if current_user.is_authenticated:
        return {
            "unread_notifications": Notification.query
            .filter_by(user_id=current_user.id, is_read=False)
            .count(),
            "unread_messages": Message.query
            .filter_by(user_id=current_user.id, direction="in", is_read=False)
            .count(),
        }
    return {}