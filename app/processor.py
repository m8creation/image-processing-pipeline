"""
Image processing logic:
  - Generate thumbnails (small: 128×128, medium: 512×512)
  - Extract metadata (dimensions, format, size, datetime)
  - Extract EXIF data (bonus)
  - Caption via HuggingFace Inference API (Salesforce/blip-image-captioning-large)
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from PIL import Image, ExifTags
import requests

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
THUMBNAIL_DIR = os.path.join(os.path.dirname(__file__), "..", "thumbnails")
SUPPORTED_FORMATS = {"jpg", "jpeg", "png"}

# Thumbnail sizes
SMALL_SIZE = (128, 128)
MEDIUM_SIZE = (512, 512)

# HuggingFace Inference API (free, no auth for public models)
HF_API_URL = (
    "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
)


def _ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)


def _get_exif(image: Image.Image) -> dict:
    """Extract EXIF data if available."""
    try:
        raw_exif = image._getexif()
        if not raw_exif:
            return {}
        readable = {}
        for tag_id, value in raw_exif.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            # Skip binary / IFD objects
            if isinstance(value, bytes):
                continue
            if hasattr(value, "numerator"):
                value = float(value)
            readable[tag] = str(value)
        return readable
    except Exception as exc:  # noqa: BLE001
        logger.debug("EXIF extraction failed: %s", exc)
        return {}


def _generate_caption(image_path: str) -> str:
    """Request a caption from HuggingFace Inference API."""
    try:
        with open(image_path, "rb") as fh:
            data = fh.read()
        response = requests.post(
            HF_API_URL,
            headers={"Content-Type": "application/octet-stream"},
            data=data,
            timeout=30,
        )
        if response.ok:
            result = response.json()
            if isinstance(result, list) and result:
                return result[0].get("generated_text", "No caption generated")
        logger.warning("Caption API returned %s: %s", response.status_code, response.text[:200])
        return "Caption unavailable"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Caption generation failed: %s", exc)
        return "Caption unavailable"


def process_image(file_bytes: bytes, original_name: str) -> dict:
    """
    Full processing pipeline for a single image.

    Returns a dict with all metadata, thumbnail paths, caption, and timings.
    Raises ValueError for unsupported formats or invalid images.
    """
    _ensure_dirs()
    start = time.monotonic()

    # Validate extension
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: .{ext}. Only JPG and PNG are accepted.")

    image_id = "img_" + uuid.uuid4().hex[:10]
    save_ext = "jpg" if ext in {"jpg", "jpeg"} else "png"
    original_path = os.path.join(UPLOAD_DIR, f"{image_id}.{save_ext}")
    small_path = os.path.join(THUMBNAIL_DIR, f"{image_id}_small.{save_ext}")
    medium_path = os.path.join(THUMBNAIL_DIR, f"{image_id}_medium.{save_ext}")

    # Write raw upload to disk
    with open(original_path, "wb") as fh:
        fh.write(file_bytes)

    # Open and validate image
    try:
        img = Image.open(original_path)
        img.verify()
        img = Image.open(original_path)  # Re-open after verify
    except Exception as exc:
        os.remove(original_path)
        raise ValueError(f"Invalid image file: {exc}") from exc

    width, height = img.size
    fmt = img.format or save_ext.upper()
    size_bytes = len(file_bytes)
    file_datetime = datetime.fromtimestamp(
        os.path.getmtime(original_path), tz=timezone.utc
    ).isoformat()

    # EXIF (bonus)
    exif_data = _get_exif(img) if ext in {"jpg", "jpeg"} else {}

    # Thumbnails — use LANCZOS for quality
    for size, path in [(SMALL_SIZE, small_path), (MEDIUM_SIZE, medium_path)]:
        thumb = img.copy()
        thumb.thumbnail(size, Image.LANCZOS)
        thumb.save(path)
    logger.info("Thumbnails generated for %s", image_id)

    # Caption
    logger.info("Requesting caption for %s via HuggingFace API", image_id)
    caption = _generate_caption(original_path)
    logger.info("Caption for %s: %s", image_id, caption)

    elapsed = time.monotonic() - start

    return {
        "image_id": image_id,
        "original_name": original_name,
        "status": "success",
        "processed_at": datetime.now(tz=timezone.utc).isoformat(),
        "metadata": {
            "width": width,
            "height": height,
            "format": fmt.lower(),
            "size_bytes": size_bytes,
            "file_datetime": file_datetime,
        },
        "exif_data": exif_data,
        "caption": caption,
        "processing_time_seconds": round(elapsed, 3),
        "error": None,
    }
