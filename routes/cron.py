from flask import Blueprint, jsonify, request
from config import Config
from services.timeutils import today_tehran, now_tehran
from services.rebooking import run_next_week_rebooking
from services.reminders import run_tomorrow_reminders
from services.sms import notify_doctor_daily_schedule
from models import Appointment, CronRun
from extensions import db
from datetime import timedelta, datetime, timezone

cron_bp = Blueprint("cron", __name__, url_prefix="/api/cron")


def _check_key():
    return request.args.get("key", "") == Config.CRON_SECRET_KEY


@cron_bp.route("/server-time")
def server_time():
    """تشخیصی — بدون کلید هم قابل مشاهده‌ست چون اطلاعات حساسی نداره.
    برای تنظیم درست ساعت Cron Job روی cPanel لازمه."""
    return jsonify({
        "server_utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "tehran_time": now_tehran().strftime("%Y-%m-%d %H:%M:%S"),
    })


@cron_bp.route("/rebook")
def cron_rebook():
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    today_str = today_tehran().strftime("%Y-%m-%d")
    report = run_next_week_rebooking(today_str)
    return jsonify({"success": True, "report": report})


@cron_bp.route("/reminders")
def cron_reminders():
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    tomorrow_str = (today_tehran() + timedelta(days=1)).strftime("%Y-%m-%d")
    report = run_tomorrow_reminders(tomorrow_str)
    return jsonify({"success": True, "report": report})


@cron_bp.route("/doctor-report")
def cron_doctor_report():
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    today_str = today_tehran().strftime("%Y-%m-%d")

    # جلوگیری از ارسال دوباره در همون روز
    already = CronRun.query.filter_by(job_name="doctor_report", run_date=today_str).first()
    if already:
        return jsonify({"success": True, "message": "قبلاً امروز ارسال شده", "skipped": True})

    tomorrow_str = (today_tehran() + timedelta(days=1)).strftime("%Y-%m-%d")
    items = Appointment.query.filter(
        Appointment.date == tomorrow_str,
        Appointment.payment_status.in_(("paid", "not")),
    ).order_by(Appointment.time).all()

    result = notify_doctor_daily_schedule(items)

    db.session.add(CronRun(job_name="doctor_report", run_date=today_str))
    db.session.commit()

    return jsonify({"success": True, "sms_result": result, "appointments_count": len(items)})