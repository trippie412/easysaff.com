from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
    ValidationError,
)

from ..models.user import User
from ..services.verification import validate_national_id


# ============================================================
# KENYAN PHONE NUMBER VALIDATION
# ============================================================
#
# Accepted:
#   0712345678
#   0112345678
#   +254712345678
#   +254112345678
#
# Rejected:
#   0612345678
#   0212345678
#   +254612345678
#   +254212345678
#
PHONE_RE = r"^(?:0[17]\d{8}|\+254[17]\d{8})$"


# ============================================================
# PHONE UNIQUENESS
# ============================================================

def phone_exists(form, field):
    phone = field.data.strip()

    if User.query.filter_by(phone=phone).first():
        raise ValidationError(
            "This phone number is already registered."
        )


# ============================================================
# EMAIL UNIQUENESS
# ============================================================

def email_exists(form, field):
    email = field.data.strip().lower()

    if User.query.filter_by(email=email).first():
        raise ValidationError(
            "This email is already registered."
        )


# ============================================================
# NATIONAL ID UNIQUENESS
# ============================================================

def nid_unique(form, field):
    national_id = field.data.strip()

    if User.query.filter_by(national_id=national_id).first():
        raise ValidationError(
            "This National ID is already registered."
        )


# ============================================================
# REGISTRATION FORM
# ============================================================

class RegistrationForm(FlaskForm):

    first_name = StringField(
        "First Name",
        validators=[
            DataRequired(),
            Length(max=80),
        ],
    )

    last_name = StringField(
        "Last Name",
        validators=[
            DataRequired(),
            Length(max=80),
        ],
    )

    phone = StringField(
        "Phone Number",
        validators=[
            DataRequired(
                message="Phone number is required."
            ),

            Regexp(
                PHONE_RE,
                message=(
                    "Use a valid Kenyan number, e.g. "
                    "0712345678, 0112345678, "
                    "or +254712345678."
                ),
            ),

            phone_exists,
        ],
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(
                message="Email address is required."
            ),
            Email(
                message="Enter a valid email address."
            ),
            email_exists,
        ],
    )

    national_id = StringField(
        "National ID Number",
        validators=[
            DataRequired(
                message="National ID number is required."
            ),
            Length(
                max=20,
                message="National ID number is too long.",
            ),
            nid_unique,
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(
                message="Password is required."
            ),
            Length(
                min=8,
                message="Password must be at least 8 characters.",
            ),
        ],
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(
                message="Please confirm your password."
            ),
            EqualTo(
                "password",
                message="Passwords must match.",
            ),
        ],
    )

    accept_terms = BooleanField(
        "I accept the Terms & Conditions",
        validators=[
            DataRequired(
                message="You must accept the terms."
            ),
        ],
    )

    # ========================================================
    # NATIONAL ID VALIDATION
    # ========================================================

    def validate_national_id(self, field):
        valid, error = validate_national_id(
            field.data.strip()
        )

        if not valid:
            raise ValidationError(error)


# ============================================================
# LOGIN FORM
# ============================================================

class LoginForm(FlaskForm):

    phone = StringField(
        "Phone Number",
        validators=[
            DataRequired(
                message="Phone number is required."
            ),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(
                message="Password is required."
            ),
        ],
    )

    remember = BooleanField(
        "Remember Me"
    )