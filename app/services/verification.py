"""Mock identity verification service.

VALIDATION: National ID must be 7-8 digits (sample Kenyan ID format).
The client replaces `verify_identity()` with their real identity backend —
the route contract and return shape stay the same.
"""

import re

NID_PATTERN = re.compile(r"^\d{7,8}$")
SAMPLE_VALID_IDS = {
    "10000000": {"name": "SYSTEM ADMIN", "status": "verified"},
    "29876543": {"name": "DEMO MEMBER", "status": "verified"},
}


def validate_national_id(national_id):
    """Format-level validation only. Returns (is_valid, error_message)."""
    nid = (national_id or "").strip()
    if not NID_PATTERN.match(nid):
        return False, "National ID must contain 7 to 8 digits only (sample format)."
    return True, None


def verify_identity(national_id, first_name=None, last_name=None, phone=None):
    """Mock verification — replace the body with the client's real backend."""
    valid, error = validate_national_id(national_id)
    if not valid:
        return {"verified": False, "reason": error}

    record = SAMPLE_VALID_IDS.get(national_id.strip())
    if record:
        return {
            "verified": True,
            "id_number": national_id.strip(),
            "name": record["name"],
            "status": record["status"],
            "source": "MOCK",
        }
    # Valid-format but unknown IDs pass in dev mode.
    return {
        "verified": True,
        "id_number": national_id.strip(),
        "name": None,
        "status": "format_ok",
        "source": "MOCK",
    }


def send_verification_code(phone=None, email=None):
    """Mock SMS/email OTP sender — returns the code for dev display."""
    import random

    code = f"{random.randint(100000, 999999)}"
    print(f"[MOCK OTP] phone={phone} email={email} code={code}")
    return code