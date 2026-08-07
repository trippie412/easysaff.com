from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required
from palpluss import parse_webhook_payload, PalPlussApiError

from ..extensions import db
from ..models.transaction import Transaction
from ..services.fees import FEE_TIERS, fee_breakdown
from ..services.mpesa import generate_reference, stk_push


payments_bp = Blueprint("payments", __name__)


# ============================================================
# FEES
# ============================================================

@payments_bp.route("/fees")
@login_required
def fee_lookup():
    """
    Return the fee breakdown for the requested amount.

    Example:
        GET /payments/fees?amount=10000
    """

    try:
        amount = int(request.args.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "Invalid amount.",
        }), 400

    try:
        breakdown = fee_breakdown(amount)

        return jsonify({
            "ok": True,
            **breakdown,
        })

    except ValueError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400


# ============================================================
# STK PUSH
# ============================================================

@payments_bp.route("/<int:transaction_id>/stk")
@login_required
def stk_payment(transaction_id):
    """
    Display the STK payment page and initiate a real
    PalPluss M-Pesa STK Push when necessary.
    """

    txn = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id,
    ).first_or_404()

    # Already completed
    if txn.status == "completed":
        return render_template(
            "payments/stk.html",
            txn=txn,
        )

    # Already waiting for customer to enter PIN
    if (
        txn.status == "pending"
        and txn.stk_status == "pending"
        and txn.stk_checkout_id
    ):
        return render_template(
            "payments/stk.html",
            txn=txn,
        )

    # Start a new STK Push
    if (
        txn.status == "pending"
        and txn.stk_status in ("pending", "failed")
    ):
        try:
            success, checkout_id = stk_push(txn)

            if success:
                db.session.commit()

                flash(
                    "M-Pesa payment request sent. "
                    "Check your phone and enter your M-Pesa PIN.",
                    "info",
                )

        except PalPlussApiError as exc:
            txn.status = "failed"
            txn.stk_status = "failed"

            db.session.commit()

            flash(
                f"PalPluss payment request failed: {exc}",
                "danger",
            )

        except ValueError as exc:
            txn.status = "failed"
            txn.stk_status = "failed"

            db.session.commit()

            flash(
                str(exc),
                "danger",
            )

        except Exception as exc:
            txn.status = "failed"
            txn.stk_status = "failed"

            db.session.commit()

            flash(
                f"Unable to start M-Pesa payment: {exc}",
                "danger",
            )

    return render_template(
        "payments/stk.html",
        txn=txn,
    )


# ============================================================
# STK STATUS
# ============================================================

@payments_bp.route("/<int:transaction_id>/stk/status")
@login_required
def stk_status(transaction_id):
    """
    AJAX polling endpoint used by payments/stk.html.

    The database status is updated by the PalPluss webhook.
    """

    txn = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id,
    ).first_or_404()

    return jsonify({
        "ok": True,
        "status": txn.stk_status,
        "txn_status": txn.status,
        "reference": txn.reference,
        "total_amount": txn.total_amount,
        "receive_amount": txn.receive_amount,
        "service_fee": txn.service_fee,
        "phone": txn.phone,
        "checkout_id": txn.stk_checkout_id,
    })


# ============================================================
# STK RETRY
# ============================================================

@payments_bp.route(
    "/<int:transaction_id>/stk/retry",
    methods=["POST"],
)
@login_required
def stk_retry(transaction_id):
    """
    Retry a failed PalPluss STK Push.
    """

    txn = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id,
    ).first_or_404()

    if txn.status == "completed":
        flash(
            "This payment has already been completed.",
            "info",
        )

        return redirect(
            url_for(
                "payments.stk_payment",
                transaction_id=txn.id,
            )
        )

    if txn.stk_status != "failed":
        flash(
            "This payment is not currently available for retry.",
            "warning",
        )

        return redirect(
            url_for(
                "payments.stk_payment",
                transaction_id=txn.id,
            )
        )

    txn.status = "pending"
    txn.stk_status = "pending"
    txn.stk_checkout_id = None
    txn.stk_started_at = None

    db.session.commit()

    return redirect(
        url_for(
            "payments.stk_payment",
            transaction_id=txn.id,
        )
    )


