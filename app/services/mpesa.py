import os
import secrets
import string
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from palpluss import PalPluss, PalPlussApiError

load_dotenv()


def generate_reference(prefix: str = "TXN") -> str:
    """
    Generate a unique transaction reference.

    Example:
        DP-20260807-A8K3F2
    """

    date_part = datetime.utcnow().strftime("%Y%m%d")

    chars = string.ascii_uppercase + string.digits
    random_part = "".join(
        secrets.choice(chars)
        for _ in range(6)
    )

    return f"{prefix}-{date_part}-{random_part}"


class PalPlussService:
    """
    PalPluss payment service for the loan portal.
    """

    def __init__(self):
        self.api_key = os.getenv("PALPLUSS_API_KEY")
        self.callback_url = os.getenv(
            "PALPLUSS_CALLBACK_URL"
        )

        self.timeout = float(
            os.getenv("PALPLUSS_TIMEOUT", "30")
        )

        if not self.api_key:
            raise RuntimeError(
                "PALPLUSS_API_KEY is not configured "
                "in the .env file."
            )

        self.client = PalPluss(
            api_key=self.api_key,
            timeout=self.timeout,
            auto_retry_on_rate_limit=True,
            max_retries=3,
        )

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Convert Kenyan phone numbers to 254XXXXXXXXX.
        """

        if not phone:
            raise ValueError(
                "Phone number is required."
            )

        phone = (
            str(phone)
            .strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if phone.startswith("+254"):
            phone = phone[1:]

        elif phone.startswith("07") or phone.startswith("01"):
            phone = "254" + phone[1:]

        elif phone.startswith("254"):
            pass

        else:
            raise ValueError(
                "Invalid Kenyan phone number. "
                "Use 07XXXXXXXX, 01XXXXXXXX, "
                "+254XXXXXXXXX or 254XXXXXXXXX."
            )

        if len(phone) != 12 or not phone.isdigit():
            raise ValueError(
                "Invalid Kenyan phone number."
            )

        if not (
            phone.startswith("2547")
            or phone.startswith("2541")
        ):
            raise ValueError(
                "Invalid Kenyan M-Pesa phone number."
            )

        return phone

    def stk_push(
        self,
        amount: float,
        phone: str,
        account_reference: str,
        transaction_desc: str = "Loan payment",
    ) -> Dict[str, Any]:
        """
        Initiate a real M-Pesa STK Push
        through PalPluss.
        """

        if amount <= 0:
            raise ValueError(
                "Payment amount must be greater than zero."
            )

        phone = self.normalize_phone(phone)

        account_reference = str(
            account_reference
        )[:20]

        transaction_desc = str(
            transaction_desc
        )[:100]

        try:
            return self.client.stk_push(
                amount=amount,
                phone=phone,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
                callback_url=self.callback_url,
            )

        except PalPlussApiError:
            raise

    def b2c_payout(
        self,
        amount: float,
        phone: str,
        reference: str,
        description: str = "Loan disbursement",
        idempotency_key: str | None = None,
    ) -> Dict[str, Any]:
        """
        Send money to a customer's M-Pesa number.

        This will be used for loan disbursements.
        """

        if amount <= 0:
            raise ValueError(
                "Payout amount must be greater than zero."
            )

        phone = self.normalize_phone(phone)

        if not idempotency_key:
            idempotency_key = generate_reference(
                "B2C"
            )

        return self.client.b2c_payout(
            amount=amount,
            phone=phone,
            reference=str(reference)[:40],
            description=str(description)[:100],
            idempotency_key=idempotency_key,
        )

    def get_transaction(
        self,
        transaction_id: str,
    ) -> Dict[str, Any]:
        """
        Retrieve a PalPluss transaction.
        """

        return self.client.get_transaction(
            transaction_id
        )

    def get_service_balance(
        self,
    ) -> Dict[str, Any]:
        """
        Get the PalPluss service balance.
        """

        return self.client.get_service_balance()

    def close(self):
        """
        Close the PalPluss client.
        """

        self.client.close()


# ============================================================
# GLOBAL PALPLUSS SERVICE
# ============================================================

palpluss_service = PalPlussService()


# ============================================================
# STK COMPATIBILITY FUNCTION
# ============================================================

def stk_push(txn):
    """
    Start a PalPluss STK Push for a Transaction model.

    Returns:

        (True, checkout_id)
    """

    result = palpluss_service.stk_push(
        amount=txn.total_amount,
        phone=txn.phone,
        account_reference=txn.reference,
        transaction_desc=(
            txn.description
            or "Loan payment"
        ),
    )

    checkout_id = result.get(
        "transactionId"
    )

    if not checkout_id:
        raise RuntimeError(
            "PalPluss did not return a transactionId."
        )

    txn.stk_checkout_id = checkout_id

    txn.stk_started_at = datetime.utcnow()

    txn.stk_status = "pending"

    txn.status = "pending"

    return True, checkout_id