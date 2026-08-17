import os
import traceback
from flask import Blueprint, jsonify, request, redirect, session, url_for
from extensions import db
from models import Appointment
from services.booking import validate_booking
from services.zarinpal import request_payment, verify_payment, get_amount
from services.gsheet import log_appointment
from services.customers import ensure_customer_exists
from config import BASE_DIR

payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")


def home_url(params=""):
    base = url_for("main.index", _external=False)
    return f"{base}?{params}" if params else base


@payment_bp.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "داده‌ای ارسال نشده است"}), 400

    name         = data.get("name", "").strip()
    phone        = data.get("phone", "").strip()
    date         = data.get("date", "").strip()
    time         = data.get("time", "").strip()
    session_type = data.get("session_type", "").strip()
    notes        = data.get("notes", "").strip()

    if not all([name, phone, date, time, session_type]):
        return jsonify({"success": False, "message": "تمام فیلدهای اجباری را پر کنید"}), 400

    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        return jsonify({"success": False, "message": "شماره موبایل معتبر نیست"}), 400

    error = validate_booking(date, time, session_type)
    if error:
        return jsonify({"success": False, "message": error}), 400

    session["pending_booking"] = {
        "name":         name,
        "phone":        phone,
        "date":         date,
        "time":         time,
        "session_type": session_type,
        "notes":        notes,
        "amount":       get_amount(session_type),
    }

    desc = f"رزرو جلسه مشاوره — {name} — {date} ساعت {time}"
    result = request_payment(desc, session_type)

    if not result["ok"]:
        return jsonify({"success": False, "message": result["error"]}), 502

    session["pending_booking"]["authority"] = result["authority"]

    return jsonify({"success": True, "payment_url": result["url"]})


def _log_callback_error(error_text):
    try:
        with open(os.path.join(BASE_DIR, "callback_error.log"), "a", encoding="utf-8") as f:
            f.write(error_text + "\n" + "=" * 80 + "\n")
    except Exception:
        pass


@payment_bp.route("/callback")
def callback():
    try:
        authority = request.args.get("Authority", "")
        status    = request.args.get("Status", "")

        pending = session.get("pending_booking")

        if not pending or pending.get("authority") != authority:
            return redirect(home_url("error=invalid_session"))

        amount = pending.get("amount", get_amount(pending.get("session_type", "online")))
        result = verify_payment(authority, status, amount)

        if not result["ok"]:
            session.pop("pending_booking", None)
            return redirect(home_url("error=payment_failed"))

        conflict = Appointment.query.filter(
            Appointment.date == pending["date"],
            Appointment.time == pending["time"],
            Appointment.payment_status.in_(("paid", "not")),
        ).first()

        if conflict:
            session.pop("pending_booking", None)
            return redirect(home_url("error=slot_taken"))

        appointment = Appointment(
            name=pending["name"],
            phone=pending["phone"],
            date=pending["date"],
            time=pending["time"],
            session_type=pending["session_type"],
            notes=pending.get("notes", ""),
            payment_status="paid",
            authority=authority,
            ref_id=result["ref_id"],
        )

        db.session.add(appointment)
        db.session.commit()

        log_appointment(appointment)
        ensure_customer_exists(appointment.phone, appointment.name)

        session.pop("pending_booking", None)

        ref = result["ref_id"]
        return redirect(home_url(f"success=1&ref={ref}"))

    except Exception:
        # خطای واقعی رو لاگ می‌کنیم تا خودمون بعداً بررسی کنیم،
        # ولی کاربر واقعی هرگز نباید traceback خام ببینه — می‌ره به صفحه‌ی ناموفق عادی.
        _log_callback_error(traceback.format_exc())
        session.pop("pending_booking", None)
        return redirect(home_url("error=payment_failed"))
