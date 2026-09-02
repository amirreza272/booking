from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, abort
from werkzeug.security import check_password_hash
from sqlalchemy import or_

from extensions import db
from models import Appointment, SmsLog, Customer
from config import Config
from services.booking import validate_admin_booking
from services.zarinpal import get_amount
from services.gsheet import write_appointment, update_status, clear_appointment_row
from services.gsheet_customers import upsert_customer, delete_customer_row
from services.customers import ensure_customer_exists
from services.customers_import import import_customers_from_excel

import traceback
import os
from config import BASE_DIR


admin_bp = Blueprint("admin", __name__, url_prefix="/masircenter")


def _check_username(username):
    if username != Config.ADMIN_USERNAME:
        abort(404)


def require_admin(view):
    @wraps(view)
    def wrapped(username, *args, **kwargs):
        _check_username(username)
        if not session.get("is_admin"):
            return redirect(url_for("admin.login", username=username))
        return view(username, *args, **kwargs)
    return wrapped


# ───────── احراز هویت ─────────

@admin_bp.route("/<username>/login", methods=["GET", "POST"])
def login(username):
    _check_username(username)

    if request.method == "GET":
        return render_template("admin_login.html", username=username)

    try:
        data = request.get_json(silent=True) or request.form
        password = (data.get("password") or "").strip()

        if not check_password_hash(Config.ADMIN_PASSWORD_HASH, password):
            return jsonify({"success": False, "message": "رمز عبور اشتباه است"}), 401

        session["is_admin"] = True
        session.permanent = True
        redirect_url = url_for("admin.dashboard", username=username)
        return jsonify({"success": True, "redirect": redirect_url})

    except Exception:
        error_text = traceback.format_exc()
        try:
            with open(os.path.join(BASE_DIR, "admin_login_error.log"), "a", encoding="utf-8") as f:
                f.write(error_text + "\n" + "=" * 80 + "\n")
        except Exception:
            pass
        return jsonify({"success": False, "message": "خطای سرور — لاگ ذخیره شد", "debug": error_text}), 500


@admin_bp.route("/<username>/logout")
@require_admin
def logout(username):
    session.pop("is_admin", None)
    return redirect(url_for("admin.login", username=username))


@admin_bp.route("/<username>/dashboard")
@require_admin
def dashboard(username):
    return render_template("admin_dashboard.html", username=username)


# ───────── تقویم (بر اساس بازه‌ی from/to — سازگار با ماه شمسی) ─────────

@admin_bp.route("/<username>/api/calendar")
@require_admin
def api_calendar(username):
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if not date_from or not date_to:
        return jsonify({"success": False, "message": "پارامترهای from و to الزامی هستند"}), 400

    items = Appointment.query.filter(
        Appointment.date >= date_from,
        Appointment.date <= date_to,
    ).all()

    days = {}
    for a in items:
        d = days.setdefault(a.date, {"paid": 0, "not": 0, "cancel": 0, "blocked": 0, "total": 0})
        d[a.payment_status] = d.get(a.payment_status, 0) + 1
        d["total"] += 1

    return jsonify(days)


@admin_bp.route("/<username>/api/appointments/<int:appointment_id>")
@require_admin
def api_get_appointment(username, appointment_id):
    a = Appointment.query.get_or_404(appointment_id)
    return jsonify(a.to_dict())


# ───────── مدیریت نوبت‌ها ─────────

@admin_bp.route("/<username>/api/appointments")
@require_admin
def api_list_appointments(username):
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()

    query = Appointment.query
    if date_from:
        query = query.filter(Appointment.date >= date_from)
    if date_to:
        query = query.filter(Appointment.date <= date_to)
    if status:
        query = query.filter(Appointment.payment_status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Appointment.name.like(like), Appointment.phone.like(like)))

    items = query.order_by(Appointment.date, Appointment.time).all()
    return jsonify([a.to_dict() for a in items])


