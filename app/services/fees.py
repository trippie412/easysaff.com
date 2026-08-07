"""Centralized tiered fee configuration — the SINGLE SOURCE OF TRUTH for all
fee math in the application. Nothing else may hardcode fee amounts.

Receive Amount (KES) -> Service Fee (KES). Ranges are inclusive.
"""

FEE_TIERS = [
    (1, 1000, 150),
    (1100, 2500, 200),
    (2600, 4000, 250),
    (4100, 6000, 300),
    (6100, 8000, 350),
    (8100, 10000, 400),
    (10100, 15000, 450),
    (15100, 20000, 500),
    (20100, 30000, 600),
    (30100, 40000, 700),
    (40100, 50000, 800),
    (50100, 75000, 900),
    (75100, 100000, 1000),
    (100100, 150000, 1200),
    (150100, 200000, 1500),
    (200100, 250000, 1800),
    (250100, 300000, 2100),
    (300100, 350000, 2400),
    (350100, 400000, 2700),
    (400100, 450000, 3000),
    (450100, 500000, 3500),
]

MIN_RECEIVE = 1
MAX_RECEIVE = 500000


def service_fee_for(receive_amount):
    """Return the service fee for the amount the user wants to RECEIVE."""
    for low, high, fee in FEE_TIERS:
        if low <= receive_amount <= high:
            return fee
    return None


def calculate_fees(receive_amount):
    """Return (service_fee, total_amount_to_pay).

    Raises ValueError when the receive amount is outside KES 1 - 500,000.
    """
    receive_amount = int(receive_amount)
    if not (MIN_RECEIVE <= receive_amount <= MAX_RECEIVE):
        raise ValueError(
            f"Receive amount must be between KES {MIN_RECEIVE:,} and KES {MAX_RECEIVE:,}."
        )
    fee = service_fee_for(receive_amount)
    if fee is None:
        raise ValueError("No fee tier matches this amount.")
    return fee, receive_amount + fee


def fee_breakdown(receive_amount):
    """Return a display-ready dict: receive / fee / total."""
    fee, total = calculate_fees(receive_amount)
    return {
        "receive_amount": receive_amount,
        "service_fee": fee,
        "total_amount_to_pay": total,
    }