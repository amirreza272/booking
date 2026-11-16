from datetime import timedelta
from extensions import db
from models import Appointment
from services.sms import send_sms

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# دقیقاً هم‌قرارداد با gsheet.py / gsheet_setup.py — کلید بر اساس
# date.weekday() پایتون استاندارد (میلادی، دوشنبه=۰) محاسبه می‌شه،
# نه weekday() خودِ آبجکت jdatetime (که شنبه=۰ حساب می‌کنه).
WEEKDAY_FA = {
    0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه",
    4: "جمعه", 5: "شنبه", 6: "یکشنبه",
}


def _build_reminder_sms(appointment):
    import jdatetime
    from datetime import datetime as dt

    g_date = dt.strptime(appointment.date, "%Y-%m-%d").date()
    j_date = jdatetime.date.fromgregorian(date=g_date)

    weekday_fa = WEEKDAY_FA[g_date.weekday()]
    day_fa = str(j_date.day).translate(FA_DIGITS)
    month_name = JALALI_MONTHS[j_date.month - 1]

    return (
        f"سلام 🌱\n"
        f"یادآوری جلسه:\n"
        f"📅 {weekday_fa} {day_fa} {month_name} | ⏰ {appointment.time}\n"
        f"جهت تایید نهایی یا هماهنگی با شماره ۰۹۰۱۷۶۴۴۶۷۸ تماس بگیرید\n"
        f"مرکز روانشناسی مسیر\n"
        f"خانم دکتر سولماز دینی"
    )


def run_tomorrow_reminders(tomorrow_str):
    report = {"total": 0, "sent": 0, "failed": 0, "skipped_no_phone": 0}

    items = Appointment.query.filter(
        Appointment.date == tomorrow_str,
        Appointment.payment_status.in_(("paid", "not", "deposit")),
        Appointment.reminder_sent.is_(False),
    ).all()

    for a in items:
        report["total"] += 1

        is_valid_phone = a.phone.startswith("09") and len(a.phone) == 11 and a.phone.isdigit()
        if not is_valid_phone:
            report["skipped_no_phone"] += 1
            a.reminder_sent = True
            db.session.commit()
            continue

        message = _build_reminder_sms(a)
        result = send_sms([a.phone], message)

        # فقط در صورت موفقیت علامت می‌زنیم تا اجرای بعدی برای ناموفق‌ها دوباره تلاش کنه
        if result["ok"]:
            a.reminder_sent = True
            report["sent"] += 1
        else:
            report["failed"] += 1

        # بعد از هر پیامک commit — اگه پروسس وسط کار کشته شد، دوباره‌ارسال نشه
        db.session.commit()

    return report