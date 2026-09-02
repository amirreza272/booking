from flask import Blueprint, jsonify, request
from sqlalchemy import text

from config import Config
from extensions import db
from models import Appointment, Customer, SmsLog
from services.gsheet_setup import build_year
from services.gsheet_customers import clear_all as clear_customers_sheet

setup_bp = Blueprint("setup", __name__, url_prefix="/api/setup")


def _check_key():
    key = request.args.get("key", "")
    return key == Config.SETUP_SECRET_KEY


@setup_bp.route("/gsheet")
def setup_gsheet():
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    year  = int(request.args.get("year", 1405))
    force = request.args.get("force", "0") == "1"

    try:
        report = build_year(jalali_year=year, force=force)
        return jsonify({"success": True, "report": report})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@setup_bp.route("/gsheet-test")
def gsheet_test():
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    from services.gsheet import _get_spreadsheet
    try:
        spreadsheet = _get_spreadsheet()
        titles = [ws.title for ws in spreadsheet.worksheets()]
        return jsonify({"success": True, "message": "اتصال موفق بود", "worksheets": titles})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@setup_bp.route("/migrate-db")
def migrate_db():
    """
    اجرای یک‌بارمصرف برای هماهنگ‌کردن جدول‌های موجود روی سرور با مدل‌های
    فعلی. db.create_all() فقط جدول‌های جدید رو می‌سازه و به جدول‌های
    موجود (مثل appointments) ستون جدید اضافه نمی‌کنه — این روت اون کار
    رو دستی با ALTER TABLE انجام می‌ده.

    اجرای چندباره‌ش مشکلی نداره (اگه ستون از قبل باشه، فقط توی گزارش
    خطاش نوشته می‌شه، جلوی بقیه رو نمی‌گیره).
    """
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    results = []

    try:
        db.session.execute(text(
            "ALTER TABLE appointments ADD COLUMN reminder_sent BOOLEAN DEFAULT 0"
        ))
        db.session.commit()
        results.append({"step": "add reminder_sent column", "ok": True})
    except Exception as e:
        db.session.rollback()
        results.append({"step": "add reminder_sent column", "ok": False, "detail": str(e)})

    try:
        db.create_all()
        results.append({"step": "create_all (sms_logs, customers و جدول‌های جدید احتمالی)", "ok": True})
    except Exception as e:
        results.append({"step": "create_all", "ok": False, "detail": str(e)})

    return jsonify({"success": True, "results": results})


@setup_bp.route("/gsheet-resync")
def gsheet_resync():
    """
    بعد از تغییر ساختار شیت (مثلاً وقتی ردیف‌های بافر روزانه اضافه شدن)،
    باید هم /api/setup/gsheet?force=1 بزنی (ساختار خالی جدید بسازه) و
    هم این روت رو (تا همه‌ی نوبت‌های موجود توی دیتابیس دوباره روی
    ساختار جدید نوشته بشن — چون force=1 فقط ساختار رو می‌سازه، محتوای
    قبلی از دیتابیس رو خودکار نمی‌نویسه).
    """
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    from services.gsheet import write_appointment

    items = Appointment.query.order_by(Appointment.date, Appointment.time).all()

    ok, failed = 0, 0
    errors = []
    for a in items:
        if write_appointment(a):
            ok += 1
        else:
            failed += 1
            errors.append(f"{a.date} {a.time} — {a.name}")

    return jsonify({
        "success": True,
        "total": len(items),
        "written": ok,
        "failed": failed,
        "errors": errors[:20],
    })


@setup_bp.route("/wipe-data")
def wipe_data():
    """
    ⚠️ خطرناک — برای پاک‌کردن داده‌ی تستی/فیک قبل از لانچ واقعی.
    عمداً پشت یه پارامتر جدا (confirm=YES) هم هست تا کسی به‌اشتباه با
    باز کردن لینک همه‌چیز رو پاک نکنه.

    پارامتر what: یکی از appointments / customers / sms_logs / customers_sheet / all
    - appointments, customers, sms_logs: فقط ردیف‌های جدول مربوطه توی SQLite پاک می‌شن.
    - customers_sheet: ردیف‌های داده‌ی گوگل‌شیت باشگاه مشتریان پاک می‌شن (هدر می‌مونه).
    - all: همه‌ی موارد بالا با هم.

    برای پاک‌کردن شیت *رزرو* (نه باشگاه مشتریان)، از روت /api/setup/gsheet
    با force=1 استفاده کن — اون از قبل ساختار سال رو از نو می‌سازه.

    این روت رکورد آدمین (کاربر پنل) یا تنظیمات رو دست نمی‌زنه، فقط داده.
    """
    if not _check_key():
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    if request.args.get("confirm", "") != "YES":
        return jsonify({
            "success": False,
            "message": "برای جلوگیری از پاک‌شدن اشتباهی، باید &confirm=YES هم به آدرس اضافه کنی"
        }), 400

    what = request.args.get("what", "")
    valid = {"appointments", "customers", "sms_logs", "customers_sheet"}
    targets = valid if what == "all" else {what}

    if not targets.issubset(valid):
        return jsonify({
            "success": False,
            "message": f"پارامتر what باید یکی از این‌ها باشه: {', '.join(sorted(valid))}, all"
        }), 400

    results = {}

    if "appointments" in targets:
        count = Appointment.query.delete()
        results["appointments"] = f"{count} ردیف حذف شد"

    if "customers" in targets:
        count = Customer.query.delete()
        results["customers"] = f"{count} ردیف حذف شد"

    if "sms_logs" in targets:
        count = SmsLog.query.delete()
        results["sms_logs"] = f"{count} ردیف حذف شد"

    db.session.commit()

    if "customers_sheet" in targets:
        ok = clear_customers_sheet()
        results["customers_sheet"] = "پاک شد" if ok else "خطا — به gsheet_error.log نگاه کن"

    return jsonify({"success": True, "results": results})