from datetime import datetime
from extensions import db


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    # اطلاعات مراجع
    name  = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20),  nullable=False)

    # زمان نوبت — date به فرمت میلادی: 2026-06-25
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(10), nullable=False)

    # online / inperson
    session_type = db.Column(db.String(20), nullable=False)

    # paid / not / cancel
    payment_status = db.Column(
        db.String(20),
        nullable=False,
        default="paid"   # هر رکوردی که ثبت می‌شود قطعاً پرداخت شده
    )

    # زرین‌پال
    authority = db.Column(db.String(120))
    ref_id    = db.Column(db.String(120))

    # توضیحات مراجع
    notes = db.Column(db.Text)

    # ─── جدید — برای جلوگیری از ارسال دوباره‌ی یادآوری ۲۴ساعته ───
    reminder_sent = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "date": self.date,
            "time": self.time,
            "session_type": self.session_type,
            "payment_status": self.payment_status,
            "notes": self.notes,
            "ref_id": self.ref_id,
            "reminder_sent": self.reminder_sent,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


# ─── جدید — باشگاه مشتریان (شماره، نام، تاریخ تولد، شهر) ───
class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)

    phone     = db.Column(db.String(20), nullable=False, unique=True)
    name      = db.Column(db.String(120), nullable=False)
    birthdate = db.Column(db.String(20))   # متن آزاد — شمسی یا میلادی، هرچی مادرت راحت‌تره
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

    phone = db.Column(db.String(60), nullable=False)   # می‌تونه چند شماره با کاما باشه
    text  = db.Column(db.String(500), nullable=False)

    success = db.Column(db.Boolean, nullable=False, default=False)
    error   = db.Column(db.String(200))

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "text": self.text,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }
