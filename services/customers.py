from extensions import db
from models import Customer
from services.gsheet_customers import upsert_customer


def ensure_customer_exists(phone, name):
    try:
        existing = Customer.query.filter_by(phone=phone).first()
        if existing:
            return
        customer = Customer(phone=phone, name=name)
        db.session.add(customer)
        db.session.commit()
        upsert_customer(customer)
    except Exception:
        db.session.rollback()