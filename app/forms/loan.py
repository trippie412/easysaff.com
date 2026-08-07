from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, IntegerField, StringField
from wtforms.validators import DataRequired, Email, NumberRange, Regexp

from ..services.fees import MAX_RECEIVE, MIN_RECEIVE

PHONE_RE = r"^0[17]\d{8}$"
NID_RE = r"^\d{7,8}$"


class LoanApplicationForm(FlaskForm):
    product_slug = HiddenField("Product")
    product_name = HiddenField("Product Name")

    phone = StringField("Phone Number", validators=[DataRequired(), Regexp(PHONE_RE)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    national_id = StringField(
        "National ID Number",
        validators=[DataRequired(), Regexp(NID_RE, message="National ID must be 7-8 digits.")],
    )
    amount = IntegerField(
        "Amount to Receive (KES)",
        validators=[
            DataRequired(),
            NumberRange(
                min=MIN_RECEIVE, max=MAX_RECEIVE,
                message=f"Amount must be between KES {MIN_RECEIVE:,} and KES {MAX_RECEIVE:,}.",
            ),
        ],
    )
    accept_terms = BooleanField(
        "I accept the loan terms",
        validators=[DataRequired(message="You must accept the terms.")],
    )