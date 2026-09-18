import jdatetime
from flask import Blueprint, render_template, abort
from models import Appointment
from services.zarinpal import get_amount
from config import Config

pay_bp = Blueprint("pay", __name__)

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
WEEKDAY_FA = {
    0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه",
    4: "جمعه", 5: "شنبه", 6: "یکشنبه",
}


@pay_bp.route("/pay/<token>")
def pay_page(token):
    appointment = Appointment.query.filter_by(payment_token=token).first()
    if not appointment:
        abort(404)

    from datetime import datetime as dt
    g_date = dt.strptime(appointment.date, "%Y-%m-%d").date()
    j_date = jdatetime.date.fromgregorian(date=g_date)
    jalali_str = f"{WEEKDAY_FA[j_date.weekday()]} {j_date.day} {JALALI_MONTHS[j_date.month - 1]} {j_date.year}"

    amount_toman = get_amount(appointment.session_type, appointment.session_format) // 10
    type_fa = "آنلاین" if appointment.session_type == "online" else "حضوری"
    format_fa = "زوجی" if appointment.session_format == "couple" else "فردی"

    return render_template(
        "pay.html",
        appointment=appointment,
        jalali_str=jalali_str,
        amount_toman=f"{amount_toman:,}".replace(",", "٬"),
        type_fa=type_fa,
        format_fa=format_fa,
        clinic_address=Config.CLINIC_ADDRESS,
        session_link=Config.SESSION_LINK,
    )