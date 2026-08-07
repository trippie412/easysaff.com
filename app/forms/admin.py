from flask_wtf import FlaskForm
from wtforms import (
    BooleanField, IntegerField, PasswordField, StringField,
)
from wtforms.validators import DataRequired, Length, NumberRange

from ..services.fees import MAX_RECEIVE, MIN_RECEIVE


class AdminLoginForm(FlaskForm):
    phone = StringField("Phone / Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")


class AdminUserEditForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=80)])
    phone = StringField("Phone", validators=[DataRequired(), Length(max=20)])
    email = StringField("Email", validators=[DataRequired(), Length(max=120)])
    credit_limit = IntegerField(
        "Credit Limit (KES)",
        validators=[DataRequired(), NumberRange(min=1000, max=10_000_000)],
    )
    is_verified = BooleanField("Verified")
    is_active = BooleanField("Active")
    is_suspended = BooleanField("Suspended")
    is_admin = BooleanField("Admin")
    new_password = PasswordField("New Password (leave blank to keep)")


class AdminDepositForm(FlaskForm):
    user_id = IntegerField("User ID", validators=[DataRequired()])
    receive_amount = IntegerField(
        "Amount User Receives (KES)",
        validators=[
            DataRequired(),
            NumberRange(
                min=MIN_RECEIVE, max=MAX_RECEIVE,
                message=f"Amount must be between KES {MIN_RECEIVE:,} and KES {MAX_RECEIVE:,}.",
            ),
        ],
    )