# ============================================================
# WALLET DEPOSIT
# ============================================================

@payments_bp.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """
    Create a wallet deposit transaction.

    The amount entered by the customer is the amount they
    want to receive.

    The service fee is added automatically.
    """

    if request.method == "POST":

        try:
            amount = int(
                request.form.get("amount", 0)
            )

            breakdown = fee_breakdown(amount)

        except (TypeError, ValueError) as exc:
            flash(
                str(exc),
                "danger",
            )

            return render_template(
                "payments/deposit.html",
                tiers=FEE_TIERS,
            )

        txn = Transaction(
            user_id=current_user.id,
            kind="deposit",
            description="Wallet top-up via M-Pesa",

            receive_amount=breakdown["receive_amount"],
            service_fee=breakdown["service_fee"],
            total_amount=breakdown["total_amount_to_pay"],

            status="pending",

            reference=generate_reference("DP"),

            phone=current_user.phone,

            stk_status="pending",

            created_at=datetime.utcnow(),
        )

        db.session.add(txn)
        db.session.commit()

        return redirect(
            url_for(
                "payments.stk_payment",
                transaction_id=txn.id,
            )
        )

    return render_template(
        "payments/deposit.html",
        tiers=FEE_TIERS,
    )


# ============================================================
# PALPLUSS WEBHOOK
# ============================================================

@payments_bp.route(
    "/palpluss/webhook",
    methods=["POST"],
)
def palpluss_webhook():
    """
    Receive payment events from PalPluss.

    IMPORTANT:
    Do NOT use @login_required here.

    PalPluss calls this endpoint directly.
    """

    try:
        raw_body = request.get_data(
            as_text=True
        )

        if not raw_body:
            return jsonify({
                "ok": False,
                "error": "Empty webhook body.",
            }), 400

        payload = parse_webhook_payload(
            raw_body
        )

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": f"Invalid webhook payload: {exc}",
        }), 400

    # --------------------------------------------------------
    # Extract event information
    # --------------------------------------------------------

    event_type = payload.get(
        "event_type"
    )

    payment = payload.get(
        "transaction",
        {}
    )

    if not isinstance(payment, dict):
        return jsonify({
            "ok": False,
            "error": "Invalid transaction data.",
        }), 400

    palpluss_transaction_id = payment.get(
        "id"
    )

    if not palpluss_transaction_id:
        return jsonify({
            "ok": False,
            "error": "Missing PalPluss transaction ID.",
        }), 400

    # --------------------------------------------------------
    # Find our local transaction
    # --------------------------------------------------------

    txn = Transaction.query.filter_by(
        stk_checkout_id=palpluss_transaction_id
    ).first()

    if not txn:
        return jsonify({
            "ok": True,
            "received": True,
            "message": "Transaction not found locally.",
        }), 200

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    if event_type == "transaction.success":

        # Prevent duplicate processing
        if txn.status != "completed":

            txn.status = "completed"
            txn.stk_status = "success"
            txn.updated_at = datetime.utcnow()

            db.session.commit()

        return jsonify({
            "ok": True,
            "received": True,
            "status": "completed",
        }), 200

    # --------------------------------------------------------
    # FAILED
    # --------------------------------------------------------

    if event_type == "transaction.failed":

        txn.status = "failed"
        txn.stk_status = "failed"
        txn.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            "ok": True,
            "received": True,
            "status": "failed",
        }), 200

    # --------------------------------------------------------
    # OTHER EVENTS
    # --------------------------------------------------------

    return jsonify({
        "ok": True,
        "received": True,
        "event_type": event_type,
    }), 200