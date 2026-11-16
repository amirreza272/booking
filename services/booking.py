from datetime import datetime, timedelta
from models import Appointment
from services.timeutils import now_tehran, today_tehran
from services.schedule_constants import AVAILABLE_TIMES, ONLINE_ONLY_TIMES

# وضعیت‌هایی که یک ساعت رو «اشغال‌شده» حساب می‌کنن (برای مراجع عادی نمایش داده نمی‌شن)
# deposit = فقط پیش‌پرداخت از طریق سایت دریافت شده (مابقی بعداً)
# blocked = مسدودشده‌ی دستی توسط ادمین
# فقط cancel باعث آزاد شدن ساعت می‌شه
OCCUPIED_STATUSES = ("paid", "not", "deposit", "blocked")

MAX_DAYS_AHEAD = 60

HOLIDAYS = [
    "2025-03-20", "2025-03-21", "2025-03-22", "2025-03-23", "2025-03-24",
    "2025-04-01", "2025-04-20", "2025-06-21", "2025-07-07", "2025-07-17",
    "2025-07-18", "2025-09-23", "2025-10-01", "2025-10-25", "2025-10-26",
    "2025-11-03", "2025-11-12", "2025-11-14", "2025-12-12", "2025-12-22",
    "2026-01-10", "2026-03-21", "2026-03-22", "2026-03-23", "2026-03-24",
    "2026-04-01", "2026-06-10", "2026-06-11",
]


def is_friday(date_obj):
    return date_obj.weekday() == 4


def is_wednesday(date_obj):
    return date_obj.weekday() == 2


def is_holiday(date_obj):
    return date_obj.strftime("%Y-%m-%d") in HOLIDAYS


def can_book_tomorrow():
    return now_tehran().hour < 20


# ───────── «دامنه‌ی» اشغال‌کنندگی هر نوبت ─────────
# scope یکی از: "all" (هم آنلاین هم حضوری) / "online" / "inperson"
# - نوبت واقعی (paid/not/deposit) همیشه کل ساعت رو اشغال می‌کنه → "all"
# - مسدودسازی کامل: session_type="blocked" → "all"
# - مسدودسازی فقط آنلاین: session_type="blocked_online" → "online"
# - مسدودسازی فقط حضوری: session_type="blocked_inperson" → "inperson"

def slot_scope(a):
    if a.payment_status != "blocked":
        return "all"
    return {"blocked_online": "online", "blocked_inperson": "inperson"}.get(a.session_type, "all")


def scopes_overlap(s1, s2):
    return s1 == "all" or s2 == "all" or s1 == s2


def scope_for_new(payment_status, session_type):
    """دامنه‌ی یک رکورد (جدید یا در حال ویرایش) بر اساس وضعیت و نوع."""
    if payment_status == "blocked":
        return {"blocked_online": "online", "blocked_inperson": "inperson"}.get(session_type, "all")
    if session_type in ("online", "inperson"):
        return session_type
    return "all"


def find_slot_conflict(date_str, time_str, scope, exclude_appointment_id=None):
    query = Appointment.query.filter(
        Appointment.date == date_str,
        Appointment.time == time_str,
        Appointment.payment_status.in_(OCCUPIED_STATUSES),
    )
    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)

    for a in query.all():
        if scopes_overlap(slot_scope(a), scope):
            return a
    return None


def get_available_days(days_ahead=MAX_DAYS_AHEAD):
    today = today_tehran()
    result = []

    for i in range(1, days_ahead + 1):
        target = today + timedelta(days=i)
        if i == 1 and not can_book_tomorrow():
            continue
        if is_friday(target):
            continue
        if is_holiday(target):
            continue
        result.append(target.strftime("%Y-%m-%d"))

    return result


def get_free_slots(date_str, session_type):
    slots = AVAILABLE_TIMES.copy()

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return []

    today = today_tehran()
    if date_obj <= today or is_friday(date_obj) or is_holiday(date_obj):
        return []

    if session_type == "inperson":
        # چهارشنبه‌ها کلاً حضوری نداریم
        if is_wednesday(date_obj):
            return []
        slots = [t for t in slots if t not in ONLINE_ONLY_TIMES]

    scope = "inperson" if session_type == "inperson" else "online"

    booked = Appointment.query.filter(
        Appointment.date == date_str,
        Appointment.payment_status.in_(OCCUPIED_STATUSES),
    ).all()

    booked_times = {a.time for a in booked if scopes_overlap(slot_scope(a), scope)}

    return [t for t in slots if t not in booked_times]


def validate_booking(date_str, time_str, session_type):
    """اعتبارسنجی رزرو عمومی (سمت مراجع) — همه‌ی قوانین کلینیک اعمال می‌شن."""
    try:
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return "فرمت تاریخ نامعتبر است"

    today = today_tehran()

    if booking_date <= today:
        return "رزرو برای امروز یا گذشته مجاز نیست"

    if booking_date > today + timedelta(days=MAX_DAYS_AHEAD):
        return "این تاریخ خارج از بازه‌ی قابل رزرو است"

    if booking_date == today + timedelta(days=1) and not can_book_tomorrow():
        return "رزرو فردا بعد از ساعت ۲۰ امکان‌پذیر نیست"

    if is_friday(booking_date):
        return "رزرو در روز جمعه امکان‌پذیر نیست"

    if is_holiday(booking_date):
        return "این روز تعطیل رسمی است"

    if time_str not in AVAILABLE_TIMES:
        return "ساعت انتخابی معتبر نیست"

    if session_type == "inperson":
        if is_wednesday(booking_date):
            return "چهارشنبه‌ها فقط پذیرش آنلاین داریم"
        if time_str in ONLINE_ONLY_TIMES:
            return "این ساعت فقط برای جلسات آنلاین قابل رزرو است"

    scope = "inperson" if session_type == "inperson" else "online"
    if find_slot_conflict(date_str, time_str, scope):
        return "این ساعت قبلاً رزرو شده است"

    return None


def validate_admin_booking(date_str, time_str, exclude_appointment_id=None, scope="all"):
    """
    اعتبارسنجی نوبت دستی/مسدودسازی/جابجایی/ویرایش توسط ادمین.
    فقط تداخل چک می‌شه (محدودیت «گذشته ممنوع» عمداً حذف شده).
    scope: دامنه‌ی رکوردی که ثبت/ویرایش می‌شه ("all" / "online" / "inperson") —
    مثلاً مسدودسازی «فقط آنلاین» با یک مسدودسازی «فقط حضوری» در همون ساعت تداخل نداره.
    exclude_appointment_id: موقع ویرایش، خودِ نوبت رو از چک تداخل کنار می‌ذاریم.
    """
    try:
        datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "فرمت تاریخ یا ساعت نامعتبر است (ساعت باید HH:MM باشد)"

    if find_slot_conflict(date_str, time_str, scope, exclude_appointment_id):
        return "این تاریخ/ساعت قبلاً اشغال یا مسدود شده است"

    return None