"""
Image Processing Pipeline API
Main Flask application entry point.
"""

from flask import Flask
from app.database import init_db
from app.routes import register_routes
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_app():
    """Application factory."""
    app = Flask(__name__)

    # Initialize the SQLite database
    init_db()
    logger.info("Database initialised.")

    # Register all route blueprints
    register_routes(app)
    logger.info("Routes registered.")

    return app


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Image Processing Pipeline API on http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
