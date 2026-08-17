from flask import Blueprint, jsonify, request
from services.booking import get_available_days, get_free_slots

booking_bp = Blueprint("booking", __name__, url_prefix="/api")


@booking_bp.route("/available-days")
def available_days():
    return jsonify(get_available_days())


@booking_bp.route("/slots")
def slots():
    date         = request.args.get("date", "").strip()
    session_type = request.args.get("type", "online").strip()

    if not date:
        return jsonify({
            "success": False,
            "message": "پارامتر date الزامی است"
        }), 400

    return jsonify(get_free_slots(date, session_type))


@booking_bp.route("/health")
def health():
    return jsonify({"status": "ok"})
