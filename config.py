import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-loan-portal-2026")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///" + str(BASE_DIR / "instance" / "portal.db"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    WTF_CSRF_TIME_LIMIT = None

    # ---- Mock behaviour (development only) ------------------------------
    SHOW_MOCK_CODES = True              # display mock OTP codes on-screen
    STK_SIM_DELAY_SECONDS = 3           # mock STK Push processing time
    STK_SIM_FAIL_PHONE_SUFFIX = "5555"  # phones ending in this suffix fail

    # ---- M-PESA / Daraja SANDBOX placeholders ---------------------------
    # The client replaces these with their real Daraja credentials later.
    MPESA_ENV = "sandbox"
    MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", "sandbox-key")
    MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "sandbox-secret")
    MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY", "sandbox-passkey")
    MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE", "174379")
    MPESA_CALLBACK_URL = os.environ.get(
        "MPESA_CALLBACK_URL", "https://sandbox-callback.example.com/callback"
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}