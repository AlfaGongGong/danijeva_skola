from flask import Blueprint, send_from_directory
from config import ATLAS_DIR

atlas_bp = Blueprint("atlas", __name__)


@atlas_bp.route("/atlas/<path:filename>")
def serve_atlas_image(filename):
    return send_from_directory(ATLAS_DIR, filename)
