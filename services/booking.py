from datetime import datetime, timedelta
from models import Appointment
from services.timeutils import now_tehran, today_tehran
from services.schedule_constants import AVAILABLE_TIMES, ONLINE_ONLY_TIMES

# وضعیت‌هایی که یک ساعت رو «اشغال‌شده» حساب می‌کنن (برای مراجع عادی نمایش داده نمی‌شن)
# blocked = مسدودشده‌ی دستی توسط ادمین (مثلاً قرار شخصی خانم دکتر)
# فقط cancel باعث آزاد شدن ساعت می‌شه
OCCUPIED_STATUSES = ("paid", "not", "blocked")

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


def is_tuesday(date_obj):
    return date_obj.weekday() == 1


def is_holiday(date_obj):
    return date_obj.strftime("%Y-%m-%d") in HOLIDAYS


def can_book_tomorrow():
    return now_tehran().hour < 20


def get_available_days(days_ahead=60):
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

    if session_type == "inperson":
        # سه‌شنبه‌ها کلاً حضوری نداریم
        if is_tuesday(date_obj):
            return []
        slots = [t for t in slots if t not in ONLINE_ONLY_TIMES]

    booked = Appointment.query.filter(
        Appointment.date == date_str,
        Appointment.payment_status.in_(OCCUPIED_STATUSES),
    ).all()

    booked_times = {a.time for a in booked}

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

    if booking_date == today + timedelta(days=1) and not can_book_tomorrow():
        return "رزرو فردا بعد از ساعت ۲۰ امکان‌پذیر نیست"

    if is_friday(booking_date):
        return "رزرو در روز جمعه امکان‌پذیر نیست"

    if is_holiday(booking_date):
        return "این روز تعطیل رسمی است"

    if time_str not in AVAILABLE_TIMES:
        return "ساعت انتخابی معتبر نیست"

    if session_type == "inperson":
        if is_tuesday(booking_date):
            return "سه‌شنبه‌ها فقط پذیرش آنلاین داریم"
        if time_str in ONLINE_ONLY_TIMES:
            return "این ساعت فقط برای جلسات آنلاین قابل رزرو است"

    conflict = Appointment.query.filter(
        Appointment.date == date_str,
        Appointment.time == time_str,
        Appointment.payment_status.in_(OCCUPIED_STATUSES),
    ).first()

    if conflict:
        return "این ساعت قبلاً رزرو شده است"

    return None


def validate_admin_booking(date_str, time_str, exclude_appointment_id=None):
    """
    اعتبارسنجی نوبت دستی/مسدودسازی/جابجایی/ویرایش توسط ادمین.
    فقط تداخل چک می‌شه. محدودیت «گذشته ممنوع» عمداً حذف شده — ادمین باید
    بتونه نوبت‌های تاریخی (که قبلاً برگزار شده ولی توی سیستم نبوده) رو
    هم برای هر تاریخی ثبت کنه.
    exclude_appointment_id: موقع ویرایش/جابجایی، خودِ نوبتِ در حال ویرایش رو
    از چک تداخل کنار می‌ذاریم — وگرنه اگه تاریخ/ساعتش عوض نشه، سیستم خودش
    رو به‌عنوان تداخل با خودش رد می‌کنه.
    """
    try:
        datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "فرمت تاریخ یا ساعت نامعتبر است (ساعت باید HH:MM باشد)"

    conflict_query = Appointment.query.filter(
        Appointment.date == date_str,
        Appointment.time == time_str,
        Appointment.payment_status.in_(OCCUPIED_STATUSES),
    )
    if exclude_appointment_id:
        conflict_query = conflict_query.filter(Appointment.id != exclude_appointment_id)

    conflict = conflict_query.first()

    if conflict:
        return "این تاریخ/ساعت قبلاً اشغال یا مسدود شده است"

    return None