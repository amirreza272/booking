import secrets
from datetime import datetime
from extensions import db


def generate_payment_token():
    return secrets.token_urlsafe(16)


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    name  = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20),  nullable=False)

    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(10), nullable=False)

    session_type = db.Column(db.String(20), nullable=False)
    session_format = db.Column(db.String(20), nullable=False, default="individual")

    payment_status = db.Column(db.String(20), nullable=False, default="paid")

    authority = db.Column(db.String(120))
    ref_id    = db.Column(db.String(120))

    notes = db.Column(db.Text)

    reminder_sent = db.Column(db.Boolean, nullable=False, default=False)

    # ─── جدید ───────────────────────────────────────────
    # توکن امنیتی برای لینک پرداخت اختصاصی این نوبت (پیامکی)
    payment_token = db.Column(db.String(64), unique=True, index=True)

    # جلوگیری از رزرو دوباره‌ی هفته‌ی بعد اگه کرون دوبار اجرا بشه
    rebook_processed = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "date": self.date,
            "time": self.time,
            "session_type": self.session_type,
            "session_format": self.session_format,
            "payment_status": self.payment_status,
            "notes": self.notes,
            "ref_id": self.ref_id,
            "reminder_sent": self.reminder_sent,
            "payment_token": self.payment_token,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    phone     = db.Column(db.String(20), nullable=False, unique=True)
    name      = db.Column(db.String(120), nullable=False)
    birthdate = db.Column(db.String(20))
    city      = db.Column(db.String(80))
    notes     = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "birthdate": self.birthdate,
            "city": self.city,
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
        }


class SmsLog(db.Model):
    __tablename__ = "sms_logs"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(60), nullable=False)
    text  = db.Column(db.String(500), nullable=False)
    success = db.Column(db.Boolean, nullable=False, default=False)
    error   = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "text": self.text,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


# ─── جدید — نوبت‌هایی که رزرو خودکار هفته‌ی بعدشون به‌خاطر تداخل انجام نشده ───
class PendingRebooking(db.Model):
    __tablename__ = "pending_rebookings"

    id = db.Column(db.Integer, primary_key=True)

    name  = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    target_date = db.Column(db.String(20), nullable=False)   # روزی که باید توش رزرو بشه ولی پر بود
    time        = db.Column(db.String(10), nullable=False)

    session_type   = db.Column(db.String(20), nullable=False)
    session_format = db.Column(db.String(20), nullable=False, default="individual")

    source_appointment_id = db.Column(db.Integer)  # نوبت اصلی که این رزرو ازش تولید شده
    resolved = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "target_date": self.target_date,
            "time": self.time,
            "session_type": self.session_type,
            "session_format": self.session_format,
            "resolved": self.resolved,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


# ─── جدید — جلوگیری از اجرای دوباره‌ی گزارش شبانه‌ی دکتر در یک روز ───
class CronRun(db.Model):
    __tablename__ = "cron_runs"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(50), nullable=False)
    run_date = db.Column(db.String(20), nullable=False)  # YYYY-MM-DD (تهران)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("job_name", "run_date"),)