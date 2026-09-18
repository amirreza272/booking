from datetime import timedelta, datetime
from extensions import db
from models import Appointment, PendingRebooking, generate_payment_token
from services.booking import OCCUPIED_STATUSES
from services.gsheet import write_appointment
from services.sms import send_sms
from config import Config

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
WEEKDAY_FA = {
    0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه",
    4: "جمعه", 5: "شنبه", 6: "یکشنبه",
}


def _jalali_str(date_str):
    """date_str میلادی (YYYY-MM-DD) رو به شکل نمایشی شمسی تبدیل می‌کنه."""
    import jdatetime
    g_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    j_date = jdatetime.date.fromgregorian(date=g_date)
    weekday_fa = WEEKDAY_FA[g_date.weekday()]
    day_fa = str(j_date.day).translate(FA_DIGITS)
    month_name = JALALI_MONTHS[j_date.month - 1]
    year_fa = str(j_date.year).translate(FA_DIGITS)
    return f"{weekday_fa} {day_fa} {month_name} {year_fa}"


def _build_payment_sms(appointment, pay_link):
    type_fa = "آنلاین" if appointment.session_type == "online" else "حضوری"
    format_fa = "زوجی" if appointment.session_format == "couple" else "فردی"
    jalali_date = _jalali_str(appointment.date)
    return (
        f"کلینیک مسیر\n"
        f"نوبت هفته‌ی آینده‌ی شما ثبت شد ({type_fa} - {format_fa}).\n"
        f"تاریخ: {jalali_date} ساعت {appointment.time}\n"
        f"جهت تکمیل رزرو، هزینه را از لینک زیر پرداخت کنید:\n"
        f"{pay_link}"
    )


def run_next_week_rebooking(today_str):
    """
    today_str: تاریخ امروز به فرمت YYYY-MM-DD (میلادی، تهران)
    برای همه‌ی نوبت‌های امروز (paid یا not) که هنوز پردازش نشدن،
    همون ساعت هفته‌ی بعد رو با وضعیت 'not' می‌سازه و پیامک پرداخت می‌فرسته.
    """
    report = {"processed": 0, "created": 0, "conflicts": 0, "sms_sent": 0, "sms_failed": 0, "skipped_no_phone": 0}

    todays = Appointment.query.filter(
        Appointment.date == today_str,
        Appointment.payment_status.in_(("paid", "not")),
        Appointment.rebook_processed.is_(False),
    ).all()

    for a in todays:
        report["processed"] += 1
        a.rebook_processed = True  # همین الان مارک می‌کنیم که دوباره پردازش نشه

        target_date_obj = datetime.strptime(a.date, "%Y-%m-%d").date() + timedelta(days=7)
        target_date = target_date_obj.strftime("%Y-%m-%d")

        conflict = Appointment.query.filter(
            Appointment.date == target_date,
            Appointment.time == a.time,
            Appointment.payment_status.in_(OCCUPIED_STATUSES),
        ).first()

        if conflict:
            report["conflicts"] += 1
            db.session.add(PendingRebooking(
                name=a.name, phone=a.phone,
                target_date=target_date, time=a.time,
                session_type=a.session_type, session_format=a.session_format,
                source_appointment_id=a.id,
            ))
            db.session.commit()
            continue

        new_appointment = Appointment(
            name=a.name, phone=a.phone,
            date=target_date, time=a.time,
            session_type=a.session_type, session_format=a.session_format,
            payment_status="not",
            payment_token=generate_payment_token(),
        )
        db.session.add(new_appointment)
        db.session.commit()
        report["created"] += 1

        write_appointment(new_appointment)

        is_valid_phone = new_appointment.phone.startswith("09") and len(new_appointment.phone) == 11 and new_appointment.phone.isdigit()
        if is_valid_phone:
            pay_link = f"{Config.SITE_BASE_URL}/pay/{new_appointment.payment_token}"
            result = send_sms([new_appointment.phone], _build_payment_sms(new_appointment, pay_link))
            if result["ok"]:
                report["sms_sent"] += 1
            else:
                report["sms_failed"] += 1
        else:
            report["skipped_no_phone"] += 1

    db.session.commit()
    return report