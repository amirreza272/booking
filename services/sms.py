import os
import requests
from datetime import datetime

from extensions import db
from models import SmsLog
from config import Config, BASE_DIR

BASE_URL      = "https://transmitor.signalads.com"
SEND_ENDPOINT = f"{BASE_URL}/api_v1/sms/send"
STATUS_ENDPOINT = f"{BASE_URL}/api_v1/sms/status/{{msg_id}}"

UNSUBSCRIBE_SUFFIX = "\nلغو 11"


def _log_error(message):
    try:
        with open(os.path.join(BASE_DIR, "sms_error.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} — {message}\n")
    except Exception:
        pass


def send_sms(numbers, message, append_unsubscribe=None):
    """
    numbers: list[str]  — شماره‌های گیرنده (فرمت 09xxxxxxxxx)
    message: str        — متن پیام (بدون پسوند لغو۱۱)
    append_unsubscribe: None => از Config.SMS_APPEND_UNSUBSCRIBE پیروی می‌کنه
                        True/False => override دستی (برای تست)

    خروجی همیشه dict — هرگز exception بیرون نمی‌ندازه.
    {
        "ok": bool,
        "status_code": int | None,
        "response": dict | str | None,
        "error": str | None,
    }
    """
    if not numbers:
        return {"ok": False, "status_code": None, "response": None, "error": "شماره‌ای ارسال نشده"}

    if append_unsubscribe is None:
        append_unsubscribe = getattr(Config, "SMS_APPEND_UNSUBSCRIBE", True)

    final_message = message + (UNSUBSCRIBE_SUFFIX if append_unsubscribe else "")

    result = {"ok": False, "status_code": None, "response": None, "error": None}

    try:
        resp = requests.post(
            SEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {Config.SMS_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "from": Config.SMS_FROM,
                "message": final_message,
                "numbers": numbers,
                "send_at": None,
            },
            timeout=15,
        )
        result["status_code"] = resp.status_code
        try:
            result["response"] = resp.json()
        except Exception:
            result["response"] = resp.text

        # هر status_code غیر از 200 رو ناموفق در نظر می‌گیریم
        result["ok"] = resp.status_code == 200

        if not result["ok"]:
            result["error"] = f"HTTP {resp.status_code}"

    except requests.exceptions.Timeout:
        result["error"] = "اتصال به SignalAds قطع شد (timeout)"
    except Exception as e:
        result["error"] = str(e)

    # ─── لاگ در دیتابیس (هرگز نباید فرآیند اصلی رو متوقف کنه) ───
    try:
        log = SmsLog(
            phone=",".join(numbers),
            text=final_message[:500],
            success=result["ok"],
            error=(result["error"] or str(result["response"]))[:200] if not result["ok"] else None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        _log_error(f"خطا در ثبت SmsLog: {e}")

    if not result["ok"]:
        _log_error(f"خطا در ارسال پیامک به {numbers}: {result['error']} — پاسخ: {result['response']}")

    return result


def check_status(msg_id):
    """بررسی وضعیت تحویل یک پیامک ارسال‌شده."""
    try:
        resp = requests.get(
            STATUS_ENDPOINT.format(msg_id=msg_id),
            headers={"Authorization": f"Bearer {Config.SMS_API_TOKEN}"},
            timeout=10,
        )
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"ok": resp.status_code == 200, "status_code": resp.status_code, "response": body}
    except Exception as e:
        _log_error(f"خطا در بررسی وضعیت پیامک {msg_id}: {e}")
        return {"ok": False, "status_code": None, "response": None, "error": str(e)}


# ─────────────────────────────────────────────────────────
# توابع اختصاصی — روی پایه‌ی send_sms ساخته می‌شوند.
# متن‌های واقعی فعلاً placeholder هستند؛ باید با کاربر نهایی بشن.
# ─────────────────────────────────────────────────────────

def notify_booking_confirmed(appointment):
    message = (
        f"کلینیک مسیر\n"
        f"نوبت شما ثبت شد.\n"
        f"تاریخ: {appointment.date} ساعت {appointment.time}\n"
        f"نوع: {'آنلاین' if appointment.session_type == 'online' else 'حضوری'}"
    )
    return send_sms([appointment.phone], message)


def notify_reminder(appointment):
    message = (
        f"کلینیک مسیر\n"
        f"یادآوری: فردا ساعت {appointment.time} نوبت مشاوره دارید."
    )
    return send_sms([appointment.phone], message)


def notify_cancelled(appointment):
    message = (
        f"کلینیک مسیر\n"
        f"نوبت شما در تاریخ {appointment.date} ساعت {appointment.time} لغو شد."
    )
    return send_sms([appointment.phone], message)


def notify_rescheduled(appointment, old_date, old_time):
    message = (
        f"کلینیک مسیر\n"
        f"نوبت شما از {old_date} ساعت {old_time} به "
        f"{appointment.date} ساعت {appointment.time} جابجا شد."
    )
    return send_sms([appointment.phone], message)


def notify_doctor_daily_schedule(appointments):
    if not appointments:
        message = "کلینیک مسیر\nفردا نوبتی ثبت نشده است."
    else:
        lines = [f"{a.time} — {a.name} ({'آنلاین' if a.session_type == 'online' else 'حضوری'})" for a in appointments]
        message = "کلینیک مسیر — برنامه‌ی فردا:\n" + "\n".join(lines)
    return send_sms([Config.DOCTOR_PHONE], message)