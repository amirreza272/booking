from flask import Blueprint, render_template
from services.zarinpal import DEPOSIT_AMOUNT

main_bp = Blueprint("main", __name__)

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@main_bp.route("/")
def index():
    deposit_toman = f"{DEPOSIT_AMOUNT // 10:,}".replace(",", "٬").translate(_FA_DIGITS)
    return render_template("index.html", deposit_toman=deposit_toman)