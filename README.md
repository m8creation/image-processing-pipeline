# Image Processing Pipeline API

A RESTful API built with **Flask** and **SQLite** that accepts image uploads, generates thumbnails, extracts metadata (including EXIF), captions images via the HuggingFace Inference API, and exposes processing statistics.

---

## Project Overview

| Component | Technology |
|-----------|-----------|
| Web framework | Flask 3 |
| Database | SQLite (built-in, no server needed) |
| Image processing | Pillow |
| AI captioning | [Salesforce/blip-image-captioning-large](https://huggingface.co/Salesforce/blip-image-captioning-large) via HuggingFace free Inference API |
| Tests | Python `unittest` |

---

## Processing Pipeline

```
Client → POST /api/images
           │
           ▼
    Validate format (JPG / PNG only)
           │
           ▼
    Save original to disk (uploads/)
           │
           ▼
    Open with Pillow → verify integrity
           │
           ▼
    Extract metadata (dimensions, format, size, datetime)
           │
           ▼
    Extract EXIF data (bonus, JPEG only)
           │
           ├── Generate small thumbnail  128×128 → thumbnails/
           └── Generate medium thumbnail 512×512 → thumbnails/
           │
           ▼
    Request caption via HuggingFace Inference API
           │
           ▼
    Persist record to SQLite (images.db)
           │
           ▼
    Return JSON response (201)
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- pip

### Local (without Docker)

```bash
# Clone / enter the repo
cd image-pipeline

# Install dependencies
pip install -r requirements.txt

# Start the server
python app/main.py
# → http://localhost:8000
```

### With Docker (bonus)

```bash
docker build -t image-pipeline .
docker run -p 8000:8000 image-pipeline
```

Set a custom base URL (for correct thumbnail links):

```bash
docker run -p 8000:8000 -e BASE_URL=http://myserver.com image-pipeline
```

---

## API Documentation

### POST `/api/images`

Upload and process an image.

**Request** – `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | JPG or PNG image |

**Response 201**
```json
{
  "status": "success",
  "data": {
    "image_id": "img_a1b2c3d4e5",
    "original_name": "photo.jpg",
    "processed_at": "2024-03-10T10:00:00+00:00",
    "metadata": {
      "width": 1920,
      "height": 1080,
      "format": "jpeg",
      "size_bytes": 2048576,
      "file_datetime": "2024-03-10T10:00:00+00:00",
      "caption": "a dog running in a field",
      "exif": { "Make": "Apple", "Model": "iPhone 14" }
    },
    "thumbnails": {
      "small": "http://localhost:8000/api/images/img_a1b2c3d4e5/thumbnails/small",
      "medium": "http://localhost:8000/api/images/img_a1b2c3d4e5/thumbnails/medium"
    }
  },
  "error": null
}
```

**Response 422** (invalid image / unsupported format)
```json
{
  "status": "failed",
  "data": { "image_id": "img_xyz" },
  "error": "Unsupported format: .xlsx. Only JPG and PNG are accepted."
}
```

---

### GET `/api/images`

List all processed images.

```bash
curl http://localhost:8000/api/images
```

Returns an array of image objects (same structure as above).

---

### GET `/api/images/{id}`

Get details for a specific image.

```bash
curl http://localhost:8000/api/images/img_a1b2c3d4e5
```

---

### GET `/api/images/{id}/thumbnails/{small|medium}`

Return the thumbnail file directly (as image/jpeg or image/png).

```bash
curl -O http://localhost:8000/api/images/img_a1b2c3d4e5/thumbnails/small
curl -O http://localhost:8000/api/images/img_a1b2c3d4e5/thumbnails/medium
```

---

### GET `/api/stats`

Processing statistics.

```bash
curl http://localhost:8000/api/stats
```

```json
{
  "total": 10,
  "failed": 2,
  "success_rate": "80.00%",
  "average_processing_time_seconds": 4.23
}
```

---

## Example Usage

### Upload an image with curl

```bash
curl -X POST http://localhost:8000/api/images \
  -F "file=@/path/to/photo.jpg"
```

### Upload with Python

```python
import requests

with open("photo.png", "rb") as f:
    r = requests.post("http://localhost:8000/api/images", files={"file": f})
print(r.json())
```

### Download a thumbnail

```bash
curl -o small.jpg http://localhost:8000/api/images/img_a1b2c3d4e5/thumbnails/small
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

All tests use an in-memory temporary database — no server needed.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | Used to construct thumbnail URLs in responses |

---

## Notes on AI Captioning

The captioning endpoint uses HuggingFace's **free** Inference API (no API key required for public models). The first request to a model may take ~20 seconds as HuggingFace "warms up" the model. Subsequent requests are faster. If the API is unavailable, the caption field returns `"Caption unavailable"` and processing continues normally.

---

## Project Structure

```
image-pipeline/
├── app/
│   ├── __init__.py
│   ├── main.py          # Flask app factory & entry point
│   ├── database.py      # SQLite setup
│   ├── processor.py     # Image processing pipeline
│   └── routes.py        # API route handlers
├── tests/
│   └── test_api.py      # Unit tests
├── uploads/             # Original uploaded images (auto-created)
├── thumbnails/          # Generated thumbnails (auto-created)
├── images.db            # SQLite database (auto-created)
├── requirements.txt
├── Dockerfile
└── README.md
```
