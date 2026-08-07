from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.loan import LoanApplicationForm
from ..models.loan import LoanApplication
from ..models.transaction import Transaction
from ..services.eligibility import check_eligibility
from ..services.fees import fee_breakdown
from ..services.mpesa import generate_reference
from ..services.products import PRODUCTS
from ..services.verification import verify_identity

loans_bp = Blueprint("loans", __name__)


def _get_product(slug):
    return next((p for p in PRODUCTS if p["slug"] == slug), None)


@loans_bp.route("/apply")
@login_required
def apply():
    """Step 1 — choose a product."""
    return render_template("loans/apply.html", products=PRODUCTS)


@loans_bp.route("/apply/<slug>", methods=["GET", "POST"])
@login_required
def apply_product(slug):
    """Step 2 — enter details. On POST: mock verification + mock eligibility (step 3)."""
    product = _get_product(slug)
    if product is None:
        abort(404)

    form = LoanApplicationForm()
    form.product_slug.data = slug
    form.product_name.data = product["name"]

    if form.validate_on_submit():
        amount = form.amount.data

        # ---- Mock identity verification (swap with client's real backend) ----
        identity = verify_identity(
            form.national_id.data,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            phone=form.phone.data,
        )
        if not identity.get("verified"):
            flash(f"Identity verification failed: {identity.get('reason', 'Unknown error')}", "danger")
            return render_template("loans/apply_form.html", form=form, product=product)

        # ---- Mock eligibility engine (swap with client's decisioning) -------
        eligibility = check_eligibility(current_user, slug, amount)

        breakdown = None
        if eligibility.get("eligible"):
            breakdown = fee_breakdown(amount)  # centralized fee math

        session["loan_application"] = {
            "product_slug": slug,
            "product_name": product["name"],
            "phone": form.phone.data,
            "email": form.email.data,
            "national_id": form.national_id.data,
            "amount": amount,
        }

        return render_template(
            "loans/result.html",
            product=product,
            form_data=session["loan_application"],
            identity=identity,
            eligibility=eligibility,
            breakdown=breakdown,
        )

    return render_template("loans/apply_form.html", form=form, product=product)


@loans_bp.route("/apply/<slug>/proceed", methods=["POST"])
@login_required
def proceed(slug):
    """Step 3 — eligible user confirms: create application + transaction, go to STK."""
    product = _get_product(slug)
    if product is None:
        abort(404)

    data = session.get("loan_application") or {}
    if data.get("product_slug") != slug:
        flash("Application session expired. Please start again.", "warning")
        return redirect(url_for("loans.apply"))

    amount = int(data["amount"])
    try:
        breakdown = fee_breakdown(amount)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("loans.apply_product", slug=slug))

    loan = LoanApplication(
        user_id=current_user.id,
        product_slug=slug,
        product_name=product["name"],
        phone=data["phone"],
        email=data["email"],
        national_id=data["national_id"],
        amount=breakdown["receive_amount"],
        service_fee=breakdown["service_fee"],
        total_to_pay=breakdown["service_fee"],
        status="pending",
        eligibility_status="eligible",
        approved_limit=current_user.credit_limit,
        reason="Awaiting payment confirmation.",
    )
    db.session.add(loan)
    db.session.flush()

    txn = Transaction(
        user_id=current_user.id,
        kind="loan_repayment",
        description=f"{product['name']} — loan payment",
        receive_amount=breakdown["receive_amount"],
        service_fee=breakdown["service_fee"],
        total_amount=breakdown["service_fee"],
        status="pending",
        reference=generate_reference("GL"),
        phone=data["phone"],
        loan_id=loan.id,
        stk_status="pending",
    )
    db.session.add(txn)
    db.session.commit()

    session.pop("loan_application", None)
    flash("Application received. Complete the M-PESA payment to finalize.", "info")
    return redirect(url_for("payments.stk_payment", transaction_id=txn.id))