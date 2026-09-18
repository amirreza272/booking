import requests
from config import Config

MERCHANT_ID      = "38c7a109-8115-4090-bfb1-021b481a6926"

# ─── قیمت‌گذاری (ریال) — پایه + سورشارژهای مستقل ────────
BASE_AMOUNT      = 8000000   # ۸۰۰٬۰۰۰ تومان — حضوری + فردی
ONLINE_SURCHARGE = 500000    # ۵۰٬۰۰۰ تومان اضافه برای آنلاین
COUPLE_SURCHARGE = 500000    # ۵۰٬۰۰۰ تومان اضافه برای زوجی

CALLBACK_URL     = "https://masircenter.com/booking/api/payment/callback"

# ─── سوییچ sandbox / production ────────────────────────
_API_DOMAIN   = "sandbox.zarinpal.com" if Config.ZARINPAL_SANDBOX else "api.zarinpal.com"
_START_DOMAIN = "sandbox.zarinpal.com" if Config.ZARINPAL_SANDBOX else "www.zarinpal.com"

ZARINPAL_REQUEST = f"https://{_API_DOMAIN}/pg/v4/payment/request.json"
ZARINPAL_VERIFY  = f"https://{_API_DOMAIN}/pg/v4/payment/verify.json"
ZARINPAL_START   = f"https://{_START_DOMAIN}/pg/StartPay/"


def get_amount(session_type, session_format="individual"):
    amount = BASE_AMOUNT
    if session_type == "online":
        amount += ONLINE_SURCHARGE
    if session_format == "couple":
        amount += COUPLE_SURCHARGE
    return amount


def request_payment(description, session_type, session_format="individual", callback_url=None):
    amount = get_amount(session_type, session_format)
    cb_url = callback_url or CALLBACK_URL
    try:
        resp = requests.post(ZARINPAL_REQUEST, json={
            "merchant_id":  MERCHANT_ID,
            "amount":       amount,
            "callback_url": cb_url,
            "description":  description,
        }, timeout=10)

        data = resp.json().get("data", {})
        code = data.get("code")

        if code == 100:
            authority = data["authority"]
            return {
                "ok":        True,
                "authority": authority,
                "url":       ZARINPAL_START + authority,
                "amount":    amount,
            }

        return {"ok": False, "error": f"کد خطای زرین‌پال: {code}"}

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "اتصال به زرین‌پال قطع شد"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def verify_payment(authority, status, amount):
    if status != "OK":
        return {"ok": False, "error": "پرداخت توسط کاربر لغو شد"}

    try:
        resp = requests.post(ZARINPAL_VERIFY, json={
            "merchant_id": MERCHANT_ID,
            "amount":      amount,
            "authority":   authority,
        }, timeout=10)

        data = resp.json().get("data", {})
        code = data.get("code")

        if code in (100, 101):
            return {
                "ok":     True,
                "ref_id": str(data.get("ref_id", "")),
            }

        return {"ok": False, "error": f"تأیید پرداخت ناموفق — کد: {code}"}

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "اتصال به زرین‌پال قطع شد"}
    except Exception as e:
        return {"ok": False, "error": str(e)}