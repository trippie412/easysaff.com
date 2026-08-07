from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Regexp, ValidationError,
)

from ..models.user import User
from ..services.verification import validate_national_id

PHONE_RE = r"^0[17]\d{8}$"  # Kenyan mobile sample: 0712 345 678


def phone_exists(form, field):
    if User.query.filter_by(phone=field.data).first():
        raise ValidationError("This phone number is already registered.")


def email_exists(form, field):
    if User.query.filter_by(email=field.data.lower()).first():
        raise ValidationError("This email is already registered.")


def nid_unique(form, field):
    if User.query.filter_by(national_id=field.data).first():
        raise ValidationError("This National ID is already registered.")


class RegistrationForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=80)])
    phone = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Regexp(PHONE_RE, message="Use a valid Kenyan number, e.g. 0712345678."),
            phone_exists,
        ],
    )
    email = StringField(
        "Email Address",
        validators=[DataRequired(), Email(), email_exists],
    )
    national_id = StringField(
        "National ID Number",
        validators=[DataRequired(), Length(max=20), nid_unique],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    accept_terms = BooleanField(
        "I accept the Terms & Conditions",
        validators=[DataRequired(message="You must accept the terms.")],
    )

    def validate_national_id(self, field):
        valid, error = validate_national_id(field.data)
        if not valid:
            raise ValidationError(error)


class LoginForm(FlaskForm):
    phone = StringField("Phone Number", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")