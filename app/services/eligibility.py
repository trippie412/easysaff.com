"""Mock eligibility engine — replace with the client's scoring/decisioning backend."""

from .fees import calculate_fees


def check_eligibility(user, product_slug, amount):
    """Return dict: eligible / approved_limit / reason."""
    try:
        _, total_to_pay = calculate_fees(amount)
    except ValueError as exc:
        return {"eligible": False, "approved_limit": None, "reason": str(exc)}

    reasons = []
    if not user.can_access:
        reasons.append("Account is suspended or inactive.")
    if amount > user.credit_limit:
        reasons.append(
            f"Requested amount exceeds your approved limit of KES {user.credit_limit:,}."
        )
    if total_to_pay > user.credit_limit * 1.1:
        reasons.append("Total repayment exceeds the allowed credit exposure.")

    if not reasons:
        return {
            "eligible": True,
            "approved_limit": user.credit_limit,
            "reason": "Qualified for this facility. Continue to payment.",
        }
    return {
        "eligible": False,
        "approved_limit": user.credit_limit,
        "reason": " ".join(reasons),
    }