@admin_bp.route("/<username>/api/appointments/<int:appointment_id>/cancel", methods=["POST"])
@require_admin
def api_cancel_appointment(username, appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.payment_status = "cancel"
    db.session.commit()

    update_status(appointment.date, appointment.time, "cancel")
    # TODO: پیامک لغو به مراجع — بعد از فعال‌شدن خط پیامک

    return jsonify({"success": True})


@admin_bp.route("/<username>/api/appointments/<int:appointment_id>/edit", methods=["POST"])
@require_admin
def api_edit_appointment(username, appointment_id):
    """
    ویرایش کامل و مستقیم یک نوبت — هر فیلدی (اسم، موبایل، تاریخ، ساعت،
    نوع جلسه، وضعیت پرداخت، یادداشت) قابل تغییره، چه نوبت گذشته باشه چه
    آینده. برخلاف حالت قبلی (لغو + ثبت نوبت جدید)، همین رکورد مستقیم
    آپدیت می‌شه — پس هیچ ردی از خودش (نوبت لغوشده‌ی اضافه) باقی نمی‌مونه.
    """
    appointment = Appointment.query.get_or_404(appointment_id)
    data = request.get_json() or {}

    new_date = (data.get("date") or appointment.date).strip()
    new_time = (data.get("time") or appointment.time).strip()

    # فقط اگه واقعاً تاریخ/ساعت عوض شده، چک تداخل بزن (با نادیده‌گرفتن خودش)
    if new_date != appointment.date or new_time != appointment.time:
        error = validate_admin_booking(new_date, new_time, exclude_appointment_id=appointment.id)
        if error:
            return jsonify({"success": False, "message": error}), 400

    old_date, old_time = appointment.date, appointment.time

    appointment.name = (data.get("name", appointment.name) or "").strip() or "بدون نام"
    appointment.phone = (data.get("phone", appointment.phone) or "").strip() or "-"
    appointment.date = new_date
    appointment.time = new_time
    appointment.session_type = data.get("session_type", appointment.session_type)
    appointment.payment_status = data.get("payment_status", appointment.payment_status)
    appointment.notes = data.get("notes", appointment.notes)

    db.session.commit()

    # اگه جابجا شده، خونه‌ی قبلی توی شیت رو آزاد کن (برای ساعات استاندارد)
    if old_date != new_date or old_time != new_time:
        update_status(old_date, old_time, "cancel")
    write_appointment(appointment)

    if appointment.phone and appointment.phone != "-":
        ensure_customer_exists(appointment.phone, appointment.name)

    return jsonify({"success": True, "appointment": appointment.to_dict()})


@admin_bp.route("/<username>/api/appointments/<int:appointment_id>/delete", methods=["POST"])
@require_admin
def api_delete_appointment(username, appointment_id):
    """
    حذف واقعی و کامل — از دیتابیس و گوگل‌شیت، بدون باقی‌ماندن هیچ ردی
    (نه توی لیست نوبت‌ها، نه تقویم، نه گزارش مالی). غیرقابل بازگشت.
    """
    appointment = Appointment.query.get_or_404(appointment_id)
    clear_appointment_row(appointment)
    db.session.delete(appointment)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/<username>/api/appointments/manual", methods=["POST"])
@require_admin
def api_manual_appointment(username):
    data = request.get_json() or {}
    name         = (data.get("name") or "").strip()
    phone        = (data.get("phone") or "").strip()
    date         = (data.get("date") or "").strip()
    time         = (data.get("time") or "").strip()
    session_type = (data.get("session_type") or "").strip()
    notes        = (data.get("notes") or "").strip()

    if not date or not time or not session_type:
        return jsonify({"success": False, "message": "تاریخ، ساعت و نوع جلسه الزامی‌اند"}), 400

    # ادمین می‌تونه هر تاریخ/ساعتی (غیر از گذشته) تعریف کنه — حتی خارج از ۷ ساعت استاندارد.
    error = validate_admin_booking(date, time)
    if error:
        return jsonify({"success": False, "message": error}), 400

    appointment = Appointment(
        name=(name or "بدون نام"), phone=(phone or "-"), date=date, time=time,
        session_type=session_type, payment_status="not", notes=notes,
    )
    db.session.add(appointment)
    db.session.commit()

    write_appointment(appointment)
    if phone:
        ensure_customer_exists(phone, name or "بدون نام")

    return jsonify({"success": True, "appointment_id": appointment.id})


# ───────── باشگاه مشتریان ─────────

@admin_bp.route("/<username>/api/customers")
@require_admin
def api_list_customers(username):
    q = (request.args.get("q") or "").strip()
    query = Customer.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Customer.name.like(like),
            Customer.phone.like(like),
            Customer.city.like(like),
        ))
    items = query.order_by(Customer.name).all()
    return jsonify([c.to_dict() for c in items])


