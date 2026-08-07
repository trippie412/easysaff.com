from datetime import datetime, timedelta

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms.auth import LoginForm, RegistrationForm
from ..models.user import User
from ..services.verification import send_verification_code

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone=form.phone.data.strip(),
            email=form.email.data.strip().lower(),
            national_id=form.national_id.data.strip(),
        )
        user.set_password(form.password.data)

        code = send_verification_code(phone=user.phone, email=user.email)
        user.verification_code = code
        user.verification_expires = datetime.utcnow() + timedelta(minutes=10)

        db.session.add(user)
        db.session.commit()

        session["pending_user_id"] = user.id
        flash("A 6-digit verification code was sent to your phone and email.", "info")
        return redirect(url_for("auth.verify"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify", methods=["GET", "POST"])
def verify():
    pending_id = session.get("pending_user_id")
    if not pending_id:
        return redirect(url_for("auth.register"))

    user = db.session.get(User, pending_id)
    if user is None:
        session.pop("pending_user_id", None)
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        entered = (request.form.get("code") or "").strip()
        if user.verification_code and entered == user.verification_code:
            if user.verification_expires and user.verification_expires < datetime.utcnow():
                flash("Verification code expired. Please register again.", "danger")
                return redirect(url_for("auth.register"))
            user.is_verified = True
            user.verification_code = None
            user.verification_expires = None
            db.session.commit()
            session.pop("pending_user_id", None)
            login_user(user)
            flash(f"Welcome, {user.first_name}! Your account is verified.", "success")
            return redirect(url_for("dashboard.index"))
        flash("Invalid verification code. Please try again.", "danger")

    show_code = user.verification_code if current_app.config.get("SHOW_MOCK_CODES") else None
    return render_template("auth/verify.html", user=user, show_code=show_code)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard" if current_user.is_admin else "dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(phone=form.phone.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid phone number or password.", "danger")
        elif not user.is_active:
            flash("This account has been deactivated. Contact support.", "danger")
        elif user.is_suspended:
            flash("This account is suspended. Contact support.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            next_url = request.args.get("next")
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(next_url or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    reset_phone = session.get("reset_phone")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "send_code":
            phone = (request.form.get("phone") or "").strip()
            user = User.query.filter_by(phone=phone).first()
            if user is None:
                flash("No account found with that phone number.", "danger")
            else:
                code = send_verification_code(phone=user.phone)
                user.verification_code = code
                user.verification_expires = datetime.utcnow() + timedelta(minutes=10)
                db.session.commit()
                session["reset_phone"] = user.phone
                flash("A reset code was sent to your phone.", "info")

        elif action == "reset":
            phone = reset_phone
            user = User.query.filter_by(phone=phone).first() if phone else None
            code = (request.form.get("code") or "").strip()
            new_pass = request.form.get("password") or ""
            confirm = request.form.get("confirm") or ""
            if user is None:
                session.pop("reset_phone", None)
                flash("Session expired. Please start again.", "danger")
            elif not user.verification_code or user.verification_code != code:
                flash("Invalid verification code.", "danger")
            elif len(new_pass) < 8:
                flash("Password must be at least 8 characters.", "danger")
            elif new_pass != confirm:
                flash("Passwords do not match.", "danger")
            else:
                user.set_password(new_pass)
                user.verification_code = None
                user.verification_expires = None
                db.session.commit()
                session.pop("reset_phone", None)
                flash("Password reset successful. Please log in.", "success")
                return redirect(url_for("auth.login"))

    reset_user = User.query.filter_by(phone=reset_phone).first() if reset_phone else None
    return render_template("auth/forgot_password.html", reset_user=reset_user)


@auth_bp.route("/logout")
@login_required
def logout():
    was_admin = current_user.is_admin
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin.login" if was_admin else "main.index"))