"""
Unit tests for the Image Processing Pipeline API.
Run with: python -m pytest tests/ -v
"""

import io
import json
import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use a temp DB for tests
os.environ["TESTING"] = "1"
import tempfile

# Patch DB_PATH before importing app modules
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import app.database as db_module

db_module.DB_PATH = _tmp_db.name

from app.main import create_app


def _make_tiny_png() -> bytes:
    """Return bytes of a minimal valid PNG (1×1 red pixel)."""
    from PIL import Image as PILImage

    buf = io.BytesIO()
    img = PILImage.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_tiny_jpg() -> bytes:
    from PIL import Image as PILImage

    buf = io.BytesIO()
    img = PILImage.new("RGB", (10, 10), color=(0, 128, 0))
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestImageAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    # ------------------------------------------------------------------
    # POST /api/images
    # ------------------------------------------------------------------

    def test_upload_png_returns_201(self):
        data = {"file": (io.BytesIO(_make_tiny_png()), "test.png")}
        res = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertIn("image_id", body["data"])

    def test_upload_jpg_returns_201(self):
        data = {"file": (io.BytesIO(_make_tiny_jpg()), "photo.jpg")}
        res = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body["status"], "success")

    def test_upload_invalid_format_returns_422(self):
        data = {"file": (io.BytesIO(b"not an image"), "doc.xlsx")}
        res = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 422)
        body = res.get_json()
        self.assertEqual(body["status"], "failed")

    def test_upload_no_file_returns_400(self):
        res = self.client.post("/api/images", data={}, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_upload_corrupt_image_returns_422(self):
        data = {"file": (io.BytesIO(b"\x89PNG corrupt bytes"), "bad.png")}
        res = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 422)

    # ------------------------------------------------------------------
    # GET /api/images
    # ------------------------------------------------------------------

    def test_list_images_returns_list(self):
        res = self.client.get("/api/images")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertIsInstance(body, list)

    # ------------------------------------------------------------------
    # GET /api/images/<id>
    # ------------------------------------------------------------------

    def test_get_image_by_id(self):
        # Upload first
        data = {"file": (io.BytesIO(_make_tiny_png()), "detail_test.png")}
        up = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        image_id = up.get_json()["data"]["image_id"]

        res = self.client.get(f"/api/images/{image_id}")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["data"]["image_id"], image_id)
        self.assertIn("thumbnails", body["data"])

    def test_get_nonexistent_image_returns_404(self):
        res = self.client.get("/api/images/does_not_exist")
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------------------------
    # GET /api/images/<id>/thumbnails/<size>
    # ------------------------------------------------------------------

    def test_thumbnail_small_returns_image(self):
        data = {"file": (io.BytesIO(_make_tiny_png()), "thumb_test.png")}
        up = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        image_id = up.get_json()["data"]["image_id"]

        res = self.client.get(f"/api/images/{image_id}/thumbnails/small")
        self.assertEqual(res.status_code, 200)
        self.assertIn("image/", res.content_type)

    def test_thumbnail_medium_returns_image(self):
        data = {"file": (io.BytesIO(_make_tiny_jpg()), "medium_thumb.jpg")}
        up = self.client.post("/api/images", data=data, content_type="multipart/form-data")
        image_id = up.get_json()["data"]["image_id"]

        res = self.client.get(f"/api/images/{image_id}/thumbnails/medium")
        self.assertEqual(res.status_code, 200)

    def test_thumbnail_invalid_size_returns_400(self):
        res = self.client.get("/api/images/any_id/thumbnails/huge")
        self.assertEqual(res.status_code, 400)

    # ------------------------------------------------------------------
    # GET /api/stats
    # ------------------------------------------------------------------

    def test_stats_structure(self):
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        for key in ("total", "failed", "success_rate", "average_processing_time_seconds"):
            self.assertIn(key, body)

    def test_stats_success_rate_format(self):
        res = self.client.get("/api/stats")
        body = res.get_json()
        # Should end with %
        self.assertTrue(body["success_rate"].endswith("%"))


if __name__ == "__main__":
    unittest.main()
