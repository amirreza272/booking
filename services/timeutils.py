from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def now_tehran():
    """datetime آگاه از تایم‌زون (timezone-aware)، همیشه بر اساس وقت تهران."""
    return datetime.now(TEHRAN_TZ)


def now_tehran_naive():
    """
    همون now_tehran ولی naive (بدون tzinfo) — چون datetime هایی که از
    strptime روی ورودی کاربر می‌سازیم naive هستن، و پایتون اجازه‌ی
    مقایسه‌ی مستقیم naive با aware رو نمی‌ده.
    """
    return now_tehran().replace(tzinfo=None)


def today_tehran():
    """تاریخ امروز (date، بدون ساعت) بر اساس وقت تهران."""
    return now_tehran().date()
