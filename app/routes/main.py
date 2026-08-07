from flask import Blueprint, abort, render_template

from ..services.products import PRODUCTS

main_bp = Blueprint("main", __name__)

STATS = [
    {"value": 250000, "suffix": "+", "label": "Happy Customers"},
    {"value": 1200000, "suffix": "+", "label": "Loans Disbursed (KES)"},
    {"value": 99.9, "suffix": "%", "label": "Uptime", "decimals": 1},
    {"value": 47, "suffix": "", "label": "Counties Served"},
]


@main_bp.route("/")
def index():
    return render_template("landing.html", products=PRODUCTS, stats=STATS)


@main_bp.route("/services")
def services():
    return render_template("services.html", products=PRODUCTS)


@main_bp.route("/services/<slug>")
def product_detail(slug):
    product = next((p for p in PRODUCTS if p["slug"] == slug), None)
    if product is None:
        abort(404)

    faqs = [
        {"q": "How long does approval take?",
         "a": "Eligibility checks run instantly. Once verified, funds are disbursed within minutes during business hours."},
        {"q": "What are the repayment options?",
         "a": "Repay via M-PESA STK Push, standing order, or in-branch depending on the product."},
        {"q": "Is my data safe?",
         "a": "All data is encrypted in transit and at rest. We never share your information with third parties."},
        {"q": "Can I repay early?",
         "a": "Yes. Early repayment is allowed with no penalty on most products."},
    ]
    return render_template("product_detail.html", product=product, faqs=faqs)