@admin_bp.route("/<username>/api/customers", methods=["POST"])
@require_admin
def api_create_customer(username):
    data = request.get_json() or {}
    phone     = (data.get("phone") or "").strip()
    name      = (data.get("name") or "").strip()
    birthdate = (data.get("birthdate") or "").strip()
    city      = (data.get("city") or "").strip()

    if not phone or not name:
        return jsonify({"success": False, "message": "شماره و نام الزامی است"}), 400

    customer = Customer.query.filter_by(phone=phone).first()
    if customer:
        customer.name = name
        customer.birthdate = birthdate
        customer.city = city
    else:
        customer = Customer(phone=phone, name=name, birthdate=birthdate, city=city)
        db.session.add(customer)

    db.session.commit()
    upsert_customer(customer)

    return jsonify({"success": True, "customer": customer.to_dict()})


@admin_bp.route("/<username>/api/customers/<int:customer_id>/update", methods=["POST"])
@require_admin
def api_update_customer(username, customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    if name:
        customer.name = name
    customer.birthdate = (data.get("birthdate") or "").strip()
    customer.city = (data.get("city") or "").strip()

    db.session.commit()
    upsert_customer(customer)

    return jsonify({"success": True, "customer": customer.to_dict()})


@admin_bp.route("/<username>/api/customers/<int:customer_id>/delete", methods=["POST"])
@require_admin
def api_delete_customer(username, customer_id):
    customer = Customer.query.get_or_404(customer_id)
    delete_customer_row(customer.phone)
    db.session.delete(customer)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/<username>/api/customers/import", methods=["POST"])
@require_admin
def api_import_customers(username):
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"success": False, "message": "فایلی انتخاب نشده"}), 400

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"success": False, "message": "فقط فایل اکسل (.xlsx) قابل قبوله"}), 400

    try:
        report = import_customers_from_excel(file)
        return jsonify({"success": True, "report": report})
    except Exception as e:
        return jsonify({"success": False, "message": f"خطا در پردازش فایل: {e}"}), 500

@admin_bp.route("/<username>/api/appointments/block", methods=["POST"])
@require_admin
def api_block_slot(username):
    data = request.get_json() or {}
    date   = (data.get("date") or "").strip()
    time   = (data.get("time") or "").strip()
    reason = (data.get("reason") or "").strip()

    if not date or not time:
        return jsonify({"success": False, "message": "تاریخ و ساعت الزامی است"}), 400

    error = validate_admin_booking(date, time)
    if error:
        return jsonify({"success": False, "message": error}), 400

    appointment = Appointment(
        name="مسدود شده (ادمین)",
        phone="-",
        date=date,
        time=time,
        session_type="blocked",
        payment_status="blocked",
        notes=reason or "مسدودسازی دستی",
    )
    db.session.add(appointment)
    db.session.commit()

    write_appointment(appointment)

    return jsonify({"success": True, "appointment_id": appointment.id})


# ───────── لاگ پیامک‌ها ─────────

