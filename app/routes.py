"""
Route definitions for the Image Processing Pipeline API.
"""

import json
import logging
import os
from flask import Blueprint, request, jsonify, send_file, abort

from app.database import get_db
from app.processor import process_image, THUMBNAIL_DIR

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thumbnail_urls(image_id: str) -> dict:
    return {
        "small": f"{BASE_URL}/api/images/{image_id}/thumbnails/small",
        "medium": f"{BASE_URL}/api/images/{image_id}/thumbnails/medium",
    }


def _row_to_response(row) -> dict:
    """Convert a DB row to the standard response format."""
    row = dict(row)
    status = row["status"]
    image_id = row["image_id"]

    metadata = {}
    thumbnails = {}

    if status == "success":
        metadata = {
            "width": row.get("width"),
            "height": row.get("height"),
            "format": row.get("format"),
            "size_bytes": row.get("size_bytes"),
            "file_datetime": row.get("file_datetime"),
        }
        if row.get("exif_data"):
            try:
                metadata["exif"] = json.loads(row["exif_data"])
            except (json.JSONDecodeError, TypeError):
                pass
        if row.get("caption"):
            metadata["caption"] = row["caption"]
        thumbnails = _thumbnail_urls(image_id)

    return {
        "status": status,
        "data": {
            "image_id": image_id,
            "original_name": row["original_name"],
            "processed_at": row.get("processed_at"),
            "metadata": metadata,
            "thumbnails": thumbnails,
        },
        "error": row.get("error"),
    }


# ---------------------------------------------------------------------------
# POST /api/images
# ---------------------------------------------------------------------------

@api.route("/images", methods=["POST"])
def upload_image():
    """Upload and process an image synchronously."""
    if "file" not in request.files:
        return jsonify({"status": "error", "error": "No file part in request"}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"status": "error", "error": "No file selected"}), 400

    file_bytes = file.read()
    original_name = file.filename

    logger.info("Received upload: %s (%d bytes)", original_name, len(file_bytes))

    try:
        result = process_image(file_bytes, original_name)
    except ValueError as exc:
        # Invalid file — store a failed record
        logger.warning("Processing failed for %s: %s", original_name, exc)
        failed_id = "img_" + __import__("uuid").uuid4().hex[:10]
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO images
                   (image_id, original_name, status, processed_at, error)
                   VALUES (?, ?, 'failed', datetime('now'), ?)""",
                (failed_id, original_name, str(exc)),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"status": "failed", "data": {"image_id": failed_id}, "error": str(exc)}), 422

    # Persist success record
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO images
               (image_id, original_name, status, processed_at,
                width, height, format, size_bytes, file_datetime,
                caption, exif_data, processing_time_seconds)
               VALUES (?, ?, 'success', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result["image_id"],
                result["original_name"],
                result["processed_at"],
                result["metadata"]["width"],
                result["metadata"]["height"],
                result["metadata"]["format"],
                result["metadata"]["size_bytes"],
                result["metadata"]["file_datetime"],
                result.get("caption"),
                json.dumps(result.get("exif_data", {})),
                result["processing_time_seconds"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Image %s processed successfully in %.2fs", result["image_id"], result["processing_time_seconds"])

    # Build response
    response_data = {
        "status": "success",
        "data": {
            "image_id": result["image_id"],
            "original_name": result["original_name"],
            "processed_at": result["processed_at"],
            "metadata": result["metadata"],
            "thumbnails": _thumbnail_urls(result["image_id"]),
        },
        "error": None,
    }
    # Include caption and exif in metadata for the response
    response_data["data"]["metadata"]["caption"] = result.get("caption")
    if result.get("exif_data"):
        response_data["data"]["metadata"]["exif"] = result["exif_data"]

    return jsonify(response_data), 201


# ---------------------------------------------------------------------------
# GET /api/images
# ---------------------------------------------------------------------------

@api.route("/images", methods=["GET"])
def list_images():
    """List all images."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM images ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()

    return jsonify([_row_to_response(r) for r in rows])


# ---------------------------------------------------------------------------
# GET /api/images/<id>
# ---------------------------------------------------------------------------

@api.route("/images/<image_id>", methods=["GET"])
def get_image(image_id: str):
    """Get details for a specific image."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM images WHERE image_id = ?", (image_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"status": "error", "error": "Image not found"}), 404

    return jsonify(_row_to_response(row))


# ---------------------------------------------------------------------------
# GET /api/images/<id>/thumbnails/<size>
# ---------------------------------------------------------------------------

@api.route("/images/<image_id>/thumbnails/<size>", methods=["GET"])
def get_thumbnail(image_id: str, size: str):
    """Return the small or medium thumbnail file."""
    if size not in {"small", "medium"}:
        return jsonify({"status": "error", "error": "Size must be 'small' or 'medium'"}), 400

    # Find the thumbnail file
    for ext in ("jpg", "png"):
        path = os.path.join(THUMBNAIL_DIR, f"{image_id}_{size}.{ext}")
        if os.path.exists(path):
            return send_file(path, mimetype=f"image/{ext}")

    return jsonify({"status": "error", "error": "Thumbnail not found"}), 404


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------

@api.route("/stats", methods=["GET"])
def get_stats():
    """Return processing statistics."""
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
                 AVG(CASE WHEN status='success' THEN processing_time_seconds END) AS avg_time
               FROM images"""
        ).fetchone()
    finally:
        conn.close()

    total = row["total"] or 0
    failed = row["failed"] or 0
    success = total - failed
    success_rate = f"{(success / total * 100):.2f}%" if total > 0 else "0%"
    avg_time = round(row["avg_time"] or 0, 2)

    return jsonify(
        {
            "total": total,
            "failed": failed,
            "success_rate": success_rate,
            "average_processing_time_seconds": avg_time,
        }
    )


def register_routes(app):
    app.register_blueprint(api)
