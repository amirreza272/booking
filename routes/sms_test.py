from flask import Blueprint, jsonify, request
from config import Config
from services.sms import send_sms

sms_test_bp = Blueprint("sms_test", __name__, url_prefix="/api/setup")


@sms_test_bp.route("/sms-test")
def sms_test():
    key = request.args.get("key", "")
    if key != Config.SETUP_SECRET_KEY:
        return jsonify({"success": False, "message": "دسترسی غیرمجاز"}), 403

    phone = request.args.get("phone", "").strip()
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        return jsonify({"success": False, "message": "پارامتر phone معتبر نیست (فرمت 09xxxxxxxxx)"}), 400

    # پیش‌فرض: بدون پسوند لغو۱۱ — برای همین تست وجود داره
    # با ?unsub=1 می‌تونی نسخه‌ی با پسوند رو هم تست کنی
    append_unsub = request.args.get("unsub", "0") == "1"

    message = "کلینیک مسیر — این یک پیامک تستی است."

    result = send_sms([phone], message, append_unsubscribe=append_unsub)

    return jsonify({
        "sent_with_unsubscribe_suffix": append_unsub,
        "result": result,
    })