@admin_bp.route("/<username>/api/sms-logs")
@require_admin
def api_sms_logs(username):
    only_failed = request.args.get("failed") == "1"

    query = SmsLog.query.order_by(SmsLog.created_at.desc())
    if only_failed:
        query = query.filter(SmsLog.success.is_(False))

    items = query.limit(300).all()
    return jsonify([s.to_dict() for s in items])


# ───────── آمار و مالی (بر اساس بازه‌ی from/to — سازگار با ماه شمسی) ─────────

@admin_bp.route("/<username>/api/stats/monthly")
@require_admin
def api_monthly_stats(username):
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    label = request.args.get("label", "")

    if not date_from or not date_to:
        return jsonify({"success": False, "message": "پارامترهای from و to الزامی هستند"}), 400

    items = Appointment.query.filter(
        Appointment.date >= date_from,
        Appointment.date <= date_to,
    ).all()

    cancelled = [a for a in items if a.payment_status == "cancel"]
    blocked   = [a for a in items if a.payment_status == "blocked"]
    paid      = [a for a in items if a.payment_status == "paid"]
    unpaid    = [a for a in items if a.payment_status == "not"]

    active = paid + unpaid  # نوبت‌های واقعاً برگزارشده/برنامه‌ریزی‌شده (مسدودی‌ها جزو این‌ها نیستن)

    return jsonify({
        "success": True,
        "label": label,
        "from": date_from,
        "to": date_to,
        "total_appointments": len(items) - len(blocked),
        "cancelled": len(cancelled),
        "blocked": len(blocked),
        "online_sessions": sum(1 for a in active if a.session_type == "online"),
        "inperson_sessions": sum(1 for a in active if a.session_type == "inperson"),
        # مقادیر خام (ریال) — تقسیم بر ۱۰ برای نمایش به‌تومان توی فرانت‌اند انجام می‌شه
        "income": {
            "online": sum(get_amount("online") for a in paid if a.session_type == "online"),
            "inperson": sum(get_amount("inperson") for a in paid if a.session_type == "inperson"),
        },
        "debt": {
            "online": sum(get_amount("online") for a in unpaid if a.session_type == "online"),
            "inperson": sum(get_amount("inperson") for a in unpaid if a.session_type == "inperson"),
        },
    })


@admin_bp.route("/<username>/api/clients/debts")
@require_admin
def api_client_debts(username):
    unpaid = Appointment.query.filter_by(payment_status="not").all()
    debts = {}
    for a in unpaid:
        amount = get_amount(a.session_type)
        # اگه موبایل نداشته باشه (نوبت دستی بدون شماره)، هرکدوم جدا حساب می‌شه —
        # وگرنه چند مراجع بی‌شماره‌ی مختلف اشتباهی زیر یه ردیف جمع می‌شدن.
        key = a.phone if a.phone and a.phone != "-" else f"noph-{a.id}"
        entry = debts.setdefault(key, {
            "name": a.name, "phone": a.phone, "total_debt": 0,
            "sessions": 0, "appointment_ids": [],
        })
        entry["total_debt"] += amount
        entry["sessions"] += 1
        entry["appointment_ids"].append(a.id)

    return jsonify(list(debts.values()))


@admin_bp.route("/<username>/api/clients/settle-debt", methods=["POST"])
@require_admin
def api_settle_debt(username):
    data = request.get_json() or {}
    ids = data.get("appointment_ids") or []
    if not ids:
        return jsonify({"success": False, "message": "شناسه‌ی نوبتی ارسال نشده"}), 400

    items = Appointment.query.filter(
        Appointment.id.in_(ids),
        Appointment.payment_status == "not",
    ).all()
    if not items:
        return jsonify({"success": False, "message": "طلبی برای تسویه یافت نشد"}), 404

    for a in items:
        a.payment_status = "paid"
    db.session.commit()

    for a in items:
        update_status(a.date, a.time, "paid")

    return jsonify({"success": True, "settled_count": len(items)})