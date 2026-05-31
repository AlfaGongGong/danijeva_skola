import os
from flask import Blueprint, send_from_directory, abort
from config import ATLAS_DIR

atlas_bp = Blueprint("atlas", __name__)


@atlas_bp.route("/atlas/<path:filename>")
def serve_atlas_image(filename):
    # Prevent path traversal
    safe_name = os.path.normpath(filename)
    if safe_name.startswith("..") or os.path.isabs(safe_name):
        abort(403)
    abs_path = os.path.abspath(os.path.join(ATLAS_DIR, safe_name))
    if not abs_path.startswith(os.path.abspath(ATLAS_DIR)):
        abort(403)
    return send_from_directory(ATLAS_DIR, safe_name)
