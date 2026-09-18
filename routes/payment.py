import os
import traceback
from flask import Blueprint, jsonify, request, redirect, session, url_for
from extensions import db
from models import Appointment, generate_payment_token
from services.booking import validate_booking
from services.zarinpal import request_payment, verify_payment, get_amount
from services.gsheet import log_appointment, update_status
from services.customers import ensure_customer_exists
from config import BASE_DIR, Config

payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")


def home_url(params=""):
    base = url_for("main.index", _external=False)
    return f"{base}?{params}" if params else base


def _log_callback_error(error_text):
    try:
        with open(os.path.join(BASE_DIR, "callback_error.log"), "a", encoding="utf-8") as f:
            f.write(error_text + "\n" + "=" * 80 + "\n")
    except Exception:
        pass


# ───────── رزرو معمولی (فرم سایت) ─────────

@payment_bp.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "داده‌ای ارسال نشده است"}), 400

    name           = data.get("name", "").strip()
    phone          = data.get("phone", "").strip()
    date           = data.get("date", "").strip()
    time           = data.get("time", "").strip()
    session_type   = data.get("session_type", "").strip()
    session_format = (data.get("session_format") or "individual").strip()
    notes          = data.get("notes", "").strip()

    if not all([name, phone, date, time, session_type]):
        return jsonify({"success": False, "message": "تمام فیلدهای اجباری را پر کنید"}), 400

    if session_format not in ("individual", "couple"):
        return jsonify({"success": False, "message": "نوع مراجعه (فردی/زوجی) معتبر نیست"}), 400

    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        return jsonify({"success": False, "message": "شماره موبایل معتبر نیست"}), 400

    error = validate_booking(date, time, session_type)
    if error:
        return jsonify({"success": False, "message": error}), 400

    session["pending_booking"] = {
        "name": name, "phone": phone, "date": date, "time": time,
        "session_type": session_type, "session_format": session_format, "notes": notes,
        "amount": get_amount(session_type, session_format),
    }

    format_fa = "زوجی" if session_format == "couple" else "فردی"
    desc = f"رزرو جلسه مشاوره — {name} — {date} ساعت {time} ({format_fa})"
    result = request_payment(desc, session_type, session_format)

    if not result["ok"]:
        return jsonify({"success": False, "message": result["error"]}), 502

    session["pending_booking"]["authority"] = result["authority"]
    return jsonify({"success": True, "payment_url": result["url"]})


@payment_bp.route("/callback")
def callback():
    try:
        authority = request.args.get("Authority", "")
        status    = request.args.get("Status", "")
        pending = session.get("pending_booking")

        if not pending or pending.get("authority") != authority:
            return redirect(home_url("error=invalid_session"))

        amount = pending.get("amount", get_amount(
            pending.get("session_type", "online"),
            pending.get("session_format", "individual"),
        ))
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
            name=pending["name"], phone=pending["phone"],
            date=pending["date"], time=pending["time"],
            session_type=pending["session_type"],
            session_format=pending.get("session_format", "individual"),
            notes=pending.get("notes", ""),
            payment_status="paid",
            authority=authority, ref_id=result["ref_id"],
            payment_token=generate_payment_token(),
        )

        db.session.add(appointment)
        db.session.commit()

        log_appointment(appointment)
        ensure_customer_exists(appointment.phone, appointment.name)

        session.pop("pending_booking", None)
        ref = result["ref_id"]
        return redirect(home_url(f"success=1&ref={ref}&type={appointment.session_type}"))

    except Exception:
        _log_callback_error(traceback.format_exc())
        session.pop("pending_booking", None)
        return redirect(home_url("error=payment_failed"))


# ───────── پرداخت نوبت از قبل رزروشده (لینک پیامکی) ─────────
# مستقل از session مرورگر — چون از گوشی/پیامک باز می‌شه، ممکنه
# session مرورگری که ازش پرداخت رو شروع کرده با مرورگری که Zarinpal
# ریدایرکتش می‌کنه فرق داشته باشه (اپ پیامک، تلگرام preview و ...).
# به‌جاش authority مستقیم روی خود رکورد appointment ذخیره می‌شه.

@payment_bp.route("/token/start", methods=["POST"])
def token_start():
    data = request.get_json() or {}
    token = (data.get("token") or "").strip()

    appointment = Appointment.query.filter_by(payment_token=token).first()
    if not appointment:
        return jsonify({"success": False, "message": "لینک نامعتبر است"}), 404

    if appointment.payment_status != "not":
        return jsonify({"success": False, "message": "این نوبت قبلاً پرداخت شده یا معتبر نیست"}), 400

    amount = get_amount(appointment.session_type, appointment.session_format)
    format_fa = "زوجی" if appointment.session_format == "couple" else "فردی"
    desc = f"پرداخت نوبت — {appointment.name} — {appointment.date} ساعت {appointment.time} ({format_fa})"

    cb_url = f"{Config.SITE_BASE_URL}/api/payment/token-callback?tok={token}"
    result = request_payment(desc, appointment.session_type, appointment.session_format, callback_url=cb_url)

    if not result["ok"]:
        return jsonify({"success": False, "message": result["error"]}), 502

    appointment.authority = result["authority"]
    db.session.commit()

    return jsonify({"success": True, "payment_url": result["url"]})


@payment_bp.route("/token-callback")
def token_callback():
    tok = request.args.get("tok", "")
    authority = request.args.get("Authority", "")
    status = request.args.get("Status", "")

    try:
        appointment = Appointment.query.filter_by(payment_token=tok).first()
        if not appointment:
            return redirect(home_url("error=invalid_session"))

        # اگه از قبل paid شده (مثلاً کاربر دوبار کلیک کرده)، دوباره پردازش نکن
        if appointment.payment_status != "not":
            return redirect(f"{Config.SITE_BASE_URL}/pay/{tok}")

        if appointment.authority != authority:
            return redirect(f"{Config.SITE_BASE_URL}/pay/{tok}?error=1")

        amount = get_amount(appointment.session_type, appointment.session_format)
        result = verify_payment(authority, status, amount)

        if not result["ok"]:
            return redirect(f"{Config.SITE_BASE_URL}/pay/{tok}?error=1")

        appointment.payment_status = "paid"
        appointment.ref_id = result["ref_id"]
        db.session.commit()

        update_status(appointment.date, appointment.time, "paid")
        ensure_customer_exists(appointment.phone, appointment.name)

        return redirect(f"{Config.SITE_BASE_URL}/pay/{tok}")

    except Exception:
        _log_callback_error(traceback.format_exc())
        return redirect(f"{Config.SITE_BASE_URL}/pay/{tok}?error=1")