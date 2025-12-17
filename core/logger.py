import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configure logging for the entire application."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "ytbmusic.log"

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            ),
            # We do NOT add StreamHandler because it would mess up Urwid UI
        ],
    )

    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.CRITICAL)

    return logging.getLogger("YTBMusic")
