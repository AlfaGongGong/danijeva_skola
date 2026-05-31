from flask import Blueprint, request, jsonify
from config import ADMIN_PASSWORD, ACCESS_PASSWORD

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth", methods=["POST"])
def api_auth():
    d = request.json or {}
    user = d.get("user")
    pw = d.get("pw")

    if user == "admin" and pw == ADMIN_PASSWORD:
        return jsonify({"ok": True, "role": "admin"})
    if request.remote_addr in ["127.0.0.1", "::1"]:
        if pw == ADMIN_PASSWORD and user == "admin":
            return jsonify({"ok": True, "role": "admin"})
        elif pw == ACCESS_PASSWORD:
            return jsonify({"ok": True, "role": "student", "user": user or "Dani"})
        return jsonify({"ok": False, "msg": "Pristup odbijen"})
    if pw == ACCESS_PASSWORD:
        return jsonify({"ok": True, "role": "student", "user": user or "Dani"})
    return jsonify({"ok": False, "role": "student"})
